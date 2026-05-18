from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CanonicalWMEvent:
    event_id: int
    event_type: str
    player_guid: int
    target_entry: int | None
    target_guid: int | None
    zone_id: int | None
    area_id: int | None
    source_adapter: str
    raw_data: dict
    canonical_at: datetime
    subject_entry: int | None = None
    subject_card: object | None = None  # SubjectCard when Phase 1 is wired in


def normalize_native_bridge_event(raw: dict, adapter: str = "native_bridge") -> CanonicalWMEvent:
    """Normalize a raw native bridge event dict to CanonicalWMEvent."""
    target_entry = raw.get("target_entry")
    return CanonicalWMEvent(
        event_id=raw["event_id"],
        event_type=raw["event_type"],
        player_guid=raw["player_guid"],
        target_entry=target_entry,
        target_guid=raw.get("target_guid"),
        zone_id=raw.get("zone_id"),
        area_id=raw.get("area_id"),
        source_adapter=adapter,
        raw_data=raw,
        canonical_at=datetime.utcnow(),
        subject_entry=target_entry,
    )
