from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
