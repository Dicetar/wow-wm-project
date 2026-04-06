from __future__ import annotations

import unittest

from wm.config import Settings
from wm.quests.edit_live import QuestLiveEditor


class FakeMysqlClient:
    def __init__(self) -> None:
        self.mysql_bin_path = "mysql"
        self.queries: list[str] = []

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        self.queries.append(sql)
        if database == "information_schema" and "FROM information_schema.COLUMNS" in sql:
            columns = [
                "ID",
                "LogTitle",
                "RewardMoney",
                "RewardItem1",
                "RewardAmount1",
                "RewardXPDifficulty",
                "OfferRewardText",
            ]
            return [{"COLUMN_NAME": column} for column in columns]
        if database == "information_schema" and "FROM information_schema.TABLES" in sql:
            return [
                {"TABLE_NAME": "quest_offer_reward"},
                {"TABLE_NAME": "item_template"},
                {"TABLE_NAME": "creature_queststarter"},
            ]
        if database == "acore_world" and "FROM `quest_template` WHERE `ID` = 910005" in sql:
            return [{"ID": "910005"}]
        if database == "acore_world" and "FROM `item_template` WHERE `entry` = 6948" in sql:
            return [{"entry": "6948"}]
        if database == "acore_world" and "FROM `creature_queststarter` WHERE `quest` = 910005" in sql:
            return [{"id": "197"}]
        return []


class RecordingEditor(QuestLiveEditor):
    def __init__(self) -> None:
        super().__init__(client=FakeMysqlClient(), settings=Settings(world_db_name="acore_world"))
        self.executed: list[str] = []

    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)

    def _sync_runtime(self, *, quest_id: int, runtime_sync_mode: str, apply: bool):
        del quest_id, runtime_sync_mode, apply
        class Dummy:
            restart_recommended = False
            def to_dict(self):
                return {"enabled": False, "overall_ok": True, "protocol": "none", "commands": [], "note": None}
        return Dummy()


class EditLiveTests(unittest.TestCase):
    def test_edit_builds_expected_update(self) -> None:
        editor = RecordingEditor()
        result = editor.edit(
            quest_id=910005,
            title="Marshal's Kobold Bounty",
            reward_money_copper=2400,
            reward_item_entry=6948,
            reward_item_count=1,
            clear_reward_item=False,
            reward_xp=4,
            offer_reward_text="Take this and report back later.",
            runtime_sync_mode="off",
            apply=True,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.applied)
        joined = "\n".join(editor.executed)
        self.assertIn("`LogTitle` = 'Marshal''s Kobold Bounty'", joined)
        self.assertIn("`RewardMoney` = 2400", joined)
        self.assertIn("`RewardItem1` = 6948", joined)
        self.assertIn("`RewardAmount1` = 1", joined)
        self.assertIn("`RewardXPDifficulty` = 4", joined)
        self.assertIn("`OfferRewardText` = 'Take this and report back later.'", joined)


if __name__ == "__main__":
    unittest.main()
