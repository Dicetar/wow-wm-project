from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from wm.autoplay.durable_native import LedgerRequest, native_key_for, run_durable_native_intent
from wm.autoplay.durable_native import DirectorLedger
from wm.config import Settings


class FakeLedger:
    def __init__(self) -> None:
        self.request: LedgerRequest | None = None
        self.transitions: list[str] = []

    def accept(self, *, origin_key, player_guid, verb, proposal):
        if self.request is None:
            self.request = LedgerRequest(
                request_id=7, origin_key=origin_key, player_guid=player_guid, verb=verb,
                proposal_hash="hash", native_key=native_key_for(proposal, verb),
                state="received", revision=0, native_request_id=None, result=None,
                age_seconds=0,
            )
        elif (self.request.origin_key, self.request.player_guid, self.request.verb) != (origin_key, player_guid, verb):
            raise ValueError("origin key scope mismatch")
        return self.request

    def transition(self, request, *, state, reason, native_request_id=None, result=None):
        if request.revision != self.request.revision:
            raise RuntimeError("stale worker")
        self.transitions.append(f"{request.state}:{state}:{reason}")
        self.request = replace(
            request, state=state, revision=request.revision + 1,
            native_request_id=native_request_id or request.native_request_id,
            result=result or request.result, age_seconds=0,
        )
        return self.request


def _proposal():
    return SimpleNamespace(idempotency_key="autoplay:intent:test")


def _receipt(status="done"):
    return SimpleNamespace(request_id=91, status=status, to_dict=lambda: {"request_id": 91, "status": status})


def test_durable_native_key_matches_existing_executor_contract():
    from wm.events.executor import _native_bridge_action_idempotency_key
    from wm.events.models import ReactionPlan, SubjectRef

    proposal = _proposal()
    plan = ReactionPlan(
        plan_key=proposal.idempotency_key, opportunity_type="control:manual_admin_action",
        rule_type="manual_admin_action", player_guid=1,
        subject=SubjectRef(subject_type="control", subject_entry=0), actions=[],
        metadata={"control_proposal": {}},
    )
    assert native_key_for(proposal, "world_announce_to_player") == _native_bridge_action_idempotency_key(
        plan=plan, native_action_kind="world_announce_to_player", payload={},
    )


def _run(ledger, apply, lookup):
    return run_durable_native_intent(
        ledger=ledger, origin_key="wm_chat:1:event-5", player_guid=1,
        verb="world_announce_to_player", proposal=_proposal(),
        apply=apply, lookup_native=lookup,
    )


def test_durable_native_records_dispatch_before_effect_and_deduplicates():
    ledger = FakeLedger()
    effects = []

    def apply():
        assert ledger.request.state == "dispatching"
        effects.append("native_submit")
        return SimpleNamespace(status="applied")

    first = _run(ledger, apply, lambda key: _receipt())
    second = _run(ledger, apply, lambda key: _receipt())
    assert first["state"] == second["state"] == "verified"
    assert effects == ["native_submit"]
    assert ledger.transitions[0].startswith("received:dispatching")


def test_durable_native_restart_reconciles_completed_receipt_without_resubmit():
    ledger = FakeLedger()
    assert _run(ledger, lambda: (_ for _ in ()).throw(ConnectionError("lost after send")), lambda key: None)["state"] == "dispatching"
    recovered = _run(ledger, lambda: pytest.fail("must not submit again"), lambda key: _receipt())
    assert recovered["state"] == "verified"
    assert recovered["result"]["request_id"] == 91


def test_durable_native_unknown_result_does_not_retry_and_can_reconcile_later():
    ledger = FakeLedger()
    _run(ledger, lambda: SimpleNamespace(status="failed"), lambda key: None)
    assert ledger.request.state == "needs_operator"
    assert _run(ledger, lambda: pytest.fail("must not submit again"), lambda key: None)["state"] == "needs_operator"
    assert _run(ledger, lambda: pytest.fail("must not submit again"), lambda key: _receipt())["state"] == "verified"


def test_durable_native_control_rejection_is_terminal_without_native_lookup():
    ledger = FakeLedger()
    result = _run(ledger, lambda: SimpleNamespace(status="rejected"),
                  lambda key: pytest.fail("rejected control never submitted native action"))
    assert result["state"] == "failed"


def test_durable_native_parallel_observer_does_not_steal_active_dispatch():
    ledger = FakeLedger()
    ledger.accept(origin_key="wm_chat:1:event-5", player_guid=1, verb="world_announce_to_player", proposal=_proposal())
    ledger.transition(ledger.request, state="dispatching", reason="test")
    result = _run(ledger, lambda: pytest.fail("must not submit again"), lambda key: None)
    assert result["state"] == "dispatching"
    assert ledger.request.state == "dispatching"


def test_durable_native_old_missing_receipt_needs_operator():
    ledger = FakeLedger()
    ledger.accept(origin_key="wm_chat:1:event-5", player_guid=1, verb="world_announce_to_player", proposal=_proposal())
    ledger.transition(ledger.request, state="dispatching", reason="test")
    ledger.request = replace(ledger.request, age_seconds=60)
    assert _run(ledger, lambda: pytest.fail("must not submit again"), lambda key: None)["state"] == "needs_operator"


class FakeSqlConnection:
    def __init__(self, row):
        self.row = row
        self.statements = []
        self.lastrowid = 7
        self.rowcount = 1
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.statements.append((sql, params))
        if sql.startswith("UPDATE wm_director_request"):
            self.row["State"] = params[0]
            self.row["Revision"] += 1

    def fetchone(self):
        return dict(self.row)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def test_sql_ledger_accept_and_transition_use_parameterized_transactions():
    class Proposal:
        idempotency_key = "autoplay:intent:test"

        def model_dump(self, *, mode):
            return {"idempotency_key": self.idempotency_key}

    import hashlib
    import json

    proposal = Proposal()
    proposal_hash = hashlib.sha256(json.dumps(
        proposal.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    row = {
        "RequestID": 7, "OriginKey": "wm_chat:1:event-5", "PlayerGUID": 1,
        "Verb": "world_announce_to_player", "ProposalHash": proposal_hash,
        "NativeKey": native_key_for(proposal, "world_announce_to_player"),
        "State": "received", "Revision": 0, "NativeRequestID": None,
        "ResultJSON": None, "AgeSeconds": 0,
    }
    conn = FakeSqlConnection(row)
    ledger = DirectorLedger(settings=Settings(), connect=lambda **kwargs: conn)
    accepted = ledger.accept(
        origin_key=row["OriginKey"], player_guid=1,
        verb="world_announce_to_player", proposal=proposal,
    )
    dispatching = ledger.transition(accepted, state="dispatching", reason="test")
    assert dispatching.state == "dispatching"
    assert dispatching.revision == 1
    assert conn.commits == 2 and conn.rollbacks == 0
    assert any("ON DUPLICATE KEY" in sql for sql, _ in conn.statements)
    assert all("event-5" not in sql for sql, _ in conn.statements)


def test_sql_ledger_rejects_origin_with_changed_proposal():
    class Proposal:
        idempotency_key = "autoplay:intent:test"

        def model_dump(self, *, mode):
            return {"value": "new"}

    row = {
        "RequestID": 7, "OriginKey": "wm_chat:1:event-5", "PlayerGUID": 1,
        "Verb": "world_announce_to_player", "ProposalHash": "old",
        "NativeKey": "old", "State": "received", "Revision": 0,
        "NativeRequestID": None, "ResultJSON": None, "AgeSeconds": 0,
    }
    conn = FakeSqlConnection(row)
    ledger = DirectorLedger(settings=Settings(), connect=lambda **kwargs: conn)
    with pytest.raises(ValueError, match="different proposal"):
        ledger.accept(origin_key=row["OriginKey"], player_guid=1,
                      verb="world_announce_to_player", proposal=Proposal())
    assert conn.rollbacks == 1 and conn.commits == 0
