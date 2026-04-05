from __future__ import annotations

import unittest

from wm.reserved.allocator import allocate_next_free_slot, build_slots_from_range, release_slot, summarize_slots, transition_slot
from wm.reserved.models import ACTIVE, ARCHIVED, FREE, RETIRED, STAGED


class ReservedAllocatorTests(unittest.TestCase):
    def test_build_slots_from_range(self) -> None:
        slots = build_slots_from_range("quest_template", 910000, 910002)
        self.assertEqual(len(slots), 3)
        self.assertEqual(slots[0].reserved_id, 910000)
        self.assertEqual(slots[-1].reserved_id, 910002)

    def test_allocate_next_free_slot_picks_lowest(self) -> None:
        slots = build_slots_from_range("spell_slots", 900000, 900002)
        slot = allocate_next_free_slot(slots, entity_type="spell_slots", character_guid=42)
        self.assertIsNotNone(slot)
        assert slot is not None
        self.assertEqual(slot.reserved_id, 900000)
        self.assertEqual(slot.slot_status, STAGED)
        self.assertEqual(slot.character_guid, 42)

    def test_transition_and_release(self) -> None:
        slots = build_slots_from_range("item_template", 911000, 911000)
        slot = allocate_next_free_slot(slots, entity_type="item_template")
        assert slot is not None
        transition_slot(slot, ACTIVE)
        self.assertEqual(slot.slot_status, ACTIVE)
        release_slot(slot)
        self.assertEqual(slot.slot_status, RETIRED)
        self.assertIsNone(slot.arc_key)
        release_slot(slot, archive=True)
        self.assertEqual(slot.slot_status, ARCHIVED)

    def test_summary_counts_statuses(self) -> None:
        slots = build_slots_from_range("gossip_menu", 912000, 912002)
        first = allocate_next_free_slot(slots, entity_type="gossip_menu")
        second = allocate_next_free_slot(slots, entity_type="gossip_menu")
        assert first is not None and second is not None
        transition_slot(first, ACTIVE)
        release_slot(second)
        summary = summarize_slots(slots)
        self.assertEqual(summary["gossip_menu"][FREE], 1)
        self.assertEqual(summary["gossip_menu"][ACTIVE], 1)
        self.assertEqual(summary["gossip_menu"][RETIRED], 1)


if __name__ == "__main__":
    unittest.main()
