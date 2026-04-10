from __future__ import annotations

from dataclasses import dataclass, field
import json

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.sources.native_bridge.models import NativeBridgeRecord
from wm.sources.native_bridge.models import NativeBridgeScanResult
from wm.sources.native_bridge.scanner import NativeBridgeScanner


@dataclass(slots=True)
class NativeBridgeAdapter:
    client: MysqlCliClient
    settings: Settings
    store: EventStore
    name: str = "native_bridge"
    cursor_key: str = "last_seen"
    batch_size: int | None = None
    player_guid_filter: int | None = None
    last_cursor_value: str | None = field(default=None, init=False)
    last_scan_result: NativeBridgeScanResult | None = field(default=None, init=False)

    def poll(self) -> list[WMEvent]:
        cursor = self.store.get_cursor(adapter_name=self.name, cursor_key=self.cursor_key)
        scanner = NativeBridgeScanner(client=self.client, settings=self.settings)
        scan_result = scanner.scan(
            cursor_value=cursor.cursor_value if cursor is not None else None,
            limit=int(self.batch_size or self.settings.native_bridge_batch_size),
            player_guid=self.player_guid_filter,
        )
        self.last_scan_result = scan_result
        self.last_cursor_value = scan_result.cursor.to_cursor_value()
        events: list[WMEvent] = []
        for record in scan_result.records:
            event = _record_to_event(record)
            if event is not None:
                events.append(event)
        events.extend(_build_gossip_session_expired_events(client=self.client, settings=self.settings, player_guid=self.player_guid_filter))
        return events


def _record_to_event(record: NativeBridgeRecord) -> WMEvent | None:
    family = record.event_family.strip().lower()
    event_type = record.event_type.strip().lower()
    metadata = {
        "bridge_event_id": record.bridge_event_id,
        "raw_event_family": family,
        "raw_event_type": event_type,
        "account_id": record.account_id,
        "subject_guid": record.subject_guid,
        "object_type": record.object_type,
        "object_guid": record.object_guid,
        "object_entry": record.object_entry,
        "payload": record.payload,
    }

    if family == "combat" and event_type == "kill":
        if record.subject_entry is None:
            return None
        return WMEvent(
            event_class="observed",
            event_type="kill",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type=record.subject_type or "creature",
            subject_entry=record.subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value="1",
            metadata=metadata,
        )

    if family == "quest" and event_type in {"accepted", "granted", "completed", "rewarded"}:
        canonical_type = {
            "accepted": "quest_accept",
            "granted": "quest_granted",
            "completed": "quest_completed",
            "rewarded": "quest_rewarded",
        }[event_type]
        return WMEvent(
            event_class="observed",
            event_type=canonical_type,
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type=record.subject_type,
            subject_entry=record.subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "quest_title") or _string_from_payload(record.payload, "quest_id"),
            metadata=metadata,
        )

    if family == "loot" and event_type == "item":
        return WMEvent(
            event_class="observed",
            event_type="loot_item",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type=record.subject_type,
            subject_entry=record.subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "count") or "1",
            metadata=metadata,
        )

    if family == "gossip" and event_type == "opened":
        return WMEvent(
            event_class="observed",
            event_type="talk",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type=record.subject_type,
            subject_entry=record.subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "subject_name"),
            metadata=metadata,
        )

    if family == "gossip" and event_type == "selected":
        return WMEvent(
            event_class="observed",
            event_type="gossip_select",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type=record.subject_type,
            subject_entry=record.subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "action"),
            metadata=metadata,
        )

    if family == "area" and event_type == "entered":
        subject_entry = record.area_id or record.subject_entry
        return WMEvent(
            event_class="observed",
            event_type="enter_area",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type="area" if subject_entry is not None else None,
            subject_entry=subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "area_name"),
            metadata=metadata,
        )

    if family == "spell" and event_type == "cast":
        return WMEvent(
            event_class="observed",
            event_type="spell_cast",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type=record.subject_type,
            subject_entry=record.subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "spell_name") or _string_from_payload(record.payload, "spell_id"),
            metadata=metadata,
        )

    if family == "item" and event_type == "used":
        return WMEvent(
            event_class="observed",
            event_type="item_use",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type=record.subject_type or record.object_type,
            subject_entry=record.subject_entry if record.subject_entry is not None else record.object_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "item_name") or _string_from_payload(record.payload, "item_entry"),
            metadata=metadata,
        )

    if family == "aura" and event_type in {"applied", "removed"}:
        return WMEvent(
            event_class="observed",
            event_type="aura_applied" if event_type == "applied" else "aura_removed",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type=record.subject_type,
            subject_entry=record.subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "aura_name") or _string_from_payload(record.payload, "spell_name"),
            metadata=metadata,
        )

    if family == "weather" and event_type == "changed":
        subject_entry = record.zone_id or record.subject_entry
        return WMEvent(
            event_class="observed",
            event_type="weather_changed",
            source="native_bridge",
            source_event_key=f"native_bridge:{record.bridge_event_id}",
            occurred_at=record.occurred_at,
            player_guid=record.player_guid,
            subject_type="zone" if subject_entry is not None else None,
            subject_entry=subject_entry,
            map_id=record.map_id,
            zone_id=record.zone_id,
            area_id=record.area_id,
            event_value=_string_from_payload(record.payload, "weather_state"),
            metadata=metadata,
        )

    return None


def _build_gossip_session_expired_events(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int | None,
) -> list[WMEvent]:
    timeout_seconds = int(settings.native_bridge_gossip_session_timeout_seconds)
    if timeout_seconds <= 0:
        return []

    predicates = [
        "talk.EventClass = 'observed'",
        "talk.EventType = 'talk'",
        "talk.Source = 'native_bridge'",
        f"talk.OccurredAt <= DATE_SUB(NOW(), INTERVAL {timeout_seconds} SECOND)",
        "NOT EXISTS ("
        "SELECT 1 FROM wm_event_log expired "
        "WHERE expired.Source = 'native_bridge_derived' "
        "AND expired.SourceEventKey = CONCAT(talk.SourceEventKey, ':gossip_session_expired')"
        ")",
        "NOT EXISTS ("
        "SELECT 1 FROM wm_event_log selected "
        "WHERE selected.EventClass = 'observed' "
        "AND selected.EventType = 'gossip_select' "
        "AND selected.Source = 'native_bridge' "
        "AND selected.PlayerGUID <=> talk.PlayerGUID "
        "AND selected.SubjectType <=> talk.SubjectType "
        "AND selected.SubjectEntry <=> talk.SubjectEntry "
        "AND selected.EventID > talk.EventID "
        f"AND selected.OccurredAt <= DATE_ADD(talk.OccurredAt, INTERVAL {timeout_seconds} SECOND)"
        ")",
    ]
    if player_guid is not None:
        predicates.append(f"talk.PlayerGUID = {int(player_guid)}")

    rows = client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=(
            "SELECT talk.EventID, talk.SourceEventKey, talk.OccurredAt, "
            "DATE_ADD(talk.OccurredAt, INTERVAL "
            f"{timeout_seconds} SECOND) AS ExpiredAt, "
            "talk.PlayerGUID, talk.SubjectType, talk.SubjectEntry, talk.MapID, talk.ZoneID, talk.AreaID, "
            "talk.EventValue, talk.MetadataJSON "
            "FROM wm_event_log talk "
            f"WHERE {' AND '.join(predicates)} "
            "ORDER BY talk.EventID ASC "
            "LIMIT 25"
        ),
    )
    events: list[WMEvent] = []
    for row in rows:
        metadata = _metadata_from_json(row.get("MetadataJSON"))
        metadata.update(
            {
                "derived": True,
                "derived_event_type": "gossip_session_expired",
                "derived_from_event_id": _int_or_none(row.get("EventID")),
                "derived_from_source_event_key": row.get("SourceEventKey"),
                "timeout_seconds": timeout_seconds,
            }
        )
        events.append(
            WMEvent(
                event_class="observed",
                event_type="gossip_session_expired",
                source="native_bridge_derived",
                source_event_key=f"{row['SourceEventKey']}:gossip_session_expired",
                occurred_at=str(row.get("ExpiredAt") or row.get("OccurredAt")),
                player_guid=_int_or_none(row.get("PlayerGUID")),
                subject_type=_str_or_none(row.get("SubjectType")),
                subject_entry=_int_or_none(row.get("SubjectEntry")),
                map_id=_int_or_none(row.get("MapID")),
                zone_id=_int_or_none(row.get("ZoneID")),
                area_id=_int_or_none(row.get("AreaID")),
                event_value=_str_or_none(row.get("EventValue")),
                metadata=metadata,
            )
        )
    return events


def _metadata_from_json(value: object) -> dict[str, object]:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {"raw_metadata": str(value)}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _string_from_payload(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value in (None, ""):
        return None
    return str(value)


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
