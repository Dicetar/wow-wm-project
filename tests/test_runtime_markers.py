from __future__ import annotations

from wm.runtime.markers import clear_runtime_markers
from wm.runtime.markers import load_runtime_markers
from wm.runtime.markers import mark_runtime_service_stopped
from wm.runtime.markers import write_runtime_marker


def test_runtime_marker_write_load_and_stale_detection(tmp_path):
    root = tmp_path / "runtime"

    marker = write_runtime_marker(
        service="watcher",
        command_key="wm.events.watch:native_bridge:apply",
        root=root,
        pid=123,
        now="2026-01-01T00:00:00Z",
    )
    fresh = load_runtime_markers(root=root, now="2026-01-01T00:00:20Z", stale_after_seconds=30)
    stale = load_runtime_markers(root=root, now="2026-01-01T00:00:31Z", stale_after_seconds=30)

    assert marker["schema_version"] == "wm.runtime.marker.v1"
    assert fresh[0]["active"] is True
    assert fresh[0]["stale"] is False
    assert stale[0]["active"] is False
    assert stale[0]["stale"] is True


def test_runtime_marker_stopped_and_clear(tmp_path):
    root = tmp_path / "runtime"
    write_runtime_marker(
        service="autoplay",
        command_key="wm.autoplay run",
        root=root,
        pid=201,
        now="2026-01-01T00:00:00Z",
    )
    mark_runtime_service_stopped(
        service="autoplay",
        command_key="wm.autoplay run",
        root=root,
        pid=201,
        now="2026-01-01T00:00:05Z",
    )

    markers = load_runtime_markers(root=root, now="2026-01-01T00:05:00Z", stale_after_seconds=30)

    assert markers[0]["health"] == "stopped"
    assert markers[0]["active"] is False
    assert markers[0]["stale"] is False
    assert clear_runtime_markers(root=root, services=["autoplay"]) == 1
    assert load_runtime_markers(root=root) == []
