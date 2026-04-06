from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.config import Settings
from wm.quests.generate_bounty import LiveCreatureResolver
from wm.targets.resolver import TargetProfile


class FakeMysqlClient:
    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password, database
        if "entry = 1498" in sql:
            return [{
                "entry": "1498",
                "name": "Bethor Iceshard",
                "subname": "Mage Trainer",
                "minlevel": "30",
                "maxlevel": "30",
                "faction": "68",
                "npcflag": "2",
                "type": "7",
                "family": "0",
                "rank": "0",
                "unit_class": "4",
                "gossip_menu_id": "0",
            }]
        if "entry = 46" in sql:
            return [{
                "entry": "46",
                "name": "Murloc Forager",
                "subname": None,
                "minlevel": "9",
                "maxlevel": "10",
                "faction": "18",
                "npcflag": "0",
                "type": "7",
                "family": "0",
                "rank": "0",
                "unit_class": "1",
                "gossip_menu_id": "0",
            }]
        return []


class GenerateBountyTests(unittest.TestCase):
    def test_live_resolver_decodes_creature_row(self) -> None:
        resolver = LiveCreatureResolver(client=FakeMysqlClient(), settings=Settings(world_db_name="acore_world"))
        result = resolver.resolve(1498)
        self.assertEqual(result.entry, 1498)
        self.assertEqual(result.name, "Bethor Iceshard")
        self.assertIn("QUEST_GIVER", result.profile.service_roles)
        self.assertEqual(result.profile.mechanical_type, "HUMANOID")


if __name__ == "__main__":
    unittest.main()
