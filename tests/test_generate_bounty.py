from __future__ import annotations

import unittest

from wm.config import Settings
from wm.quests.generate_bounty import LiveCreatureResolver


class FakeMysqlClient:
    def __init__(self) -> None:
        self.last_sql: str | None = None

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        self.last_sql = sql
        if database == "information_schema" and "TABLE_NAME = 'quest_template'" in sql:
            columns = [
                "Method",
                "QuestType",
                "QuestFlags",
                "SpecialFlags",
                "QuestInfoID",
                "QuestSortID",
                "ZoneOrSort",
                "SuggestedPlayers",
            ]
            return [{"COLUMN_NAME": column} for column in columns]
        if database == "acore_world" and "FROM `creature_queststarter`" in sql:
            return [{"quest": "783"}]
        if database == "acore_world" and "FROM `quest_template`" in sql and "WHERE `ID` = 783" in sql:
            return [{
                "Method": "2",
                "QuestType": "0",
                "QuestFlags": "8",
                "SpecialFlags": "0",
                "QuestInfoID": "0",
                "QuestSortID": "0",
                "ZoneOrSort": "12",
                "SuggestedPlayers": "1",
            }]
        if "`entry` = 1498" in sql or "`name` = 'Marshal McBride'" in sql:
            return [{
                "entry": "1498",
                "name": "Marshal McBride",
                "subname": None,
                "minlevel": "1",
                "maxlevel": "1",
                "faction": "12",
                "npcflag": "2",
                "type": "7",
                "family": "0",
                "rank": "0",
                "unit_class": "1",
                "gossip_menu_id": "0",
            }]
        if "`entry` = 6" in sql or "`name` = 'Kobold Vermin'" in sql:
            return [{
                "entry": "6",
                "name": "Kobold Vermin",
                "subname": None,
                "minlevel": "2",
                "maxlevel": "3",
                "faction": "25",
                "npcflag": "0",
                "type": "7",
                "family": "0",
                "rank": "0",
                "unit_class": "1",
                "gossip_menu_id": "0",
            }]
        if "LIKE '%Marshal%'" in sql:
            return [{
                "entry": "1498",
                "name": "Marshal McBride",
                "subname": None,
                "minlevel": "1",
                "maxlevel": "1",
                "faction": "12",
                "npcflag": "2",
                "type": "7",
                "family": "0",
                "rank": "0",
                "unit_class": "1",
                "gossip_menu_id": "0",
            }]
        return []


class GenerateBountyTests(unittest.TestCase):
    def test_live_resolver_decodes_creature_row(self) -> None:
        client = FakeMysqlClient()
        resolver = LiveCreatureResolver(client=client, settings=Settings(world_db_name="acore_world"))
        result = resolver.resolve(entry=1498)
        self.assertEqual(result.entry, 1498)
        self.assertEqual(result.name, "Marshal McBride")
        self.assertIn("QUEST_GIVER", result.profile.service_roles)
        self.assertEqual(result.profile.mechanical_type, "HUMANOID")
        self.assertIsNotNone(client.last_sql)
        self.assertIn("`rank`", client.last_sql or "")
        self.assertIn("FROM `creature_template`", client.last_sql or "")

    def test_live_resolver_supports_exact_name_lookup(self) -> None:
        resolver = LiveCreatureResolver(client=FakeMysqlClient(), settings=Settings(world_db_name="acore_world"))
        result = resolver.resolve(name="Marshal McBride")
        self.assertEqual(result.entry, 1498)
        self.assertEqual(result.name, "Marshal McBride")

    def test_fetch_template_defaults_for_questgiver(self) -> None:
        resolver = LiveCreatureResolver(client=FakeMysqlClient(), settings=Settings(world_db_name="acore_world"))
        defaults = resolver.fetch_template_defaults_for_questgiver(1498)
        self.assertEqual(defaults["Method"], 2)
        self.assertEqual(defaults["QuestFlags"], 8)
        self.assertEqual(defaults["ZoneOrSort"], 12)


if __name__ == "__main__":
    unittest.main()
