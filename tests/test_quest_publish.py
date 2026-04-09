from __future__ import annotations

import json
from pathlib import Path
import unittest

from wm.config import Settings
from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.publish import QuestPublisher, load_bounty_quest_draft
from wm.targets.resolver import TargetProfile


class FakeMysqlClient:
    def __init__(self, *, reserved_rows: list[dict[str, str]] | None = None, duplicate_rows: list[dict[str, str]] | None = None, existing_rows: list[dict[str, str]] | None = None) -> None:
        self.mysql_bin_path = Path("mysql")
        self.reserved_rows = reserved_rows if reserved_rows is not None else [{"EntityType": "quest", "ReservedID": "910001", "SlotStatus": "staged", "ArcKey": None, "CharacterGUID": None, "SourceQuestID": None, "NotesJSON": None}]
        self.duplicate_rows = duplicate_rows or []
        self.existing_rows = existing_rows or []

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "information_schema" and "FROM information_schema.TABLES" in sql:
            return [
                {"TABLE_NAME": "quest_template"},
                {"TABLE_NAME": "quest_template_addon"},
                {"TABLE_NAME": "creature_queststarter"},
                {"TABLE_NAME": "creature_questender"},
                {"TABLE_NAME": "creature_template"},
                {"TABLE_NAME": "wm_publish_log"},
                {"TABLE_NAME": "wm_rollback_snapshot"},
                {"TABLE_NAME": "wm_reserved_slot"},
            ]
        if database == "information_schema" and "FROM information_schema.COLUMNS" in sql:
            if "TABLE_NAME = 'quest_template_addon'" in sql:
                return [{"COLUMN_NAME": "ID"}, {"COLUMN_NAME": "SpecialFlags"}]
            columns = [
                "ID",
                "QuestType",
                "QuestLevel",
                "MinLevel",
                "LogTitle",
                "LogDescription",
                "QuestDescription",
                "QuestCompletionLog",
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
        if database == "acore_world" and "FROM creature_template" in sql and "entry = 197" in sql:
            return [{"entry": "197", "name": "Marshal McBride"}]
        if database == "acore_world" and "FROM creature_template" in sql and "entry = 46" in sql:
            return [{"entry": "46", "name": "Murloc Forager"}]
        if database == "acore_world" and "JOIN creature_queststarter" in sql:
            return self.duplicate_rows
        if database == "acore_world" and "FROM quest_template" in sql and "SELECT ID, LogTitle" in sql:
            return self.existing_rows
        if database == "acore_world" and "FROM quest_template" in sql and "SELECT *" in sql:
            return []
        if database == "acore_world" and "FROM creature_queststarter" in sql:
            return []
        if database == "acore_world" and "FROM creature_questender" in sql:
            return []
        if database == "acore_world" and "FROM quest_template_addon" in sql:
            return []
        if database == "acore_world" and "FROM wm_reserved_slot" in sql:
            return self.reserved_rows
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

    def test_preflight_requires_reserved_slot_row(self) -> None:
        publisher = RecordingQuestPublisher(client=FakeMysqlClient(reserved_rows=[]), settings=self._settings())
        report = publisher.preflight(self._draft())
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.path == "reserved_slot" for issue in report.issues))

    def test_preflight_blocks_duplicate_title_for_same_questgiver(self) -> None:
        duplicate_rows = [{"ID": "910099", "LogTitle": "Bounty: Murloc Forager"}]
        publisher = RecordingQuestPublisher(client=FakeMysqlClient(duplicate_rows=duplicate_rows), settings=self._settings())
        report = publisher.preflight(self._draft())
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.path == "dedupe.title" for issue in report.issues))

    def test_preflight_blocks_active_slot_republish(self) -> None:
        reserved_rows = [{"EntityType": "quest", "ReservedID": "910001", "SlotStatus": "active", "ArcKey": None, "CharacterGUID": None, "SourceQuestID": None, "NotesJSON": None}]
        existing_rows = [{"ID": "910001", "LogTitle": "Bounty: Murloc Forager"}]
        publisher = RecordingQuestPublisher(client=FakeMysqlClient(reserved_rows=reserved_rows, existing_rows=existing_rows), settings=self._settings())
        report = publisher.preflight(self._draft())
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.path == "reserved_slot.status" for issue in report.issues))

    def test_publish_apply_records_execution_plan(self) -> None:
        publisher = RecordingQuestPublisher(client=FakeMysqlClient(), settings=self._settings())
        draft = self._draft()
        draft.template_defaults["SpecialFlags"] = 1
        result = publisher.publish(draft=draft, mode="apply")
        self.assertTrue(result.applied)
        self.assertTrue(any("wm_rollback_snapshot" in statement for statement in publisher.executed_statements))
        self.assertTrue(any("INSERT INTO quest_template" in statement for statement in publisher.executed_statements))
        self.assertTrue(any("INSERT INTO quest_template_addon" in statement for statement in publisher.executed_statements))
        self.assertTrue(any("wm_publish_log" in statement and "success" in statement for statement in publisher.executed_statements))
        self.assertTrue(any("UPDATE wm_reserved_slot SET SlotStatus = 'active'" in statement for statement in publisher.executed_statements))

    def test_load_bounty_quest_draft_accepts_demo_envelope(self) -> None:
        draft_payload = {
            "draft": self._draft().to_dict(),
            "validation": {"ok": True, "issues": []},
        }
        tmpdir = Path("artifacts") / "test_tmp"
        tmpdir.mkdir(parents=True, exist_ok=True)
        path = tmpdir / "draft_envelope.json"
        path.write_text(json.dumps(draft_payload), encoding="utf-8")
        draft = load_bounty_quest_draft(path)
        self.assertEqual(draft.quest_id, 910001)
        self.assertEqual(draft.objective.target_entry, 46)

    def test_direct_grant_preflight_allows_no_starter(self) -> None:
        publisher = RecordingQuestPublisher(client=FakeMysqlClient(), settings=self._settings())
        draft = build_bounty_quest_draft(
            quest_id=910001,
            questgiver_entry=197,
            questgiver_name="Marshal McBride",
            target_profile=self._target(),
            kill_count=4,
            reward_money_copper=1200,
            start_npc_entry=None,
            end_npc_entry=197,
            grant_mode="direct_quest_add",
        )

        report = publisher.preflight(draft)

        self.assertTrue(report.ok)
        self.assertEqual(report.duplicate_title_rows, [])


if __name__ == "__main__":
    unittest.main()
