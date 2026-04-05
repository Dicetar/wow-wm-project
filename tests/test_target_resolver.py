from __future__ import annotations

import unittest
from pathlib import Path

from wm.targets.resolver import LookupStore, TargetResolver


class TargetResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        lookup_path = Path("data/lookup/sample_creature_template_full.json")
        cls.store = LookupStore.from_json(lookup_path)
        cls.resolver = TargetResolver(store=cls.store)

    def test_resolves_bethor(self) -> None:
        profile = self.resolver.resolve_creature_entry(1498)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.name, "Bethor Iceshard")
        self.assertEqual(profile.mechanical_type, "HUMANOID")
        self.assertEqual(profile.faction_id, 68)
        self.assertEqual(profile.faction_label, "Undercity / Forsaken")
        self.assertEqual(profile.service_roles, ["QUEST_GIVER"])
        self.assertFalse(profile.has_gossip_menu)

    def test_resolves_timber_wolf(self) -> None:
        profile = self.resolver.resolve_creature_entry(69)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.mechanical_type, "BEAST")
        self.assertEqual(profile.family, "WOLF")
        self.assertEqual(profile.service_roles, [])

    def test_resolves_guard_gossip(self) -> None:
        profile = self.resolver.resolve_creature_entry(68)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.service_roles, ["GOSSIP"])
        self.assertTrue(profile.has_gossip_menu)

    def test_unknown_entry_returns_none(self) -> None:
        profile = self.resolver.resolve_creature_entry(999999)
        self.assertIsNone(profile)


if __name__ == "__main__":
    unittest.main()
