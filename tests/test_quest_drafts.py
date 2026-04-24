from __future__ import annotations

import unittest

from wm.quests.bounty import build_default_bounty_reward
from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.compiler import compile_bounty_quest_sql_plan
from wm.quests.validator import validate_bounty_quest_draft
from wm.targets.resolver import TargetProfile


class BountyQuestDraftTests(unittest.TestCase):
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

    def test_build_bounty_draft_uses_target_profile(self) -> None:
        draft = build_bounty_quest_draft(
            quest_id=910001,
            questgiver_entry=1498,
            questgiver_name="Bethor Iceshard",
            target_profile=self._target(),
            kill_count=8,
            reward_money_copper=1200,
        )
        self.assertEqual(draft.objective.target_entry, 46)
        self.assertEqual(draft.objective.kill_count, 8)
        self.assertIn("Murloc Forager", draft.title)
        self.assertIn("bounty", draft.tags)
        self.assertEqual(draft.template_defaults["SpecialFlags"], 1)

    def test_bounty_draft_preserves_existing_special_flags_while_forcing_repeatable(self) -> None:
        draft = build_bounty_quest_draft(
            quest_id=910004,
            questgiver_entry=1498,
            questgiver_name="Bethor Iceshard",
            target_profile=self._target(),
            template_defaults={"SpecialFlags": 16, "QuestType": 2},
        )

        self.assertEqual(draft.template_defaults["SpecialFlags"], 17)
        self.assertEqual(draft.template_defaults["QuestType"], 2)

    def test_default_bounty_reward_scales_money_and_adds_supply_box(self) -> None:
        reward = build_default_bounty_reward(quest_level=25)

        self.assertEqual(reward.money_copper, 2500)
        self.assertEqual(reward.reward_item_entry, 6827)
        self.assertEqual(reward.reward_item_name, "Box of Supplies")
        self.assertEqual(reward.reward_item_count, 1)
        self.assertEqual(reward.reward_xp_difficulty, 5)

    def test_validator_flags_invalid_ranges(self) -> None:
        draft = build_bounty_quest_draft(
            quest_id=10,
            questgiver_entry=1498,
            questgiver_name="Bethor Iceshard",
            target_profile=self._target(),
            kill_count=30,
            reward_money_copper=1000001,
        )
        result = validate_bounty_quest_draft(draft)
        self.assertFalse(result.ok)
        self.assertTrue(any(issue.path == "objective.kill_count" for issue in result.errors))
        self.assertTrue(any(issue.path == "reward.money_copper" for issue in result.errors))
        self.assertTrue(any(issue.path == "quest_id" and issue.severity == "warning" for issue in result.issues))

    def test_compiler_escapes_sql_quotes(self) -> None:
        draft = build_bounty_quest_draft(
            quest_id=910002,
            questgiver_entry=1498,
            questgiver_name="Bethor Iceshard",
            target_profile=self._target(),
            kill_count=6,
            reward_money_copper=800,
        )
        draft.title = "Bounty: Murloc Forager's End"
        plan = compile_bounty_quest_sql_plan(draft)
        joined = "\n".join(plan.statements)
        self.assertIn("Murloc Forager''s End", joined)
        self.assertIn("INSERT INTO quest_template", joined)
        self.assertIn("INSERT INTO creature_queststarter", joined)
        self.assertIn("LogDescription", joined)
        self.assertIn("QuestCompletionLog", joined)

    def test_direct_grant_bounty_omits_starter_and_keeps_ender(self) -> None:
        draft = build_bounty_quest_draft(
            quest_id=910003,
            questgiver_entry=197,
            questgiver_name="Marshal McBride",
            target_profile=self._target(),
            kill_count=4,
            reward_money_copper=800,
            start_npc_entry=None,
            end_npc_entry=197,
            grant_mode="direct_quest_add",
        )
        self.assertIsNone(draft.start_npc_entry)
        self.assertEqual(draft.end_npc_entry, 197)
        plan = compile_bounty_quest_sql_plan(
            draft,
            available_tables={"quest_template_addon"},
            quest_template_addon_columns={"ID", "SpecialFlags"},
        )
        joined = "\n".join(plan.statements)
        self.assertNotIn("INSERT INTO creature_queststarter", joined)
        self.assertIn("INSERT INTO creature_questender", joined)
        self.assertIn("INSERT INTO quest_template_addon (ID, SpecialFlags) VALUES (910003, 1);", joined)


if __name__ == "__main__":
    unittest.main()
