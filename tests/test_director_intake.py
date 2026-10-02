from __future__ import annotations

import os
from uuid import uuid4

import pytest

from wm.autoplay.decision import DirectorDecision
from wm.autoplay.director_intake import DirectorIntakeLedger
from wm.config import Settings


@pytest.mark.db_integration
def test_intake_freezes_evidence_and_first_decision() -> None:
    import pymysql

    settings = Settings(
        world_db_host=os.environ["WM_TEST_DB_HOST"],
        world_db_port=int(os.environ.get("WM_TEST_DB_PORT", "33307")),
        world_db_name=os.environ.get("WM_TEST_DB_NAME", "acore_world"),
        world_db_user=os.environ.get("WM_TEST_DB_USER", "acore"),
        world_db_password=os.environ.get("WM_TEST_DB_PASSWORD", "acore"),
    )
    ledger = DirectorIntakeLedger(settings=settings)
    origin = f"test:director:intake:{uuid4().hex}"
    evidence = {"player_request": "Give me a quest", "observed_at": "2026-10-01T00:00:00Z"}
    first = DirectorDecision("propose_content", "quest", {}, "requested", "")
    competing = DirectorDecision("no_action", "", {}, "duplicate", "")
    try:
        intake = ledger.prepare(origin_key=origin, player_guid=5408, evidence=evidence)
        assert intake.decision is None
        assert ledger.prepare(origin_key=origin, player_guid=5408, evidence=evidence) == intake
        with pytest.raises(ValueError, match="different evidence"):
            ledger.prepare(origin_key=origin, player_guid=5408,
                           evidence={**evidence, "player_request": "Changed"})
        with pytest.raises(ValueError, match="different evidence"):
            ledger.prepare(origin_key=origin, player_guid=5405, evidence=evidence)
        assert ledger.decide(intake, decision=first) == first
        assert ledger.decide(intake, decision=competing) == first
        assert ledger.prepare(origin_key=origin, player_guid=5408, evidence=evidence).decision == first
        row = next(row for row in ledger.list_recent(player_guid=5408) if row["origin_key"] == origin)
        assert row["evidence"] == evidence
        assert row["decision"]["outcome"] == "propose_content"
    finally:
        conn = pymysql.connect(
            host=settings.world_db_host, port=settings.world_db_port,
            user=settings.world_db_user, password=settings.world_db_password,
            database=settings.world_db_name, autocommit=False,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM wm_director_intake WHERE OriginKey=%s", (origin,))
            conn.commit()
        finally:
            conn.close()


@pytest.mark.db_integration
def test_missing_capability_creates_one_linked_development_task() -> None:
    import pymysql

    settings = Settings(
        world_db_host=os.environ["WM_TEST_DB_HOST"],
        world_db_port=int(os.environ.get("WM_TEST_DB_PORT", "33307")),
        world_db_name=os.environ.get("WM_TEST_DB_NAME", "acore_world"),
        world_db_user=os.environ.get("WM_TEST_DB_USER", "acore"),
        world_db_password=os.environ.get("WM_TEST_DB_PASSWORD", "acore"),
    )
    ledger = DirectorIntakeLedger(settings=settings)
    origin = f"test:director:capability:{uuid4().hex}"
    try:
        intake = ledger.prepare(origin_key=origin, player_guid=5408,
                                evidence={"player_request": "Need a new combat mechanic"})
        ledger.decide(intake, decision=DirectorDecision(
            "needs_capability", "combat.new_mechanic", {}, "not implemented", "",
        ))
        first = ledger.await_capability(
            origin_key=origin, player_guid=5408, request="Need a new combat mechanic",
            capability="combat.new_mechanic", reason="not implemented",
        )
        second = ledger.await_capability(
            origin_key=origin, player_guid=5408, request="Need a new combat mechanic",
            capability="combat.new_mechanic", reason="not implemented",
        )
        assert first == second
        assert first["deployment_authority"] == "separate_release_step"
        row = next(row for row in ledger.list_recent(player_guid=5408) if row["origin_key"] == origin)
        assert row["state"] == "awaiting_capability"
        assert row["development_task_id"] == first["task_id"]
        assert row["development_task"]["missing_capability"] == "combat.new_mechanic"
        with pytest.raises(ValueError, match="different content"):
            ledger.await_capability(
                origin_key=origin, player_guid=5408, request="Changed request",
                capability="combat.new_mechanic", reason="not implemented",
            )
    finally:
        conn = pymysql.connect(
            host=settings.world_db_host, port=settings.world_db_port,
            user=settings.world_db_user, password=settings.world_db_password,
            database=settings.world_db_name, autocommit=False,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM wm_director_development_task WHERE OriginKey=%s", (origin,))
                cursor.execute("DELETE FROM wm_director_intake WHERE OriginKey=%s", (origin,))
            conn.commit()
        finally:
            conn.close()
