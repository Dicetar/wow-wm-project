"""Decision context assembler (Phase 6.2).

A pure function that composes the pieces the live service already fetches
(chat world context, session context pack, recent events, an optional journal
summary) into one bounded, token-aware packet: "what is going on with this
character right now." The decider (6.4) and candidate builder (6.3) read only
this packet, so the autonomy loop has a single, deterministic input.

Kept pure on purpose: the caller supplies the already-built pieces, so this is
trivially testable and never touches the DB itself.
"""

from __future__ import annotations

from typing import Any

_SCHEMA_VERSION = "wm.autonomy.decision_context.v1"

_RECENT_EVENTS_CAP = 8
_ARCS_CAP = 6
_UNLOCKS_CAP = 12
_STEERING_CAP = 8
_JOURNAL_SUMMARY_CHARS = 600


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _compact_event(event: Any) -> dict[str, Any]:
    e = _as_dict(event)
    return {
        "type": e.get("event_type"),
        "subject_type": e.get("subject_type"),
        "subject_entry": e.get("subject_entry"),
        "value": e.get("event_value"),
        "at": e.get("occurred_at"),
    }


def build_decision_context(
    *,
    player_guid: int,
    world_context: dict[str, Any] | None = None,
    session_context_pack: dict[str, Any] | None = None,
    recent_events: list[Any] | None = None,
    journal_summary: str | None = None,
) -> dict[str, Any]:
    """Compose a bounded decision-context packet for one character."""
    wc = _as_dict(world_context)
    pack = _as_dict(session_context_pack)

    live = _as_dict(wc.get("live_location"))
    perception = _as_dict(wc.get("perception"))
    speaker = _as_dict(wc.get("speaker"))

    location = {
        "zone_id": live.get("zone_id"),
        "area_id": live.get("area_id"),
        "zone_name": live.get("zone_name"),
        "area_name": live.get("area_name"),
        "fresh": bool(live.get("fresh")),
        "in_combat": bool(live.get("in_combat")),
    }
    nearby = {
        "creatures": perception.get("creature_count"),
        "objects": perception.get("gameobject_count"),
    }

    character_state = {
        "profile": pack.get("profile"),
        "arc_states": _as_list(pack.get("arc_states"))[:_ARCS_CAP],
        "unlocks": _as_list(pack.get("unlocks"))[:_UNLOCKS_CAP],
        "steering": _as_list(pack.get("conversation_steering"))[:_STEERING_CAP],
    }

    events = [_compact_event(e.to_dict() if hasattr(e, "to_dict") else e) for e in _as_list(recent_events)]
    events = events[:_RECENT_EVENTS_CAP]

    summary = str(journal_summary or "").strip()[:_JOURNAL_SUMMARY_CHARS] or None

    return {
        "schema_version": _SCHEMA_VERSION,
        "player_guid": int(player_guid),
        "player": {
            "name": speaker.get("name") or _as_dict(pack.get("profile")).get("character_name"),
            "level": live.get("level"),
            "online": live.get("online"),
        },
        "location": location,
        "nearby": nearby,
        "character_state": character_state,
        "recent_events": events,
        "journal_summary": summary,
    }
