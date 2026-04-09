from __future__ import annotations

import json
import unittest

from wm.config import Settings
from wm.quests.rollback import QuestRollbackManager
from wm.reactive.models import ReactiveQuestRule


class FakeMysqlClient:
    def __init__(self) -> None:
        self.mysql_bin_path = "mysql"

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_world" and "FROM wm_rollback_snapshot" in sql:
            snapshot = {
                "quest_template": [],
                "quest_template_addon": [],
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
                {"TABLE_NAME": "quest_template_addon"},
                {"TABLE_NAME": "wm_reserved_slot"},
            ]
        raise AssertionError(f"Unexpected SQL in database {database}: {sql}")


class RecordingRollbackManager(QuestRollbackManager):
    def __init__(self, *, reactive_rule: ReactiveQuestRule | None = None) -> None:
        class FakeReactiveStore:
            def get_rule_by_quest_id(self_nonlocal, *, quest_id: int):
                del quest_id
                return reactive_rule

        super().__init__(
            client=FakeMysqlClient(),
            settings=Settings(world_db_name="acore_world"),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
        )
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
        self.assertIn("DELETE FROM quest_template_addon WHERE ID = 910005;", joined)
        self.assertIn("DELETE FROM quest_template WHERE ID = 910005;", joined)
        self.assertIn("UPDATE wm_reserved_slot SET SlotStatus = 'staged'", joined)
        self.assertIn("'rollback', 'success'", joined)

    def test_reactive_quest_requires_explicit_override(self) -> None:
        manager = RecordingRollbackManager(
            reactive_rule=ReactiveQuestRule(
                rule_key="reactive_bounty:kobold_vermin",
                is_active=True,
                player_guid_scope=5406,
                subject_type="creature",
                subject_entry=6,
                trigger_event_type="kill",
                kill_threshold=4,
                window_seconds=120,
                quest_id=910005,
                turn_in_npc_entry=197,
                grant_mode="direct_quest_add",
                post_reward_cooldown_seconds=60,
                metadata={},
                notes=[],
            )
        )

        result = manager.rollback(
            quest_id=910005,
            mode="dry-run",
            runtime_sync_mode="off",
        )

        self.assertFalse(result.ok)
        self.assertTrue(any(issue.path == "reactive_rule" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
