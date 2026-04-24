from __future__ import annotations

import json
from pathlib import Path

from wm.reserved.allocator import allocate_next_free_slot, build_slots_from_range, release_slot, summarize_slots, transition_slot
from wm.reserved.models import ACTIVE


def main() -> None:
    spec_path = Path(r"D:\WOW\wm-project\data\specs\reserved_id_ranges.json")
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    ranges = payload.get("ranges", {})

    slots = []
    for entity_type, spec in ranges.items():
        start = spec.get("start")
        end = spec.get("end")
        if start is None or end is None:
            continue
        slots.extend(build_slots_from_range(entity_type, int(start), int(end)))

    first_spell = allocate_next_free_slot(
        slots,
        entity_type="spell",
        arc_key="wm_ironforge_arcane_incident",
        character_guid=42,
        source_quest_id=910001,
        notes=["Reserved for alternate arcane burst wrapper."],
    )
    if first_spell:
        transition_slot(first_spell, ACTIVE)

    first_item = allocate_next_free_slot(
        slots,
        entity_type="item_template",
        arc_key="wm_ironforge_arcane_incident",
        character_guid=42,
        source_quest_id=910002,
        notes=["Reserved for equipped-gate item reward."],
    )

    first_gossip = allocate_next_free_slot(
        slots,
        entity_type="gossip_menu",
        arc_key="wm_ironforge_arcane_incident",
        character_guid=42,
        notes=["Reserved for branch-choice conversation."],
    )
    if first_gossip:
        release_slot(first_gossip)

    print(json.dumps(
        {
            "summary": summarize_slots(slots),
            "examples": {
                "spell_slot": first_spell.to_record() if first_spell else None,
                "item_slot": first_item.to_record() if first_item else None,
                "gossip_slot": first_gossip.to_record() if first_gossip else None,
            },
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
