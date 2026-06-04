from __future__ import annotations

from wm.proofs.runner import list_proof_packets
from wm.proofs.runner import run_proof_packet
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
