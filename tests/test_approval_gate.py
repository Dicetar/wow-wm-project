from wm.llm.proposal_adapter import Proposal, ProposalKind
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue

def _pending_quest():
    return Proposal(kind=ProposalKind.QUEST, character_guid=5407,
                    payload={"quest_release": {"title": "x", "objective": "y", "description": "z",
                              "giver_creature_entry": 197, "objective_kind": "kill_creature",
                              "rewards": {"xp": 10}}},
                    narrative_summary="hi", provenance={"mode": "fixture"})

def test_blocked_proposal_routes_to_issues_queue():
    iq = IssuesQueue()
    gate = ApprovalGate(issues=iq)
    blocked = Proposal(kind=ProposalKind.QUEST, character_guid=5407, payload={},
                       is_blocked=True, block_reason="missing quest_release")
    gate.submit(blocked)
    assert gate.pending() == []
    assert len(iq.list_open()) == 1
    assert iq.list_open()[0].reason == "missing quest_release"

def test_pending_proposal_can_be_approved():
    iq = IssuesQueue()
    applied: list[dict] = []
    def fake_quest_compiler(p): applied.append({"kind":"quest","payload":p.payload}); return {"ok": True, "request_ids":[123]}
    def fake_ability_compiler(p): raise AssertionError("not used here")
    gate = ApprovalGate(issues=iq, quest_compiler=fake_quest_compiler, ability_compiler=fake_ability_compiler)
    p = _pending_quest()
    gate.submit(p)
    pid = gate.pending()[0].id
    result = gate.approve(pid)
    assert result.ok
    assert applied and applied[0]["kind"] == "quest"
    assert gate.pending() == []

def test_rejection_records_and_drops():
    iq = IssuesQueue()
    gate = ApprovalGate(issues=iq)
    gate.submit(_pending_quest())
    pid = gate.pending()[0].id
    gate.reject(pid, reason="operator-deferred")
    assert gate.pending() == []
    # rejected proposals are logged in issues for triage
    assert any(i.reason == "operator-deferred" for i in iq.list_open())


def test_every_proposal_kind_has_a_wired_applier_slot():
    # Guard: adding a ProposalKind without a constructor slot + _applier_for entry
    # must fail here rather than silently parking every such proposal to issues.
    sentinel = lambda p: {"ok": True}
    gate = ApprovalGate(
        issues=IssuesQueue(),
        quest_compiler=sentinel, ability_compiler=sentinel, scene_compiler=sentinel,
        item_applier=sentinel, spell_applier=sentinel, action_applier=sentinel,
    )
    for kind in ProposalKind:
        assert gate._applier_for(kind) is sentinel, f"{kind} has no wired applier slot"


def _pending_item():
    return Proposal(kind=ProposalKind.ITEM, character_guid=5407,
                    payload={"item_release": {"item_entry": 910013, "name": "Lens"}},
                    provenance={"mode": "fixture"})


def _pending_spell():
    return Proposal(kind=ProposalKind.SPELL, character_guid=5407,
                    payload={"spell_release": {"spell_entry": 946099, "name": "Echo Blast"}},
                    provenance={"mode": "fixture"})


def test_item_proposal_dispatches_to_item_applier():
    iq = IssuesQueue()
    seen: list[dict] = []
    gate = ApprovalGate(issues=iq, item_applier=lambda p: seen.append({"kind": p.kind.value}) or {"ok": True})
    gate.submit(_pending_item())
    result = gate.approve(gate.pending()[0].id)
    assert result.ok
    assert seen and seen[0]["kind"] == "item"


def test_spell_proposal_dispatches_to_spell_applier():
    iq = IssuesQueue()
    seen: list[dict] = []
    gate = ApprovalGate(issues=iq, spell_applier=lambda p: seen.append({"kind": p.kind.value}) or {"ok": True})
    gate.submit(_pending_spell())
    result = gate.approve(gate.pending()[0].id)
    assert result.ok
    assert seen and seen[0]["kind"] == "spell"


def test_mode_is_passed_to_mode_aware_applier():
    iq = IssuesQueue()
    modes: list[str] = []

    def mode_aware_applier(p, *, mode):
        modes.append(mode)
        return {"ok": True, "mode": mode}

    gate = ApprovalGate(issues=iq, spell_applier=mode_aware_applier)
    gate.submit(_pending_spell())
    gate.approve(gate.pending()[0].id, mode="dry-run")
    assert modes == ["dry-run"]


def test_legacy_one_arg_compiler_still_works_without_mode():
    iq = IssuesQueue()
    calls: list[int] = []
    # legacy 1-arg compiler must not receive a mode kwarg
    gate = ApprovalGate(issues=iq, quest_compiler=lambda p: calls.append(1) or {"ok": True})
    gate.submit(_pending_quest())
    result = gate.approve(gate.pending()[0].id, mode="apply")
    assert result.ok
    assert calls == [1]


def test_unwired_kind_parks_to_issues():
    iq = IssuesQueue()
    gate = ApprovalGate(issues=iq)  # no item applier
    gate.submit(_pending_item())
    result = gate.approve(gate.pending()[0].id)
    assert not result.ok
    assert result.error == "no_applier"
    assert len(iq.list_open()) == 1


def test_rollback_dispatches_to_lane_rollback():
    iq = IssuesQueue()
    calls: list[tuple[int, str]] = []
    gate = ApprovalGate(issues=iq, spell_rollback=lambda entry, mode: calls.append((entry, mode)) or {"ok": True})
    result = gate.rollback(artifact_type="spell", artifact_entry=946099, mode="apply")
    assert result.ok
    assert calls == [(946099, "apply")]


def test_rollback_unwired_type_parks_to_issues():
    iq = IssuesQueue()
    gate = ApprovalGate(issues=iq)
    result = gate.rollback(artifact_type="item", artifact_entry=910013)
    assert not result.ok
    assert result.error == "no_rollback"
    assert len(iq.list_open()) == 1


def test_rollback_exception_is_caught_and_parked():
    iq = IssuesQueue()

    def boom(entry, mode):
        raise RuntimeError("db down")

    gate = ApprovalGate(issues=iq, spell_rollback=boom)
    result = gate.rollback(artifact_type="spell", artifact_entry=946099)
    assert not result.ok
    assert "db down" in result.error
    assert len(iq.list_open()) == 1
