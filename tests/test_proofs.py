from __future__ import annotations

import json
import pytest

from wm.proofs.runner import list_proof_packets
from wm.proofs.runner import run_proof_packet
from wm.autoplay.state import AutoplayStateStore
from wm.runtime.status import collect_runtime_status
from wm.runtime.status import RuntimeProcess


def test_list_proof_packets_includes_core_live_packets():
    kinds = {packet["proof_kind"] for packet in list_proof_packets()}

    assert {"runtime_startup", "chat_action", "scene", "ambient", "memory", "content", "rollback", "failure", "living_lane"} <= kinds


def test_living_lane_packet_requires_lane_and_outcome(tmp_path):
    runtime = _live_runtime(tmp_path)
    missing = run_proof_packet(
        proof_kind="living_lane",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )
    assert missing["status"] == "failed"

    record = run_proof_packet(
        proof_kind="living_lane",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
        living_lane="rumor",
        living_outcome="cleanup",
    )
    assert record["status"] == "manual_required"
    assert record["living"] == {
        "schema_version": "wm.proof.living.v1",
        "lane": "rumor",
        "outcome": "cleanup",
    }


def test_living_lane_packet_passes_only_with_matching_scoped_audit(tmp_path):
    runtime = _live_runtime(tmp_path)
    state = tmp_path / ".wm-bootstrap" / "state" / "living" / "5408.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"audit": [{"at": "2026-01-01T00:06:00Z", "lane": "rumor", "operation": "trigger", "status": "active"}]}), encoding="utf-8")
    record = run_proof_packet(
        proof_kind="living_lane",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
        living_lane="rumor",
        living_outcome="success",
        target_provenance={"source": "marker", "player_guid": 5408, "marker_spell_id": 946602, "bridge_event_id": 11, "selected_at": "2026-01-01T00:05:00Z"},
    )
    assert record["server_status"] == "passed"
    assert record["status"] == "manual_required"
    assert record["client_status"] == "pending"
    assert record["player_visible_verified"] is False
    assert record["evidence_checks"][0]["status"] == "PASS"


def test_living_lane_packet_accepts_suppression_and_revocation_outcomes(tmp_path):
    runtime = _live_runtime(tmp_path)
    state = tmp_path / ".wm-bootstrap" / "state" / "living" / "5408.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps(
            {
                "audit": [
                    {"at": "2026-01-01T00:06:00Z", "lane": "rumor", "operation": "suppress", "status": "suppress", "outcome": "suppression"},
                    {"at": "2026-01-01T00:07:00Z", "lane": "oath", "operation": "revoke", "status": "revoke", "outcome": "revocation"},
                ]
            }
        ),
        encoding="utf-8",
    )

    suppression = run_proof_packet(
        proof_kind="living_lane",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
        living_lane="rumor",
        living_outcome="suppression",
        target_provenance={"source": "marker", "player_guid": 5408, "marker_spell_id": 946602, "bridge_event_id": 12, "selected_at": "2026-01-01T00:05:00Z"},
    )
    revocation = run_proof_packet(
        proof_kind="living_lane",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
        living_lane="oath",
        living_outcome="revocation",
        target_provenance={"source": "marker", "player_guid": 5408, "marker_spell_id": 946602, "bridge_event_id": 13, "selected_at": "2026-01-01T00:05:00Z"},
    )

    assert suppression["status"] == "passed"
    assert revocation["status"] == "passed"


def test_runtime_startup_packet_passes_when_required_services_running(tmp_path):
    processes = [
        RuntimeProcess(pid=1, parent_pid=None, name="mysqld.exe", command_line=""),
        RuntimeProcess(pid=2, parent_pid=None, name="mysqld.exe", command_line=""),
        RuntimeProcess(pid=3, parent_pid=None, name="authserver.exe", command_line=""),
        RuntimeProcess(pid=4, parent_pid=None, name="worldserver.exe", command_line=""),
        RuntimeProcess(pid=5, parent_pid=None, name="python.exe", command_line="python -m wm.events.watch --adapter native_bridge"),
        RuntimeProcess(pid=6, parent_pid=None, name="python.exe", command_line="python -m wm.panel serve"),
        RuntimeProcess(pid=7, parent_pid=None, name="python.exe", command_line="python -m wm.autoplay run"),
    ]
    runtime = collect_runtime_status(
        project_root=tmp_path,
        processes=processes,
        autoplay_status={"running": True, "status": "running"},
    )

    record = run_proof_packet(
        proof_kind="runtime_startup",
        project_root=tmp_path,
        runtime_status=runtime,
        mode="dry-run",
    )

    assert record["status"] == "passed"
    assert not record["blockers"]
    assert {check["status"] for check in record["checks"]} == {"PASS"}


def test_chat_action_packet_requires_player_and_live_services(tmp_path):
    runtime = collect_runtime_status(project_root=tmp_path, processes=[], autoplay_status={})

    record = run_proof_packet(
        proof_kind="chat_action",
        project_root=tmp_path,
        runtime_status=runtime,
        mode="dry-run",
    )

    assert record["status"] == "failed"
    assert any("player_guid" in blocker for blocker in record["blockers"])
    assert any(check["name"] == "service:autoplay" for check in record["checks"])
    assert any("Start autoplay" in action for action in record["next_actions"])
    assert record["timeline_refs"]["timeline_url"] == "/api/wm/timeline"


def test_manual_packet_records_manual_required_when_prereqs_pass(tmp_path):
    processes = [
        RuntimeProcess(pid=3, parent_pid=None, name="authserver.exe", command_line=""),
        RuntimeProcess(pid=4, parent_pid=None, name="worldserver.exe", command_line=""),
        RuntimeProcess(pid=5, parent_pid=None, name="python.exe", command_line="python -m wm.events.watch --adapter native_bridge"),
        RuntimeProcess(pid=6, parent_pid=None, name="python.exe", command_line="python -m wm.autoplay run"),
        RuntimeProcess(pid=7, parent_pid=None, name="mysqld.exe", command_line=""),
        RuntimeProcess(pid=8, parent_pid=None, name="mysqld.exe", command_line=""),
    ]
    runtime = collect_runtime_status(
        project_root=tmp_path,
        processes=processes,
        autoplay_status={"running": True, "status": "running"},
    )

    record = run_proof_packet(
        proof_kind="ambient",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["status"] == "manual_required"
    assert record["acceptance"]
    assert any(check["name"] == "journal:ambient_narration" and check["status"] == "PENDING" for check in record["evidence_checks"])


def test_proof_packet_records_manual_evidence(tmp_path):
    runtime = collect_runtime_status(project_root=tmp_path, processes=[], autoplay_status={})

    record = run_proof_packet(
        proof_kind="failure",
        project_root=tmp_path,
        runtime_status=runtime,
        manual_evidence=["SOAP disabled for failure proof"],
    )

    assert record["manual_evidence"] == ["SOAP disabled for failure proof"]
    assert record["evidence"] == ["SOAP disabled for failure proof"]


def test_proof_packet_records_marker_target_and_uses_selection_freshness(tmp_path):
    runtime = _live_runtime(tmp_path, started_at="2026-01-01T00:00:00Z")

    record = run_proof_packet(
        proof_kind="ambient",
        project_root=tmp_path,
        player_guid=5411,
        runtime_status=runtime,
        target_provenance={
            "source": "marker",
            "player_guid": 5411,
            "player_name": "MarkerUser",
            "marker_spell_id": 946602,
            "bridge_event_id": 77,
            "selected_at": "2026-01-01T00:05:00Z",
        },
    )

    assert record["target_provenance"]["schema_version"] == "wm.proof.target.v1"
    assert record["target_provenance"]["bridge_event_id"] == 77
    assert record["evidence_window"] == {
        "since": "2026-01-01T00:05:00Z",
        "basis": "latest_runtime_or_target_selection",
    }


def test_proof_packet_rejects_incomplete_or_noncanonical_target_provenance(tmp_path):
    runtime = _live_runtime(tmp_path)
    base = {
        "source": "marker",
        "player_guid": 5411,
        "marker_spell_id": 946602,
        "bridge_event_id": 77,
        "selected_at": "2026-01-01T00:05:00Z",
    }

    for bad in (
        {**base, "source": "manual"},
        {**base, "marker_spell_id": 946500},
        {**base, "bridge_event_id": None},
        {**base, "selected_at": ""},
    ):
        with pytest.raises(ValueError):
            run_proof_packet(
                proof_kind="ambient",
                project_root=tmp_path,
                player_guid=5411,
                runtime_status=runtime,
                target_provenance=bad,
            )


def test_ambient_packet_passes_with_journal_evidence(tmp_path):
    runtime = _live_runtime(tmp_path)
    store = AutoplayStateStore(tmp_path / ".wm-bootstrap" / "state" / "autoplay")
    entry = store.append_journal(
        "ambient_narration",
        {"player_guid": 5408, "kind": "area_entry", "ok": True, "line": "The air changes."},
    )
    store.append_journal(
        "ambient_suppressed",
        {"player_guid": 5408, "reason": "cooldown_active", "source_event_key": "area-2"},
    )

    record = run_proof_packet(
        proof_kind="ambient",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert entry["kind"] == "ambient_narration"
    assert entry["payload_kind"] == "area_entry"
    assert record["server_status"] == "passed"
    assert record["status"] == "manual_required"
    assert {ref["kind"] for ref in record["evidence_refs"]} >= {"ambient_narration", "ambient_suppressed"}


def test_chat_action_packet_passes_with_chat_deed_and_verification(tmp_path):
    runtime = _live_runtime(tmp_path)
    store = AutoplayStateStore(tmp_path / ".wm-bootstrap" / "state" / "autoplay")
    store.append_journal("chat", {"player_guid": 5408, "message": "heal me", "reply": {"message": "As you ask."}})
    store.append_journal("deed", {
        "player_guid": 5408,
        "verb": "player_restore_health_power",
        "verification": {
            "schema_version": "wm.autoplay.verification.v1",
            "verb": "player_restore_health_power",
            "status": "verified",
            "ok": True,
        },
    })

    record = run_proof_packet(
        proof_kind="chat_action",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["server_status"] == "passed"
    assert record["status"] == "manual_required"
    assert {check["name"]: check["status"] for check in record["evidence_checks"]} == {
        "journal:chat": "PASS",
        "journal:intent_or_deed": "PASS",
        "verification:latest": "PASS",
    }


def test_chat_action_packet_ignores_evidence_before_runtime_window(tmp_path):
    runtime = _live_runtime(tmp_path, started_at="2026-01-02T00:00:00Z")
    store = AutoplayStateStore(tmp_path / ".wm-bootstrap" / "state" / "autoplay")
    store.append_journal("chat", {"at": "2026-01-01T23:59:00Z", "player_guid": 5408, "message": "heal me"})
    store.append_journal("deed", {
        "at": "2026-01-01T23:59:30Z",
        "player_guid": 5408,
        "verb": "player_restore_health_power",
        "verification": {"status": "verified", "ok": True},
    })

    record = run_proof_packet(
        proof_kind="chat_action",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["status"] == "manual_required"
    assert record["evidence_window"]["since"] == "2026-01-02T00:00:00Z"
    assert {check["name"]: check["status"] for check in record["evidence_checks"]} == {
        "journal:chat": "PENDING",
        "journal:intent_or_deed": "PENDING",
        "verification:latest": "PENDING",
    }

    store.append_journal("chat", {"at": "2026-01-02T00:00:01Z", "player_guid": 5408, "message": "heal me"})
    store.append_journal("deed", {
        "at": "2026-01-02T00:00:02Z",
        "player_guid": 5408,
        "verb": "player_restore_health_power",
        "verification": {"status": "verified", "ok": True},
    })

    record = run_proof_packet(
        proof_kind="chat_action",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["server_status"] == "passed"
    assert record["status"] == "manual_required"


def test_chat_action_packet_requires_freshness_window_before_accepting_evidence(tmp_path):
    runtime = _live_runtime(tmp_path, started_at=None)
    store = AutoplayStateStore(tmp_path / ".wm-bootstrap" / "state" / "autoplay")
    store.append_journal("chat", {"player_guid": 5408, "message": "heal me"})
    store.append_journal("deed", {
        "player_guid": 5408,
        "verb": "player_restore_health_power",
        "verification": {"status": "verified", "ok": True},
    })

    record = run_proof_packet(
        proof_kind="chat_action",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["status"] == "manual_required"
    assert record["evidence_window"]["since"] is None
    assert record["evidence_window"]["basis"] == "unavailable"
    assert all(check["status"] == "PENDING" for check in record["evidence_checks"])
    assert all("Fresh evidence window is unavailable" in check["detail"] for check in record["evidence_checks"])


def test_memory_packet_waits_for_later_chat_turn(tmp_path):
    runtime = _live_runtime(tmp_path)
    store = AutoplayStateStore(tmp_path / ".wm-bootstrap" / "state" / "autoplay")
    store.append_journal("conversation_memory", {
        "at": "2026-01-01T00:00:00Z",
        "player_guid": 5408,
        "ok": True,
        "note": {"summary": "call player Ash"},
    })

    record = run_proof_packet(
        proof_kind="memory",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["status"] == "manual_required"
    assert any(check["name"] == "journal:later_chat" and check["status"] == "PENDING" for check in record["evidence_checks"])

    store.append_journal("chat", {
        "at": "2026-01-01T00:01:00Z",
        "player_guid": 5408,
        "message": "what now?",
        "reply": {"message": "Ash, follow the road."},
    })
    record = run_proof_packet(
        proof_kind="memory",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["server_status"] == "passed"
    assert record["status"] == "manual_required"


def test_memory_packet_compares_later_chat_timestamps_by_instant(tmp_path):
    runtime = _live_runtime(tmp_path, started_at="2025-12-31T21:00:00Z")
    store = AutoplayStateStore(tmp_path / ".wm-bootstrap" / "state" / "autoplay")
    store.append_journal("conversation_memory", {
        "at": "2026-01-01T01:00:00+03:00",
        "player_guid": 5408,
        "ok": True,
        "note": {"summary": "call player Ash"},
    })
    store.append_journal("chat", {
        "at": "2025-12-31T22:30:00Z",
        "player_guid": 5408,
        "message": "what now?",
        "reply": {"message": "Ash, follow the road."},
    })

    record = run_proof_packet(
        proof_kind="memory",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["server_status"] == "passed"
    assert record["status"] == "manual_required"


def test_scene_packet_passes_with_cleanup_evidence(tmp_path):
    runtime = _live_runtime(tmp_path)
    store = AutoplayStateStore(tmp_path / ".wm-bootstrap" / "state" / "autoplay")
    store.append_journal("scene_run", {
        "player_guid": 5408,
        "scene_name": "Greeting",
        "steps_total": 2,
        "steps_executed": 2,
        "ok": True,
        "cleanup_status": {"status": "temporary_spawn", "spawn_count": 1, "temporary_spawn_count": 1, "despawn_step_count": 0},
    })

    record = run_proof_packet(
        proof_kind="scene",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert record["server_status"] == "passed"
    assert record["status"] == "manual_required"
    assert any(check["name"] == "scene:cleanup" and check["status"] == "PASS" for check in record["evidence_checks"])


def _live_runtime(tmp_path, *, started_at: str | None = "2026-01-01T00:00:00Z"):
    processes = [
        RuntimeProcess(pid=1, parent_pid=None, name="mysqld.exe", command_line="", started_at=started_at),
        RuntimeProcess(pid=2, parent_pid=None, name="mysqld.exe", command_line="", started_at=started_at),
        RuntimeProcess(pid=3, parent_pid=None, name="authserver.exe", command_line="", started_at=started_at),
        RuntimeProcess(pid=4, parent_pid=None, name="worldserver.exe", command_line="", started_at=started_at),
        RuntimeProcess(pid=5, parent_pid=None, name="python.exe", command_line="python -m wm.events.watch --adapter native_bridge", started_at=started_at),
        RuntimeProcess(pid=6, parent_pid=None, name="python.exe", command_line="python -m wm.panel serve", started_at=started_at),
        RuntimeProcess(pid=7, parent_pid=None, name="python.exe", command_line="python -m wm.autoplay run", started_at=started_at),
    ]
    return collect_runtime_status(
        project_root=tmp_path,
        processes=processes,
        autoplay_status={"running": True, "status": "running"},
    )
