from __future__ import annotations

import unittest

from wm.config import Settings
from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.publish import QuestPublisher
from wm.targets.resolver import TargetProfile


class FakeCompatMysqlClient:
    def __init__(self) -> None:
        self.mysql_bin_path = "mysql"

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "information_schema" and "FROM information_schema.TABLES" in sql:
            return [
                {"TABLE_NAME": "quest_template"},
                {"TABLE_NAME": "creature_queststarter"},
                {"TABLE_NAME": "creature_questender"},
                {"TABLE_NAME": "creature_template"},
                {"TABLE_NAME": "wm_publish_log"},
                {"TABLE_NAME": "wm_rollback_snapshot"},
                {"TABLE_NAME": "quest_offer_reward"},
                {"TABLE_NAME": "quest_request_items"},
            ]
        if database == "information_schema" and "TABLE_NAME = 'quest_template'" in sql:
            columns = [
                "ID",
                "QuestType",
                "QuestLevel",
                "MinLevel",
                "LogTitle",
                "QuestDescription",
                "ObjectiveText1",
                "RewardMoney",
                "RewardItem1",
                "RewardAmount1",
                "RequiredNpcOrGo1",
                "RequiredNpcOrGoCount1",
            ]
            return [{"COLUMN_NAME": column} for column in columns]
        if database == "information_schema" and "TABLE_NAME = 'quest_offer_reward'" in sql:
            return [{"COLUMN_NAME": "ID"}, {"COLUMN_NAME": "RewardText"}]
        if database == "information_schema" and "TABLE_NAME = 'quest_request_items'" in sql:
            return [{"COLUMN_NAME": "ID"}, {"COLUMN_NAME": "CompletionText"}]
        if database == "acore_world" and "FROM creature_template" in sql:
            return [{"entry": "1", "name": "ok"}]
        if database == "acore_world" and "FROM quest_template" in sql and "SELECT ID, LogTitle" in sql:
            return []
        if database == "acore_world" and "FROM quest_template" in sql:
            return []
        if database == "acore_world" and "FROM creature_queststarter" in sql:
            return []
        if database == "acore_world" and "FROM creature_questender" in sql:
            return []
        if database == "acore_world" and "FROM quest_offer_reward" in sql:
            return []
        if database == "acore_world" and "FROM quest_request_items" in sql:
            return []
        if database == "acore_world" and "FROM wm_reserved_slot" in sql:
            return []
        raise AssertionError(f"Unexpected SQL in {database}: {sql}")


class CompatPublisher(QuestPublisher):
    def __init__(self) -> None:
        super().__init__(client=FakeCompatMysqlClient(), settings=Settings(world_db_name="acore_world"))
        self.executed: list[str] = []

    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)


class QuestPublishCompatTests(unittest.TestCase):
    def test_preflight_accepts_auxiliary_text_tables(self) -> None:
        publisher = CompatPublisher()
        draft = build_bounty_quest_draft(
            quest_id=910001,
            questgiver_entry=1498,
            questgiver_name="Bethor Iceshard",
            target_profile=TargetProfile(
                entry=46,
                name="Murloc Forager",
                subname=None,
                level_min=9,
                level_max=10,
                faction_id=18,
                faction_label="Murloc",
                mechanical_type="HUMANOID",
                family=None,
                rank="NORMAL",
                unit_class="WARRIOR",
                service_roles=[],
                has_gossip_menu=False,
            ),
        )
        report = publisher.preflight(draft)
        self.assertTrue(report.ok)
        self.assertTrue(report.compatibility["offer_reward_text_supported"])
        self.assertTrue(report.compatibility["request_items_text_supported"])

    def test_apply_uses_auxiliary_tables_when_needed(self) -> None:
        publisher = CompatPublisher()
        draft = build_bounty_quest_draft(
            quest_id=910001,
            questgiver_entry=1498,
            questgiver_name="Bethor Iceshard",
            target_profile=TargetProfile(
                entry=46,
                name="Murloc Forager",
                subname=None,
                level_min=9,
                level_max=10,
                faction_id=18,
                faction_label="Murloc",
                mechanical_type="HUMANOID",
                family=None,
                rank="NORMAL",
                unit_class="WARRIOR",
                service_roles=[],
                has_gossip_menu=False,
            ),
        )
        result = publisher.publish(draft=draft, mode="apply")
        self.assertTrue(result.applied)
        joined = "\n".join(publisher.executed)
        self.assertIn("INSERT INTO quest_offer_reward", joined)
        self.assertIn("INSERT INTO quest_request_items", joined)


if __name__ == "__main__":
    unittest.main()
