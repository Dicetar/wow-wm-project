from __future__ import annotations

from wm.proofs.runner import list_proof_packets
from wm.proofs.runner import run_proof_packet
from wm.autoplay.state import AutoplayStateStore
from wm.runtime.status import collect_runtime_status
from wm.runtime.status import RuntimeProcess


def test_list_proof_packets_includes_core_live_packets():
    kinds = {packet["proof_kind"] for packet in list_proof_packets()}

    assert {"runtime_startup", "chat_action", "scene", "ambient", "memory", "content", "rollback", "failure"} <= kinds


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


def test_ambient_packet_passes_with_journal_evidence(tmp_path):
    runtime = _live_runtime(tmp_path)
    store = AutoplayStateStore(tmp_path / ".wm-bootstrap" / "state" / "autoplay")
    entry = store.append_journal(
        "ambient_narration",
        {"player_guid": 5408, "kind": "area_entry", "ok": True, "line": "The air changes."},
    )

    record = run_proof_packet(
        proof_kind="ambient",
        project_root=tmp_path,
        player_guid=5408,
        runtime_status=runtime,
    )

    assert entry["kind"] == "ambient_narration"
    assert entry["payload_kind"] == "area_entry"
    assert record["status"] == "passed"
    assert record["evidence_refs"][0]["kind"] == "ambient_narration"


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

    assert record["status"] == "passed"
    assert {check["name"]: check["status"] for check in record["evidence_checks"]} == {
        "journal:chat": "PASS",
        "journal:intent_or_deed": "PASS",
        "verification:latest": "PASS",
    }


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

    assert record["status"] == "passed"


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

    assert record["status"] == "passed"
    assert any(check["name"] == "scene:cleanup" and check["status"] == "PASS" for check in record["evidence_checks"])


def _live_runtime(tmp_path):
    processes = [
        RuntimeProcess(pid=1, parent_pid=None, name="mysqld.exe", command_line=""),
        RuntimeProcess(pid=2, parent_pid=None, name="mysqld.exe", command_line=""),
        RuntimeProcess(pid=3, parent_pid=None, name="authserver.exe", command_line=""),
        RuntimeProcess(pid=4, parent_pid=None, name="worldserver.exe", command_line=""),
        RuntimeProcess(pid=5, parent_pid=None, name="python.exe", command_line="python -m wm.events.watch --adapter native_bridge"),
        RuntimeProcess(pid=6, parent_pid=None, name="python.exe", command_line="python -m wm.panel serve"),
        RuntimeProcess(pid=7, parent_pid=None, name="python.exe", command_line="python -m wm.autoplay run"),
    ]
    return collect_runtime_status(
        project_root=tmp_path,
        processes=processes,
        autoplay_status={"running": True, "status": "running"},
    )
