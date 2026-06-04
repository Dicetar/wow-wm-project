from __future__ import annotations

from typing import Any

from wm.autoplay.agenda import DEFAULT_AGENDA_SERVICES
from wm.autoplay.agenda import build_session_agenda


def _autoplay_status(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "running",
        "running": True,
        "paused": False,
        "active_session": None,
        "readiness": {"ok": True, "blockers": []},
        "config": {"llm_lanes": ["chat", "scene", "action"]},
    }
    payload.update(overrides)
    return payload


def _runtime_status(**service_overrides: dict[str, Any]) -> dict[str, Any]:
    services = {
        key: {
            "service": key,
            "label": key,
            "state": "running",
            "health": "running",
            "logical_count": 1,
            "stale": False,
        }
        for key in DEFAULT_AGENDA_SERVICES
    }
    for key, updates in service_overrides.items():
        services[key].update(updates)
    incidents = []
    for key, service in services.items():
        if service.get("state") == "duplicate":
            incidents.append({
                "kind": "duplicate_service",
                "severity": "error",
                "service": key,
                "message": f"{key} duplicate",
            })
        if service.get("stale"):
            incidents.append({
                "kind": "stale_service_state",
                "severity": "warning",
                "service": key,
                "message": f"{key} stale",
            })
    return {"schema_version": "wm.runtime.status.v1", "services": services, "incidents": incidents}


def test_agenda_blocks_duplicate_runtime_service() -> None:
    agenda = build_session_agenda(
        autoplay_status=_autoplay_status(),
        runtime_status=_runtime_status(world={"state": "duplicate", "logical_count": 2}),
        player_guid=5408,
    )

    assert agenda["status"] == "blocked"
    assert agenda["proof_hint"] == "runtime_startup"
    assert "duplicate" in agenda["blockers"][0]
    assert "Stop All WM" in agenda["next_action"]


def test_agenda_blocks_stale_runtime_state() -> None:
    agenda = build_session_agenda(
        autoplay_status=_autoplay_status(),
        runtime_status=_runtime_status(autoplay={"stale": True, "health": "stale"}),
        player_guid=5408,
    )

    assert agenda["status"] == "blocked"
    assert "stale" in agenda["blockers"][0]
    assert "Refresh" in agenda["next_action"]


def test_agenda_reports_missing_runtime_services() -> None:
    agenda = build_session_agenda(
        autoplay_status=_autoplay_status(),
        runtime_status=_runtime_status(watcher={"state": "not_running", "health": "not_running", "logical_count": 0}),
        player_guid=5408,
    )

    assert agenda["status"] == "needs_runtime"
    assert agenda["proof_hint"] == "runtime_startup"
    assert agenda["blockers"] == ["watcher is not_running"]


def test_agenda_paused_before_player_selection() -> None:
    agenda = build_session_agenda(
        autoplay_status=_autoplay_status(paused=True),
        runtime_status=_runtime_status(),
        player_guid=None,
    )

    assert agenda["status"] == "idle"
    assert agenda["proof_hint"] == "chat_action"
    assert agenda["player_guid"] is None


def test_agenda_needs_player_when_runtime_ready() -> None:
    agenda = build_session_agenda(
        autoplay_status=_autoplay_status(),
        runtime_status=_runtime_status(),
        player_guid=None,
    )

    assert agenda["status"] == "needs_player"
    assert agenda["blockers"] == ["no active player_guid"]


def test_agenda_ready_for_scoped_player() -> None:
    agenda = build_session_agenda(
        autoplay_status=_autoplay_status(active_session={"character_guid": 5408}),
        runtime_status=_runtime_status(),
        player_guid=None,
    )

    assert agenda["status"] == "ready"
    assert agenda["player_guid"] == 5408
    assert agenda["lanes"] == ["chat", "scene", "action"]


def test_agenda_reports_readiness_blocker() -> None:
    agenda = build_session_agenda(
        autoplay_status=_autoplay_status(readiness={"ok": False, "blockers": [{"check": "soap", "detail": "refused"}]}),
        runtime_status=_runtime_status(),
        player_guid=5408,
    )

    assert agenda["status"] == "blocked"
    assert agenda["proof_hint"] == "failure"
    assert agenda["blockers"] == ["soap: refused"]
