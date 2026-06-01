from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from wm.config import Settings
from wm.context.pack import build_session_context_pack
from wm.db.mysql_cli import MysqlCliClient
from wm.db.mysql_cli import MysqlCliError
from wm.events.store import EventStore


def build_chat_world_context(
    *,
    settings: Settings,
    player_guid: int,
    message: str,
    source_event: dict[str, Any] | None = None,
    recent_event_limit: int = 20,
) -> dict[str, Any]:
    """Build a bounded, read-only world snapshot for direct WM chat.

    This intentionally exposes curated DB facts instead of arbitrary SQL. The LLM
    can see who spoke, current character facts, recent world events, recent WM
    chat, native queue state, and the existing session context pack, while
    mutation remains constrained to typed WM proposals/actions.
    """

    client = MysqlCliClient()
    notes: list[str] = []
    event_payload = dict(source_event or {})
    speaker_guid = int(player_guid)
    speaker_name = _speaker_name(event_payload)

    char_row = _first_or_none(_query_char(
        client=client,
        settings=settings,
        sql=(
            "SELECT guid, account, name, race, class, gender, level, xp, money, map, zone, "
            "position_x, position_y, position_z, online, at_login, logout_time "
            "FROM characters "
            f"WHERE guid = {speaker_guid} LIMIT 1"
        ),
        notes=notes,
        label="character_row",
    ))
    if char_row and not speaker_name:
        speaker_name = _str_or_none(char_row.get("name"))

    context_pack: dict[str, Any] | None = None
    try:
        context_pack = build_session_context_pack(player_guid=speaker_guid)
    except Exception as exc:
        notes.append(f"session_context_pack: {type(exc).__name__}: {exc}")

    recent_player_events: list[dict[str, Any]] = []
    recent_global_events: list[dict[str, Any]] = []
    try:
        store = EventStore(client=client, settings=settings)
        recent_player_events = [
            _compact_event(event.to_dict())
            for event in store.list_recent_events(
                event_class="observed",
                player_guid=speaker_guid,
                limit=recent_event_limit,
                newest_first=True,
            )
        ]
        recent_global_events = [
            _compact_event(event.to_dict())
            for event in store.list_recent_events(
                event_class="observed",
                limit=recent_event_limit,
                newest_first=True,
            )
        ]
    except Exception as exc:
        notes.append(f"events: {type(exc).__name__}: {exc}")

    recent_chat = [
        event
        for event in recent_global_events
        if str(event.get("event_type") or "") == "wm_chat"
    ][:10]

    online_characters = _query_char(
        client=client,
        settings=settings,
        sql=(
            "SELECT guid, account, name, race, class, level, map, zone, online "
            "FROM characters "
            "WHERE online > 0 "
            "ORDER BY name LIMIT 25"
        ),
        notes=notes,
        label="online_characters",
    )
    active_quests = _query_char(
        client=client,
        settings=settings,
        sql=(
            "SELECT quest, status, explored, timer, mobcount1, mobcount2, mobcount3, mobcount4, "
            "itemcount1, itemcount2, itemcount3, itemcount4 "
            "FROM character_queststatus "
            f"WHERE guid = {speaker_guid} "
            "ORDER BY quest DESC LIMIT 25"
        ),
        notes=notes,
        label="active_quests",
    )
    recent_native_actions = _query_world(
        client=client,
        settings=settings,
        sql=(
            "SELECT RequestID, CreatedAt, ProcessedAt, PlayerGUID, ActionKind, Status, ErrorText, "
            "RiskLevel, CreatedBy, PayloadJSON, ResultJSON "
            "FROM wm_bridge_action_request "
            f"WHERE PlayerGUID = {speaker_guid} "
            "ORDER BY RequestID DESC LIMIT 15"
        ),
        notes=notes,
        label="recent_native_actions",
    )
    # The `characters` DB row only stores position at save points (logout /
    # periodic save), so it is stale for a moving online player. The bridge
    # heartbeats live state into wm_bridge_player_presence every few seconds,
    # so a single read of that row gives the always-fresh live location.
    presence_row = _first_or_none(_query_world(
        client=client,
        settings=settings,
        sql=(
            "SELECT PlayerGUID, AccountID, Online, MapID, ZoneID, AreaID, ZoneName, AreaName, "
            "PosX, PosY, PosZ, Orientation, Level, HealthPct, InCombat, UpdatedAt "
            "FROM wm_bridge_player_presence "
            f"WHERE PlayerGUID = {speaker_guid} LIMIT 1"
        ),
        notes=notes,
        label="player_presence",
    ))
    # Ambient perception: the bridge heartbeats nearby creatures/objects around
    # each scoped player into wm_bridge_player_perception, so chat stays aware of
    # the surroundings without an on-demand snapshot round-trip.
    perception_row = _first_or_none(_query_world(
        client=client,
        settings=settings,
        sql=(
            "SELECT PlayerGUID, MapID, ZoneID, AreaID, CreatureCount, GameObjectCount, PayloadJSON, UpdatedAt "
            "FROM wm_bridge_player_perception "
            f"WHERE PlayerGUID = {speaker_guid} LIMIT 1"
        ),
        notes=notes,
        label="player_perception",
    ))
    latest_native_snapshot = _first_or_none(_query_world(
        client=client,
        settings=settings,
        sql=(
            "SELECT SnapshotID, RequestID, OccurredAt, PlayerGUID, ContextKind, Radius, MapID, ZoneID, AreaID, Source, PayloadJSON "
            "FROM wm_bridge_context_snapshot "
            f"WHERE PlayerGUID = {speaker_guid} "
            "ORDER BY SnapshotID DESC LIMIT 1"
        ),
        notes=notes,
        label="latest_native_snapshot",
    ))

    return {
        "schema_version": "wm.autoplay.chat_world_context.v1",
        "speaker": {
            "guid": speaker_guid,
            "name": speaker_name,
            "message": str(message)[:1000],
            "source_event_key": event_payload.get("source_event_key"),
            "source": event_payload.get("source"),
            "map_id": event_payload.get("map_id"),
            "zone_id": event_payload.get("zone_id"),
            "area_id": event_payload.get("area_id"),
        },
        "source_event": _compact_event(event_payload) if event_payload else None,
        "live_location": _live_location_from_presence(presence_row),
        "perception": _perception_from_row(perception_row),
        "database": {
            # position_x/y/z are dropped: they reflect the last character save, not
            # the live position. Live coordinates are exposed via `live_location`.
            "character_row": _without_keys(_json_clean(char_row), ("position_x", "position_y", "position_z")),
            "online_characters": [_json_clean(row) for row in online_characters],
            "active_quests": [_json_clean(row) for row in active_quests],
        },
        "events": {
            "recent_for_speaker": recent_player_events,
            "recent_global": recent_global_events,
            "recent_wm_chat": recent_chat,
        },
        "native_bridge": {
            "recent_actions": [_json_clean(row) for row in recent_native_actions],
            "latest_context_snapshot": _parse_snapshot(latest_native_snapshot),
        },
        "session_context_pack": _compact_session_context(context_pack),
        "notes": notes,
    }


def _query_char(
    *,
    client: MysqlCliClient,
    settings: Settings,
    sql: str,
    notes: list[str],
    label: str,
) -> list[dict[str, Any]]:
    try:
        return client.query(
            host=settings.char_db_host,
            port=settings.char_db_port,
            user=settings.char_db_user,
            password=settings.char_db_password,
            database=settings.char_db_name,
            sql=sql,
        )
    except MysqlCliError as exc:
        notes.append(f"{label}: {str(exc).splitlines()[-1] if str(exc) else type(exc).__name__}")
    except Exception as exc:
        notes.append(f"{label}: {type(exc).__name__}: {exc}")
    return []


def _query_world(
    *,
    client: MysqlCliClient,
    settings: Settings,
    sql: str,
    notes: list[str],
    label: str,
) -> list[dict[str, Any]]:
    try:
        return client.query(
            host=settings.world_db_host,
            port=settings.world_db_port,
            user=settings.world_db_user,
            password=settings.world_db_password,
            database=settings.world_db_name,
            sql=sql,
        )
    except MysqlCliError as exc:
        notes.append(f"{label}: {str(exc).splitlines()[-1] if str(exc) else type(exc).__name__}")
    except Exception as exc:
        notes.append(f"{label}: {type(exc).__name__}: {exc}")
    return []


def _speaker_name(event_payload: dict[str, Any]) -> str | None:
    metadata = event_payload.get("metadata") if isinstance(event_payload.get("metadata"), dict) else {}
    payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
    for value in (
        event_payload.get("player_name"),
        metadata.get("player_name"),
        payload.get("player_name"),
        event_payload.get("character_name"),
    ):
        text = _str_or_none(value)
        if text:
            return text
    return None


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
    return {
        key: _json_clean(value)
        for key, value in {
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "source": event.get("source"),
            "source_event_key": event.get("source_event_key"),
            "occurred_at": event.get("occurred_at"),
            "player_guid": event.get("player_guid"),
            "player_name": _speaker_name(event),
            "subject_type": event.get("subject_type"),
            "subject_entry": event.get("subject_entry"),
            "event_value": event.get("event_value"),
            "map_id": event.get("map_id"),
            "zone_id": event.get("zone_id"),
            "area_id": event.get("area_id"),
            "payload": payload,
        }.items()
        if value not in (None, "", [], {})
    }


def _parse_snapshot(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    parsed = dict(row)
    parsed["PayloadJSON"] = _parse_json(parsed.get("PayloadJSON"))
    return _json_clean(parsed)


def _compact_session_context(context_pack: dict[str, Any] | None) -> dict[str, Any] | None:
    if not context_pack:
        return None
    character_state = context_pack.get("character_state") if isinstance(context_pack.get("character_state"), dict) else {}
    generation_input = context_pack.get("generation_input") if isinstance(context_pack.get("generation_input"), dict) else {}
    return _json_clean({
        "schema_version": context_pack.get("schema_version"),
        "status": context_pack.get("status"),
        "player_guid": context_pack.get("player_guid"),
        "profile": character_state.get("profile"),
        "arc_states": character_state.get("arc_states"),
        "unlocks": character_state.get("unlocks"),
        "rewards": character_state.get("rewards"),
        "conversation_steering": character_state.get("conversation_steering"),
        "prompt_queue": character_state.get("prompt_queue"),
        "native_context_snapshot": generation_input.get("native_context_snapshot"),
        "notes": context_pack.get("notes"),
    })


def _json_clean(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _json_clean(_parse_json(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_clean(item) for item in value]
    return value


def _parse_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _live_location_from_presence(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "source": "unavailable",
            "fresh": False,
            "note": "No presence heartbeat for this player yet. WM has not sensed the live position.",
        }
    online = _truthy(row.get("Online"))
    return _json_clean({
        "source": "native_bridge_presence",
        # The heartbeat keeps an online player's row fresh every few seconds; an
        # offline player's row is the last sensed position, so it is not live.
        "fresh": online,
        "online": online,
        "updated_at": row.get("UpdatedAt"),
        "map_id": row.get("MapID"),
        "zone_id": row.get("ZoneID"),
        "area_id": row.get("AreaID"),
        "zone_name": row.get("ZoneName"),
        "area_name": row.get("AreaName"),
        "x": row.get("PosX"),
        "y": row.get("PosY"),
        "z": row.get("PosZ"),
        "o": row.get("Orientation"),
        "level": row.get("Level"),
        "health_pct": row.get("HealthPct"),
        "in_combat": _truthy(row.get("InCombat")),
    })


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip() not in ("", "0", "false", "False")
    return bool(value)


def _perception_from_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "source": "unavailable",
            "note": "No ambient perception heartbeat for this player yet.",
        }
    return _json_clean({
        "source": "native_bridge_perception",
        "updated_at": row.get("UpdatedAt"),
        "map_id": row.get("MapID"),
        "zone_id": row.get("ZoneID"),
        "area_id": row.get("AreaID"),
        "creature_count": row.get("CreatureCount"),
        "gameobject_count": row.get("GameObjectCount"),
        "detail_note": (
            "Ambient counts only. Request a context_snapshot to see specific "
            "nearby creatures/objects when it matters."
        ),
    })


def _without_keys(value: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(value, dict):
        return value
    return {key: item for key, item in value.items() if key not in keys}


def _first_or_none(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
