from __future__ import annotations

import unittest

from wm.config import Settings
from wm.reserved.db_allocator import ReservedSlotDbAllocator


class FakeMysqlClient:
    mysql_bin_path = "mysql"

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows

    def query(self, **kwargs):
        sql = str(kwargs.get("sql") or "")
        if "SlotStatus = 'free'" in sql:
            return list(self.rows)
        if "AND ReservedID = 947001" in sql:
            return [
                {
                    "EntityType": "spell",
                    "ReservedID": "947001",
                    "SlotStatus": "staged",
                    "ArcKey": "wm_content:visible_spell:test",
                    "CharacterGUID": "5406",
                    "SourceQuestID": None,
                    "NotesJSON": '["test"]',
                }
            ]
        return []


class RecordingReservedSlotDbAllocator(ReservedSlotDbAllocator):
    def __init__(self, rows: list[dict[str, str]]) -> None:
        super().__init__(client=FakeMysqlClient(rows), settings=Settings(world_db_name="acore_world"))  # type: ignore[arg-type]
        self.executed: list[str] = []

    def _execute(self, sql: str) -> None:
        self.executed.append(sql)


class ReservedDbAllocatorTests(unittest.TestCase):
    def test_peek_next_free_spell_slot_skips_shell_band_rows(self) -> None:
        allocator = RecordingReservedSlotDbAllocator(
            [
                {
                    "EntityType": "spell",
                    "ReservedID": "940001",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                },
                {
                    "EntityType": "spell",
                    "ReservedID": "947000",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                },
                {
                    "EntityType": "spell",
                    "ReservedID": "947001",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                },
            ]
        )

        slot = allocator.peek_next_free_slot(entity_type="spell")

        self.assertIsNotNone(slot)
        assert slot is not None
        self.assertEqual(slot.reserved_id, 947001)

    def test_allocate_next_free_spell_slot_uses_managed_range_row(self) -> None:
        allocator = RecordingReservedSlotDbAllocator(
            [
                {
                    "EntityType": "spell",
                    "ReservedID": "940001",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                },
                {
                    "EntityType": "spell",
                    "ReservedID": "947000",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                },
                {
                    "EntityType": "spell",
                    "ReservedID": "947001",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                },
            ]
        )

        slot = allocator.allocate_next_free_slot(
            entity_type="spell",
            arc_key="wm_content:visible_spell:test",
            character_guid=5406,
            notes=["test"],
        )

        self.assertIsNotNone(slot)
        assert slot is not None
        self.assertEqual(slot.reserved_id, 947001)
        self.assertEqual(len(allocator.executed), 1)
        self.assertIn("ReservedID = 947001", allocator.executed[0])

    def test_non_spell_slots_are_not_filtered_by_spell_registry_rules(self) -> None:
        allocator = RecordingReservedSlotDbAllocator(
            [
                {
                    "EntityType": "quest",
                    "ReservedID": "910000",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                }
            ]
        )

        slot = allocator.peek_next_free_slot(entity_type="quest")

        self.assertIsNotNone(slot)
        assert slot is not None
        self.assertEqual(slot.reserved_id, 910000)


if __name__ == "__main__":
    unittest.main()
