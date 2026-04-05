from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FREE = "free"
STAGED = "staged"
ACTIVE = "active"
RETIRED = "retired"
ARCHIVED = "archived"

VALID_SLOT_STATUSES = {FREE, STAGED, ACTIVE, RETIRED, ARCHIVED}


@dataclass(slots=True)
class ReservedSlot:
    entity_type: str
    reserved_id: int
    slot_status: str = FREE
    arc_key: str | None = None
    character_guid: int | None = None
    source_quest_id: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "reserved_id": self.reserved_id,
            "slot_status": self.slot_status,
            "arc_key": self.arc_key,
            "character_guid": self.character_guid,
            "source_quest_id": self.source_quest_id,
            "notes": self.notes,
        }
