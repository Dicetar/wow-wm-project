import unittest

from wm.config import Settings
from wm.quests.purge_range import QuestPurgeRangeManager
from wm.reactive.models import ReactiveQuestRule


class _DummyClient:
    mysql_bin_path = "mysql"


class FakeReactiveStore:
    def list_active_rules(self):
        return [
            ReactiveQuestRule(
                rule_key="reactive_bounty:kobold_vermin",
                is_active=True,
                player_guid_scope=5406,
                subject_type="creature",
                subject_entry=6,
                trigger_event_type="kill",
                kill_threshold=4,
                window_seconds=120,
                quest_id=910000,
                turn_in_npc_entry=197,
                grant_mode="direct_quest_add",
                post_reward_cooldown_seconds=60,
                metadata={},
                notes=[],
            )
        ]


class RecordingQuestPurgeRangeManager(QuestPurgeRangeManager):
    def __init__(self) -> None:
        super().__init__(
            client=_DummyClient(),  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world"),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
        )
        self.executed = []

    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)


class QuestPurgeRangeTests(unittest.TestCase):
    def test_skip_reactive_quest_by_default(self) -> None:
        manager = RecordingQuestPurgeRangeManager()

        result = manager.purge_range(
            start_id=910000,
            end_id=910001,
            mode="dry-run",
            include_reactive=False,
        )

        self.assertEqual(result.entries[0].status, "skipped_protected")
        self.assertEqual(result.entries[0].protected_by_rule, "reactive_bounty:kobold_vermin")
        self.assertEqual(result.entries[1].status, "planned")
        self.assertEqual(manager.executed, [])

    def test_apply_purge_includes_template_addon_cleanup(self) -> None:
        manager = RecordingQuestPurgeRangeManager()

        result = manager.purge_range(
            start_id=910001,
            end_id=910001,
            mode="apply",
            include_reactive=False,
        )

        self.assertEqual(result.entries[0].status, "purged")
        self.assertTrue(any("DELETE FROM quest_template_addon WHERE ID = 910001;" == sql for sql in manager.executed))


if __name__ == "__main__":
    unittest.main()
