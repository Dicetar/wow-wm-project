from __future__ import annotations

from dataclasses import dataclass, field

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


def _string_from_payload(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value in (None, ""):
        return None
    return str(value)
