from pathlib import Path
import unittest

from wm.config import Settings
from wm.reserved.db_allocator import ReservedSlotDbAllocator


class FakeMysqlClient:
    def __init__(self) -> None:
        self.mysql_bin_path = Path("mysql")
        self.rows = {
            ("quest", 910001): {
                "EntityType": "quest",
                "ReservedID": "910001",
                "SlotStatus": "free",
                "ArcKey": None,
                "CharacterGUID": None,
                "SourceQuestID": None,
                "NotesJSON": None,
            }
        }

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password, database
        if "WHERE EntityType = 'quest' AND SlotStatus = 'free'" in sql:
            return [self.rows[("quest", 910001)]]
        if "WHERE EntityType = 'quest' AND ReservedID = 910001" in sql:
            return [self.rows[("quest", 910001)]]
        raise AssertionError(f"Unexpected SQL: {sql}")


class RecordingReservedSlotAllocator(ReservedSlotDbAllocator):
    def __init__(self, client: FakeMysqlClient, settings: Settings) -> None:
        super().__init__(client=client, settings=settings)
        self.executed_sql: list[str] = []

    def _execute(self, sql: str) -> None:
        self.executed_sql.append(sql)
        if "UPDATE wm_reserved_slot SET SlotStatus = 'staged'" in sql:
            row = self.client.rows[("quest", 910001)]
            row["SlotStatus"] = "staged"
            row["ArcKey"] = "wm_event:repeat_hunt_followup"
            row["CharacterGUID"] = "42"
            row["SourceQuestID"] = "910001"


class ReservedSlotDbAllocatorTests(unittest.TestCase):
    def test_peek_next_free_slot_returns_lowest_free_slot(self) -> None:
        allocator = RecordingReservedSlotAllocator(FakeMysqlClient(), Settings(world_db_name="acore_world"))

        slot = allocator.peek_next_free_slot(entity_type="quest")

        self.assertIsNotNone(slot)
        assert slot is not None
        self.assertEqual(slot.reserved_id, 910001)
        self.assertEqual(slot.slot_status, "free")

    def test_ensure_slot_prepared_stages_free_slot(self) -> None:
        allocator = RecordingReservedSlotAllocator(FakeMysqlClient(), Settings(world_db_name="acore_world"))

        slot = allocator.ensure_slot_prepared(
            entity_type="quest",
            reserved_id=910001,
            arc_key="wm_event:repeat_hunt_followup",
            character_guid=42,
            source_quest_id=910001,
            notes=["rule:repeat_hunt_followup"],
        )

        self.assertIsNotNone(slot)
        assert slot is not None
        self.assertEqual(slot.slot_status, "staged")
        self.assertTrue(any("UPDATE wm_reserved_slot SET SlotStatus = 'staged'" in sql for sql in allocator.executed_sql))


if __name__ == "__main__":
    unittest.main()
