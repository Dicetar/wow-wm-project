from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.config import Settings
from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.publish import QuestPublisher, load_bounty_quest_draft
from wm.targets.resolver import TargetProfile


class FakeMysqlClient:
    def __init__(self) -> None:
        self.mysql_bin_path = Path("mysql")

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
                {"TABLE_NAME": "wm_reserved_slot"},
            ]
        if database == "information_schema" and "FROM information_schema.COLUMNS" in sql:
            columns = [
                "ID",
                "QuestType",
                "QuestLevel",
                "MinLevel",
                "LogTitle",
                "QuestDescription",
                "ObjectiveText1",
                "OfferRewardText",
                "RequestItemsText",
                "RewardMoney",
                "RewardItem1",
                "RewardAmount1",
                "RequiredNpcOrGo1",
                "RequiredNpcOrGoCount1",
            ]
            return [{"COLUMN_NAME": column} for column in columns]
        if database == "acore_world" and "FROM creature_template" in sql and "entry = 1498" in sql:
            return [{"entry": "1498", "name": "Bethor Iceshard"}]
        if database == "acore_world" and "FROM creature_template" in sql and "entry = 46" in sql:
            return [{"entry": "46", "name": "Murloc Forager"}]
        if database == "acore_world" and "FROM quest_template" in sql and "SELECT ID, LogTitle" in sql:
            return []
        if database == "acore_world" and "FROM quest_template" in sql and "SELECT *" in sql:
            return []
        if database == "acore_world" and "FROM creature_queststarter" in sql:
            return []
        if database == "acore_world" and "FROM creature_questender" in sql:
            return []
        if database == "acore_world" and "FROM wm_reserved_slot" in sql:
            return [{"EntityType": "quest", "ReservedID": "910001", "SlotStatus": "staged", "ArcKey": None, "CharacterGUID": None, "SourceQuestID": None, "NotesJSON": None}]
        raise AssertionError(f"Unexpected SQL in database {database}: {sql}")


class RecordingQuestPublisher(QuestPublisher):
    def __init__(self, *, client: FakeMysqlClient, settings: Settings) -> None:
        super().__init__(client=client, settings=settings)
        self.executed_statements: list[str] = []

    def _execute_world(self, sql: str) -> None:
        self.executed_statements.append(sql)


class QuestPublishTests(unittest.TestCase):
    def _target(self) -> TargetProfile:
        return TargetProfile(
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
        )

    def _draft(self):
        return build_bounty_quest_draft(
            quest_id=910001,
            questgiver_entry=1498,
            questgiver_name="Bethor Iceshard",
            target_profile=self._target(),
            kill_count=8,
            reward_money_copper=1200,
        )

    def _settings(self) -> Settings:
        return Settings(world_db_name="acore_world", char_db_name="acore_characters")

    def test_preflight_ok_for_valid_demo_like_draft(self) -> None:
        publisher = RecordingQuestPublisher(client=FakeMysqlClient(), settings=self._settings())
        report = publisher.preflight(self._draft())
        self.assertTrue(report.ok)
        self.assertEqual(report.reserved_slot["SlotStatus"], "staged")

    def test_publish_apply_records_execution_plan(self) -> None:
        publisher = RecordingQuestPublisher(client=FakeMysqlClient(), settings=self._settings())
        result = publisher.publish(draft=self._draft(), mode="apply")
        self.assertTrue(result.applied)
        self.assertTrue(any("wm_rollback_snapshot" in statement for statement in publisher.executed_statements))
        self.assertTrue(any("INSERT INTO quest_template" in statement for statement in publisher.executed_statements))
        self.assertTrue(any("wm_publish_log" in statement and "success" in statement for statement in publisher.executed_statements))

    def test_load_bounty_quest_draft_accepts_demo_envelope(self) -> None:
        draft_payload = {
            "draft": self._draft().to_dict(),
            "validation": {"ok": True, "issues": []},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "draft.json"
            path.write_text(json.dumps(draft_payload), encoding="utf-8")
            draft = load_bounty_quest_draft(path)
        self.assertEqual(draft.quest_id, 910001)
        self.assertEqual(draft.objective.target_entry, 46)


if __name__ == "__main__":
    unittest.main()
