from __future__ import annotations

import json
import unittest

from wm.config import Settings
from wm.quests.rollback import QuestRollbackManager


class FakeMysqlClient:
    def __init__(self) -> None:
        self.mysql_bin_path = "mysql"

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_world" and "FROM wm_rollback_snapshot" in sql:
            snapshot = {
                "quest_template": [],
                "creature_queststarter": [],
                "creature_questender": [],
                "quest_offer_reward": [],
                "quest_request_items": [],
            }
            return [{"id": "5", "snapshot_json": json.dumps(snapshot)}]
        if database == "information_schema" and "FROM information_schema.TABLES" in sql:
            return [
                {"TABLE_NAME": "quest_offer_reward"},
                {"TABLE_NAME": "quest_request_items"},
                {"TABLE_NAME": "wm_reserved_slot"},
            ]
        raise AssertionError(f"Unexpected SQL in database {database}: {sql}")


class RecordingRollbackManager(QuestRollbackManager):
    def __init__(self) -> None:
        super().__init__(client=FakeMysqlClient(), settings=Settings(world_db_name="acore_world"))
        self.executed: list[str] = []

    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)

    def _sync_runtime(self, *, runtime_sync_mode: str, questgiver_entry: int | None, apply: bool):
        del runtime_sync_mode, questgiver_entry, apply
        class Dummy:
            overall_ok = True
            restart_recommended = False
            def to_dict(self):
                return {"enabled": False, "overall_ok": True, "protocol": "none", "commands": [], "note": None}
        return Dummy()


class QuestRollbackTests(unittest.TestCase):
    def test_rollback_apply_restores_empty_snapshot_and_sets_slot_staged(self) -> None:
        manager = RecordingRollbackManager()
        result = manager.rollback(quest_id=910005, mode="apply", runtime_sync_mode="off")
        self.assertTrue(result.ok)
        joined = "\n".join(manager.executed)
        self.assertIn("DELETE FROM creature_queststarter WHERE quest = 910005;", joined)
        self.assertIn("DELETE FROM quest_template WHERE ID = 910005;", joined)
        self.assertIn("UPDATE wm_reserved_slot SET SlotStatus = 'staged'", joined)
        self.assertIn("'rollback', 'success'", joined)


if __name__ == "__main__":
    unittest.main()
