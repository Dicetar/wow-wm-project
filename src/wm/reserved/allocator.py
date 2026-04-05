from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from wm.reserved.models import ACTIVE, ARCHIVED, FREE, RETIRED, STAGED, ReservedSlot, VALID_SLOT_STATUSES


def build_slots_from_range(entity_type: str, start: int, end: int) -> list[ReservedSlot]:
    if end < start:
        raise ValueError("range end must be >= start")
    return [ReservedSlot(entity_type=entity_type, reserved_id=value, slot_status=FREE) for value in range(start, end + 1)]


def allocate_next_free_slot(
    slots: list[ReservedSlot],
    *,
    entity_type: str,
    arc_key: str | None = None,
    character_guid: int | None = None,
    source_quest_id: int | None = None,
    notes: list[str] | None = None,
) -> ReservedSlot | None:
    for slot in sorted((x for x in slots if x.entity_type == entity_type), key=lambda s: s.reserved_id):
        if slot.slot_status != FREE:
            continue
        slot.slot_status = STAGED
        slot.arc_key = arc_key
        slot.character_guid = character_guid
        slot.source_quest_id = source_quest_id
        slot.notes = list(notes or [])
        return slot
    return None


def transition_slot(slot: ReservedSlot, new_status: str) -> ReservedSlot:
    if new_status not in VALID_SLOT_STATUSES:
        raise ValueError(f"invalid slot status: {new_status}")
    slot.slot_status = new_status
    return slot


def release_slot(slot: ReservedSlot, *, archive: bool = False) -> ReservedSlot:
    slot.slot_status = ARCHIVED if archive else RETIRED
    slot.arc_key = None
    slot.character_guid = None
    slot.source_quest_id = None
    slot.notes = []
    return slot


def summarize_slots(slots: Iterable[ReservedSlot]) -> dict[str, dict[str, int]]:
    by_entity: dict[str, Counter[str]] = defaultdict(Counter)
    for slot in slots:
        by_entity[slot.entity_type][slot.slot_status] += 1
    summary: dict[str, dict[str, int]] = {}
    for entity_type, counts in by_entity.items():
        summary[entity_type] = {
            FREE: counts.get(FREE, 0),
            STAGED: counts.get(STAGED, 0),
            ACTIVE: counts.get(ACTIVE, 0),
            RETIRED: counts.get(RETIRED, 0),
            ARCHIVED: counts.get(ARCHIVED, 0),
            "total": sum(counts.values()),
        }
    return summary
