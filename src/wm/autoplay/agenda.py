from __future__ import annotations

from typing import Any, Iterable


DEFAULT_AGENDA_SERVICES: tuple[str, ...] = ("db", "auth", "world", "watcher", "panel", "autoplay")


def build_session_agenda(
    *,
    autoplay_status: dict[str, Any] | None,
    runtime_status: dict[str, Any] | None,
    player_guid: int | None = None,
    required_services: Iterable[str] = DEFAULT_AGENDA_SERVICES,
) -> dict[str, Any]:
    """Build a deterministic explanation of the next autonomous WM step."""
    status = autoplay_status if isinstance(autoplay_status, dict) else {}
    runtime = runtime_status if isinstance(runtime_status, dict) else {}
    required = tuple(required_services)
    lanes = _lanes(status)
    resolved_player_guid = _int_or_none(player_guid) or _player_guid_from_status(status)

    if not runtime:
        return _agenda(
            status="blocked",
            objective="Recover WM runtime status.",
            next_action="Refresh runtime status from the launcher or panel.",
            blockers=["runtime status is unavailable"],
            lanes=lanes,
            player_guid=resolved_player_guid,
            proof_hint="runtime_startup",
        )

    if runtime.get("error"):
        return _agenda(
            status="blocked",
            objective="Recover WM runtime status.",
            next_action="Run the doctor and refresh runtime status.",
            blockers=[str(runtime.get("error"))],
            lanes=lanes,
            player_guid=resolved_player_guid,
            proof_hint="runtime_startup",
        )

    blocking_service = _first_blocking_service(runtime, required)
    if blocking_service is not None:
        service, reason, label = blocking_service
        stale = reason == "stale"
        return _agenda(
            status="blocked",
            objective="Return WM to one clean runtime instance per service.",
            next_action=(
                "Press Refresh. If stale state remains, press Stop All WM and start the stack once."
                if stale
                else "Press Stop All WM, wait for exits, then start each WM service once."
            ),
            blockers=[f"{label or service} is {reason}"],
            lanes=lanes,
            player_guid=resolved_player_guid,
            proof_hint="runtime_startup",
        )

    missing = _missing_services(runtime, required)
    if missing:
        blockers = [f"{label or service} is {state}" for service, state, label in missing]
        return _agenda(
            status="needs_runtime",
            objective="Start the full local WM stack.",
            next_action="Start Core, Watcher, Panel, and Autoplay from the launcher, then run the runtime_startup proof.",
            blockers=blockers,
            lanes=lanes,
            player_guid=resolved_player_guid,
            proof_hint="runtime_startup",
        )

    if bool(status.get("paused")):
        return _agenda(
            status="idle",
            objective="Autoplay is paused.",
            next_action="Resume Autoplay when you want WM to react again.",
            blockers=["autoplay is paused"],
            lanes=lanes,
            player_guid=resolved_player_guid,
            proof_hint="chat_action",
        )

    readiness_blockers = _readiness_blockers(status)
    if readiness_blockers:
        return _agenda(
            status="blocked",
            objective="Clear autoplay readiness blockers.",
            next_action="Run Doctor and fix the first failing readiness check.",
            blockers=readiness_blockers,
            lanes=lanes,
            player_guid=resolved_player_guid,
            proof_hint="failure",
        )

    if resolved_player_guid is None:
        return _agenda(
            status="needs_player",
            objective="Select an in-client player session.",
            next_action="Bootstrap or select the scoped player, then send a WM chat message.",
            blockers=["no active player_guid"],
            lanes=lanes,
            player_guid=None,
            proof_hint="chat_action",
        )

    return _agenda(
        status="ready",
        objective=f"Run bounded WM chat/action loop for player {resolved_player_guid}.",
        next_action="Wait for player chat or a notable sensed event, then apply only proven allowed actions.",
        blockers=[],
        lanes=lanes,
        player_guid=resolved_player_guid,
        proof_hint="chat_action",
    )


def _agenda(
    *,
    status: str,
    objective: str,
    next_action: str,
    blockers: list[str],
    lanes: list[str],
    player_guid: int | None,
    proof_hint: str,
) -> dict[str, Any]:
    return {
        "schema_version": "wm.autoplay.session_agenda.v1",
        "status": status,
        "objective": objective,
        "next_action": next_action,
        "player_guid": player_guid,
        "blockers": blockers,
        "lanes": lanes,
        "proof_hint": proof_hint,
    }


def _first_blocking_service(runtime: dict[str, Any], required: tuple[str, ...]) -> tuple[str, str, str] | None:
    services = runtime.get("services") if isinstance(runtime.get("services"), dict) else {}
    required_set = set(required)
    for incident in runtime.get("incidents") or []:
        if not isinstance(incident, dict):
            continue
        service = str(incident.get("service") or "")
        if service not in required_set:
            continue
        kind = str(incident.get("kind") or "")
        if kind == "duplicate_service":
            return service, "duplicate", _service_label(services, service)
        if kind == "stale_service_state":
            return service, "stale", _service_label(services, service)
    for service in required:
        record = services.get(service) if isinstance(services.get(service), dict) else {}
        if record.get("stale"):
            return service, "stale", str(record.get("label") or service)
        if str(record.get("state") or "") == "duplicate":
            return service, "duplicate", str(record.get("label") or service)
    return None


def _missing_services(runtime: dict[str, Any], required: tuple[str, ...]) -> list[tuple[str, str, str]]:
    services = runtime.get("services") if isinstance(runtime.get("services"), dict) else {}
    missing: list[tuple[str, str, str]] = []
    for service in required:
        record = services.get(service) if isinstance(services.get(service), dict) else {}
        state = str(record.get("state") or "unknown")
        if state != "running":
            missing.append((service, state, str(record.get("label") or service)))
    return missing


def _readiness_blockers(status: dict[str, Any]) -> list[str]:
    readiness = status.get("readiness") if isinstance(status.get("readiness"), dict) else {}
    if readiness.get("ok") is True:
        return []
    blockers: list[str] = []
    for blocker in readiness.get("blockers") or []:
        if isinstance(blocker, dict):
            label = str(blocker.get("check") or "readiness")
            detail = str(blocker.get("detail") or blocker.get("status") or "blocked")
            blockers.append(f"{label}: {detail}")
        else:
            blockers.append(str(blocker))
    return blockers


def _lanes(status: dict[str, Any]) -> list[str]:
    config = status.get("config") if isinstance(status.get("config"), dict) else {}
    raw = config.get("llm_lanes")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def _player_guid_from_status(status: dict[str, Any]) -> int | None:
    session = status.get("active_session")
    if isinstance(session, dict):
        return _int_or_none(session.get("character_guid") or session.get("player_guid"))
    return _int_or_none(session)


def _service_label(services: dict[str, Any], service: str) -> str:
    record = services.get(service) if isinstance(services.get(service), dict) else {}
    return str(record.get("label") or service)


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
