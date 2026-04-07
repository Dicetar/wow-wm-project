from __future__ import annotations

import unittest

from wm.config import Settings
from wm.reserved.seed import ReservedSlotSeeder


class FakeMysqlClient:
    def __init__(self) -> None:
        self.mysql_bin_path = "mysql"

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_world" and "FROM wm_reserved_slot" in sql:
            return [{"ReservedID": "910000"}, {"ReservedID": "910002"}]
        raise AssertionError(f"Unexpected SQL in database {database}: {sql}")


class RecordingSeeder(ReservedSlotSeeder):
    def __init__(self) -> None:
        super().__init__(client=FakeMysqlClient(), settings=Settings(world_db_name="acore_world"))
        self.executed: list[str] = []

    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)


class ReservedSeedTests(unittest.TestCase):
    def test_seed_inserts_only_missing_ids(self) -> None:
        seeder = RecordingSeeder()
        result = seeder.seed(entity_type="quest", start_id=910000, end_id=910003, mode="apply")
        self.assertTrue(result.ok)
        self.assertEqual(result.proposed_count, 2)
        self.assertEqual(result.inserted_count, 2)
        joined = "\n".join(seeder.executed)
        self.assertIn("910001", joined)
        self.assertIn("910003", joined)
        self.assertNotIn("910000, 'free')", joined)


if __name__ == "__main__":
    unittest.main()
