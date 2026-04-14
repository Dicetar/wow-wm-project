from __future__ import annotations

import unittest
from pathlib import Path

from wm.subjects.resolver import SubjectResolver
from wm.targets.live_profile import build_live_target_profile
from wm.targets.resolver import LookupStore, TargetResolver


class SubjectResolverTests(unittest.TestCase):
    def test_resolves_static_creature_profile_to_subject_card(self) -> None:
        store = LookupStore.from_json(Path("data/lookup/sample_creature_template_full.json"))
        resolver = SubjectResolver(TargetResolver(store=store))

        card = resolver.resolve_creature_entry(69)

        self.assertIsNotNone(card)
        assert card is not None
        self.assertEqual(card.canonical_id, "creature:69")
        self.assertEqual(card.display_name, "Timber Wolf")
        self.assertEqual(card.archetype, "Wolf")
        self.assertIn("family:wolf", card.group_keys)
        self.assertIn("type:beast", card.group_keys)
        self.assertIn("world_subject", card.role_tags)

    def test_resolves_live_profile_with_area_and_service_roles(self) -> None:
        profile = build_live_target_profile(
            {
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
        )

        card = SubjectResolver(target_resolver=_SingleProfileResolver(profile)).resolve_creature_entry(54)

        self.assertIsNotNone(card)
        assert card is not None
        self.assertEqual(card.title, "Weaponsmith")
        self.assertIn("merchant", card.role_tags)
        self.assertIn("elwynn", card.area_tags)
        self.assertIn("faction:stormwind_civilian", card.group_keys)

    def test_unknown_subject_returns_none(self) -> None:
        store = LookupStore.from_json(Path("data/lookup/sample_creature_template_full.json"))
        resolver = SubjectResolver(TargetResolver(store=store))

        self.assertIsNone(resolver.resolve_creature_entry(999999))


class _SingleProfileResolver:
    def __init__(self, profile) -> None:
        self.profile = profile

    def resolve_creature_entry(self, entry: int):
        del entry
        return self.profile


if __name__ == "__main__":
    unittest.main()
