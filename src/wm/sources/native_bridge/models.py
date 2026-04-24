from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any


@dataclass(slots=True)
class NativeBridgeCursor:
    last_seen_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"last_seen_id": int(self.last_seen_id)}

    def to_cursor_value(self) -> str:
        return str(int(self.last_seen_id))

    @classmethod
    def from_cursor_value(cls, value: str | None) -> "NativeBridgeCursor":
        if value in (None, ""):
            return cls()
        try:
            return cls(last_seen_id=max(int(str(value)), 0))
        except ValueError:
            try:
                parsed = json.loads(str(value))
            except json.JSONDecodeError:
                return cls()
            if not isinstance(parsed, dict):
                return cls()
            raw_last_seen = parsed.get("last_seen_id")
            try:
                return cls(last_seen_id=max(int(raw_last_seen), 0))
            except (TypeError, ValueError):
                return cls()


def native_bridge_cursor_key(player_guid: int | None) -> str:
    if player_guid is None:
        return "last_seen"
    return f"last_seen:player:{int(player_guid)}"


@dataclass(slots=True)
class NativeBridgeRecord:
    bridge_event_id: int
    occurred_at: str
    event_family: str
    event_type: str
    source: str
    player_guid: int | None = None
    account_id: int | None = None
    subject_type: str | None = None
    subject_guid: str | None = None
    subject_entry: int | None = None
    object_type: str | None = None
    object_guid: str | None = None
    object_entry: int | None = None
    map_id: int | None = None
    zone_id: int | None = None
    area_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge_event_id": int(self.bridge_event_id),
            "occurred_at": self.occurred_at,
            "event_family": self.event_family,
            "event_type": self.event_type,
            "source": self.source,
            "player_guid": self.player_guid,
            "account_id": self.account_id,
            "subject_type": self.subject_type,
            "subject_guid": self.subject_guid,
            "subject_entry": self.subject_entry,
            "object_type": self.object_type,
            "object_guid": self.object_guid,
            "object_entry": self.object_entry,
            "map_id": self.map_id,
            "zone_id": self.zone_id,
            "area_id": self.area_id,
            "payload": self.payload,
        }


@dataclass(slots=True)
class NativeBridgeFailure:
    reason: str
    bridge_event_id: int | None = None
    event_family: str | None = None
    event_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "bridge_event_id": self.bridge_event_id,
            "event_family": self.event_family,
            "event_type": self.event_type,
            "details": self.details,
        }


@dataclass(slots=True)
class NativeBridgeScanResult:
    table_exists: bool
    cursor: NativeBridgeCursor
    records: list[NativeBridgeRecord] = field(default_factory=list)
    failures: list[NativeBridgeFailure] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_exists": self.table_exists,
            "cursor": self.cursor.to_dict(),
            "records": [record.to_dict() for record in self.records],
            "failures": [failure.to_dict() for failure in self.failures],
        }
