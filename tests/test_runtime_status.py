from __future__ import annotations

from wm.runtime.status import RuntimeProcess
from wm.runtime.status import collect_runtime_status


def test_runtime_status_collapses_parent_child_pairs(tmp_path):
    processes = [
        RuntimeProcess(
            pid=10,
            parent_pid=1,
            name="python.exe",
            command_line="python -m wm.events.watch --adapter native_bridge",
        ),
        RuntimeProcess(
            pid=11,
            parent_pid=10,
            name="python.exe",
            command_line="python -m wm.events.watch --adapter native_bridge",
        ),
    ]

    status = collect_runtime_status(project_root=tmp_path, processes=processes, autoplay_status={})

    watcher = status["services"]["watcher"]
    assert watcher["logical_count"] == 1
    assert watcher["process_count"] == 2
    assert watcher["pid_tree"] == [{"pid": 10, "child_pids": [11], "name": "python.exe", "started_at": None}]
    assert watcher["state"] == "running"


def test_runtime_status_detects_auth_world_by_process_name_when_commandline_empty(tmp_path):
    processes = [
        RuntimeProcess(pid=20, parent_pid=1, name="authserver.exe", command_line=""),
        RuntimeProcess(pid=21, parent_pid=1, name="worldserver.exe", command_line=""),
    ]

    status = collect_runtime_status(project_root=tmp_path, processes=processes, autoplay_status={})

    assert status["services"]["auth"]["state"] == "running"
    assert status["services"]["world"]["state"] == "running"


def test_runtime_status_detects_visible_console_titles(tmp_path):
    processes = [
        RuntimeProcess(pid=25, parent_pid=None, name="cmd.exe", command_line="", window_title="WM Autoplay"),
    ]

    status = collect_runtime_status(project_root=tmp_path, processes=processes, autoplay_status={"running": True, "status": "running"})

    assert status["services"]["autoplay"]["state"] == "running"
    assert status["services"]["autoplay"]["stale"] is False


def test_runtime_status_collapses_limited_mysql_pair(tmp_path):
    processes = [
        RuntimeProcess(pid=40, parent_pid=None, name="mysqld.exe", command_line=""),
        RuntimeProcess(pid=41, parent_pid=None, name="mysqld.exe", command_line=""),
    ]

    status = collect_runtime_status(project_root=tmp_path, processes=processes, autoplay_status={})

    db = status["services"]["db"]
    assert db["state"] == "running"
    assert db["logical_count"] == 1
    assert db["pid_tree"][0]["child_pids"] == [41]


def test_runtime_status_marks_duplicate_logical_roots(tmp_path):
    processes = [
        RuntimeProcess(pid=30, parent_pid=1, name="python.exe", command_line="python -m wm.panel serve"),
        RuntimeProcess(pid=31, parent_pid=1, name="python.exe", command_line="python -m wm.panel serve"),
    ]

    status = collect_runtime_status(project_root=tmp_path, processes=processes, autoplay_status={})

    panel = status["services"]["panel"]
    assert panel["state"] == "duplicate"
    assert panel["logical_count"] == 2
    assert any(item["kind"] == "duplicate_service" and item["service"] == "panel" for item in status["incidents"])
    assert status["ok"] is False


def test_runtime_status_marks_stale_autoplay_durable_state(tmp_path):
    status = collect_runtime_status(
        project_root=tmp_path,
        processes=[],
        autoplay_status={"status": "running", "running": True, "paused": False},
    )

    autoplay = status["services"]["autoplay"]
    assert autoplay["stale"] is True
    assert autoplay["health"] == "stale"
    assert any(item["kind"] == "stale_service_state" for item in status["incidents"])


def test_runtime_status_does_not_mark_stopping_autoplay_without_process_stale(tmp_path):
    status = collect_runtime_status(
        project_root=tmp_path,
        processes=[],
        autoplay_status={"status": "stopping", "running": False, "paused": False},
    )

    autoplay = status["services"]["autoplay"]
    assert autoplay["stale"] is False
    assert autoplay["health"] == "not_running"
    assert not any(item["kind"] == "stale_service_state" for item in status["incidents"])
