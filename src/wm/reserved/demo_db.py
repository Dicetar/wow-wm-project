from __future__ import annotations

import json

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.reserved.db_allocator import ReservedSlotDbAllocator


def main() -> None:
    settings = Settings.from_env()
    client = MysqlCliClient()
    allocator = ReservedSlotDbAllocator(client=client, settings=settings)

    slot = allocator.allocate_next_free_slot(
        entity_type="spell_dbc_or_spell_slots",
        arc_key="wm_demo_db_allocation",
        character_guid=42,
        source_quest_id=910123,
        notes=["Allocated by live DB demo."],
    )
    if slot is None:
        raise SystemExit("No free spell slot available for allocation.")

    staged = slot.to_record()
    active = allocator.transition_slot(
        entity_type=slot.entity_type,
        reserved_id=slot.reserved_id,
        new_status="active",
    )
    retired = allocator.release_slot(
        entity_type=slot.entity_type,
        reserved_id=slot.reserved_id,
        archive=False,
    )

    print(json.dumps(
        {
            "staged": staged,
            "active": active.to_record() if active else None,
            "retired": retired.to_record() if retired else None,
            "summary": allocator.summarize(),
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
