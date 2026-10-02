from __future__ import annotations

import os
from uuid import uuid4

import pytest

from wm.autoplay.director_work import DirectorWorkLedger, FrozenWork
from wm.config import Settings
from wm.events.models import ExecutionResult, ExecutionStepResult, PlannedAction, ReactionPlan, SubjectRef


def _plan() -> ReactionPlan:
    return ReactionPlan(
        plan_key="test:director:plan", opportunity_type="test", rule_type="test",
        player_guid=5408, subject=SubjectRef(subject_type="test", subject_entry=1),
        actions=[PlannedAction(kind="noop", payload={"value": "fixed"})],
    )


def test_frozen_work_round_trip_preserves_operations_and_hash() -> None:
    original = FrozenWork.from_runtime({"kind": "plan", "plan": _plan()})
    restored = FrozenWork.from_runtime(original.thaw())

    assert original == restored
    assert restored.payload["plan"]["actions"][0]["payload"] == {"value": "fixed"}


def test_frozen_work_rejects_changed_artifact() -> None:
    first = FrozenWork.from_runtime({"kind": "plan", "plan": _plan()})
    changed = _plan()
    changed.actions[0].payload["value"] = "changed"

    assert FrozenWork.from_runtime({"kind": "plan", "plan": changed}).artifact_hash != first.artifact_hash


@pytest.mark.db_integration
def test_director_ledger_survives_restart_and_fences_dispatch() -> None:
    import pymysql

    settings = Settings(
        world_db_host=os.environ["WM_TEST_DB_HOST"],
        world_db_port=int(os.environ.get("WM_TEST_DB_PORT", "33307")),
        world_db_name=os.environ.get("WM_TEST_DB_NAME", "acore_world"),
        world_db_user=os.environ.get("WM_TEST_DB_USER", "acore"),
        world_db_password=os.environ.get("WM_TEST_DB_PASSWORD", "acore"),
    )
    origin = f"test:director:{uuid4().hex}"
    artifact = FrozenWork.from_runtime({"kind": "plan", "plan": _plan()})
    ledger = DirectorWorkLedger(settings=settings)
    request_id: int | None = None
    rejected_request_id: int | None = None
    try:
        prepared = ledger.prepare(
            origin_key=origin, player_guid=5408, lane="test",
            artifact=artifact, preview={"status": "dry-run"}, evidence={"source": "test"},
        )
        request_id = prepared.request_id
        reviewed, review = ledger.load_review(request_id=request_id, player_guid=5408)
        assert reviewed == prepared
        assert review["preview"]["status"] == "dry-run"
        listed = next(row for row in ledger.list_recent(player_guid=5408) if row["request_id"] == request_id)
        assert listed["artifact"]["plan"]["actions"][0]["kind"] == "noop"
        with pytest.raises(ValueError, match="not found"):
            ledger.load_review(request_id=request_id, player_guid=5405)
        assert ledger.prepare(origin_key=origin, player_guid=5408, lane="test", artifact=artifact,
                              preview={"status": "dry-run"}, evidence={"source": "test"}).request_id == request_id
        changed = _plan()
        changed.actions[0].payload["value"] = "changed"
        with pytest.raises(ValueError, match="different work"):
            ledger.prepare(origin_key=origin, player_guid=5408, lane="test",
                           artifact=FrozenWork.from_runtime({"kind": "plan", "plan": changed}),
                           preview={}, evidence={})
        authorized = ledger.authorize(prepared, policy={"ok": True, "policy": "test"}, mode="automatic")
        claimed = ledger.claim(authorized)
        with pytest.raises(RuntimeError, match="another worker"):
            ledger.claim(authorized)
        assert DirectorWorkLedger(settings=settings).load(origin).state == "dispatching"
        receipt = ExecutionResult(
            mode="apply", plan=_plan(), status="applied",
            steps=[ExecutionStepResult(kind="noop", status="applied")],
        )
        applied = ledger.record_result(claimed, results=[receipt])
        assert applied.state == "applied"
        verified = ledger.verify(applied, proof={"ok": True, "source": "test_receipt"})
        assert verified.state == DirectorWorkLedger(settings=settings).load(origin).state == "verified"
        rejection = ledger.prepare(
            origin_key=f"{origin}:reject", player_guid=5408, lane="test", artifact=artifact,
            preview={"status": "dry-run"}, evidence={"source": "test"},
        )
        rejected_request_id = rejection.request_id
        assert ledger.reject(rejection, reason="operator_rejected").state == "rejected"
        with pytest.raises(ValueError, match="only unapproved"):
            ledger.reject(ledger.load(f"{origin}:reject"), reason="again")
    finally:
        if request_id is not None or rejected_request_id is not None:
            conn = pymysql.connect(
                host=settings.world_db_host, port=settings.world_db_port,
                user=settings.world_db_user, password=settings.world_db_password,
                database=settings.world_db_name, autocommit=False,
            )
            try:
                with conn.cursor() as cursor:
                    for table in ("wm_director_proof", "wm_director_effect", "wm_director_authorization",
                                  "wm_director_artifact", "wm_director_transition", "wm_director_request"):
                        for row_id in (request_id, rejected_request_id):
                            if row_id is not None:
                                cursor.execute(f"DELETE FROM {table} WHERE RequestID=%s", (row_id,))
                conn.commit()
            finally:
                conn.close()
