from __future__ import annotations

import unittest

from wm.targets.live_profile import build_live_target_profile
from wm.targets.runtime_resolver import build_runtime_target_sql


class LiveTargetProfileTests(unittest.TestCase):
    def test_build_live_target_profile_for_murloc(self) -> None:
        raw = {
            "entry": "46",
            "name": "Murloc Forager",
            "subname": None,
            "minlevel": "9",
            "maxlevel": "10",
            "faction": "18",
            "faction_name": "Murloc",
            "npcflag": "0",
            "type": "7",
            "family": "0",
            "rank": "0",
            "unit_class": "1",
            "gossip_menu_id": "0",
            "gossip_option_count": "0",
            "quest_starter_ids": "",
            "quest_ender_ids": "45",
            "vendor_item_count": "0",
            "trainer_spell_count": "0",
            "spawn_count": "12",
            "spawn_contexts": "0:40:12",
        }
        profile = build_live_target_profile(raw)
        self.assertEqual(profile.entry, 46)
        self.assertEqual(profile.faction_label, "Murloc")
        self.assertIn("murloc", profile.derived_tags)
        self.assertIn("wild_encounter", profile.derived_tags)
        self.assertEqual(profile.spawn_contexts[0].zone_id, 40)

    def test_build_live_target_profile_for_vendor(self) -> None:
        raw = {
            "entry": "54",
            "name": "Corina Steele",
            "subname": "Weaponsmith",
            "minlevel": "10",
            "maxlevel": "10",
            "faction": "12",
            "faction_name": "Stormwind Civilian",
            "npcflag": str(128 + 4096),
            "type": "7",
            "family": "0",
            "rank": "0",
            "unit_class": "1",
            "gossip_menu_id": "0",
            "gossip_option_count": "0",
            "quest_starter_ids": "",
            "quest_ender_ids": "",
            "vendor_item_count": "24",
            "trainer_spell_count": "0",
            "spawn_count": "1",
            "spawn_contexts": "0:12:1",
        }
        profile = build_live_target_profile(raw)
        self.assertIn("merchant", profile.derived_tags)
        self.assertIn("named_service_npc", profile.derived_tags)
        self.assertIn("VENDOR", profile.service_roles)
        self.assertIn("REPAIR", profile.service_roles)

    def test_runtime_sql_includes_cross_reference_tables(self) -> None:
        sql = build_runtime_target_sql(46)
        self.assertIn("FROM creature_template ct", sql)
        self.assertIn("creature_queststarter", sql)
        self.assertIn("creature_questender", sql)
        self.assertIn("npc_vendor", sql)
        self.assertIn("trainer_spell", sql)
        self.assertIn("gossip_menu_option", sql)
        self.assertIn("faction_dbc", sql)
        self.assertIn("WHERE ct.entry = 46", sql)


if __name__ == "__main__":
    unittest.main()
