from __future__ import annotations

from typing import Any


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return None


def _chat_identity_facts(context: dict[str, Any], *, player_guid: int) -> dict[str, Any]:
    speaker = context.get("speaker") if isinstance(context.get("speaker"), dict) else {}
    database = context.get("database") if isinstance(context.get("database"), dict) else {}
    character_row = database.get("character_row") if isinstance(database.get("character_row"), dict) else {}
    live = context.get("live_location") if isinstance(context.get("live_location"), dict) else {}
    live_fresh = bool(live.get("fresh"))
    name = _first_text(speaker.get("name"), character_row.get("name"))
    position = None
    if live_fresh and live.get("x") is not None and live.get("y") is not None:
        position = {"x": live.get("x"), "y": live.get("y"), "z": live.get("z"), "o": live.get("o")}
    location_source = live.get("source") if live_fresh else (
        "source_event" if speaker.get("zone_id") is not None else "stale_characters_row" if character_row else "unknown"
    )
    return {
        "player_guid": int(player_guid),
        "speaker_name": name,
        "character_name": name,
        "level": _first_text(character_row.get("level")),
        "race": _first_text(character_row.get("race")),
        "class": _first_text(character_row.get("class")),
        "online": _first_text(character_row.get("online")),
        "map": _first_text(live.get("map_id") if live_fresh else None, speaker.get("map_id"), character_row.get("map")),
        "zone": _first_text(live.get("zone_id") if live_fresh else None, speaker.get("zone_id"), character_row.get("zone")),
        "area": _first_text(live.get("area_id") if live_fresh else None, speaker.get("area_id")),
        "zone_name": _first_text(live.get("zone_name")) if live_fresh else None,
        "area_name": _first_text(live.get("area_name")) if live_fresh else None,
        "position": position,
        "location_source": location_source,
        "location_fresh": live_fresh,
        "remembered": _remembered_facts(context),
    }


def _remembered_facts(context: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    """Compact active, priority-ordered steering notes for the chat voice."""
    pack = context.get("session_context_pack") if isinstance(context.get("session_context_pack"), dict) else {}
    notes = pack.get("memory") if isinstance(pack.get("memory"), list) else pack.get("conversation_steering")
    if not isinstance(notes, list):
        return []
    facts: list[dict[str, Any]] = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        body = _first_text(note.get("body"))
        if not body or note.get("is_active") is False:
            continue
        facts.append({"kind": _first_text(note.get("steering_kind")) or "player_preference", "body": body})
    return facts[:limit]


_MEMORY_CUES = (
    "remember", "don't forget", "dont forget", "keep in mind", "note that", "for the record",
    "i prefer", "i like", "i love", "i hate", "i dislike", "i enjoy", "i fear", "afraid of",
    "call me", "my name is", "from now on", "my favorite", "my favourite", "i want you to know",
)


def _looks_like_memory_statement(message: str) -> bool:
    text = str(message).strip().lower()
    return bool(text) and any(cue in text for cue in _MEMORY_CUES)


_SCENE_CUES = (
    "stage", "scene", "summon", "orchestrate", "set up", "set the stage",
    "have it", "have them", "and then", "make a", "perform", "act out", "play out",
    "ambush", "honor guard", "escort", "ritual", "ceremony",
)


def _looks_like_scene_request(message: str) -> bool:
    text = str(message).strip().lower()
    return bool(text) and any(cue in text for cue in _SCENE_CUES)


def _voice_world_digest(context: dict[str, Any]) -> dict[str, Any]:
    """Return only the live location, ambient counts, and recent chat needed by the voice."""
    if not isinstance(context, dict):
        return {}
    live = context.get("live_location") if isinstance(context.get("live_location"), dict) else {}
    perception = context.get("perception") if isinstance(context.get("perception"), dict) else {}
    events = context.get("events") if isinstance(context.get("events"), dict) else {}
    recent_chat = events.get("recent_wm_chat") if isinstance(events.get("recent_wm_chat"), list) else []
    live_fresh = bool(live.get("fresh"))
    return {
        "live_location": {
            key: live.get(key) if live_fresh or key in {"source", "fresh"} else None
            for key in ("source", "fresh", "zone_id", "area_id", "zone_name", "area_name", "in_combat")
        },
        "perception": {
            "source": perception.get("source"),
            "fresh": perception.get("fresh"),
            "creature_count": perception.get("creature_count"),
            "gameobject_count": perception.get("gameobject_count"),
        },
        "recent_wm_chat": recent_chat[:3],
    }


def _deterministic_chat_fact_reply(message: str, *, identity: dict[str, Any]) -> str | None:
    lowered = str(message).strip().lower()
    if not lowered:
        return None
    asks_name = (
        "my name" in lowered
        or "character name" in lowered
        or lowered in {"who am i", "who am i?", "what am i called", "what am i called?"}
    )
    if asks_name and identity.get("character_name"):
        return str(identity["character_name"])
    asks_guid = "my guid" in lowered or "player guid" in lowered or "character guid" in lowered
    if asks_guid and identity.get("player_guid") is not None:
        return str(identity["player_guid"])
    return None
