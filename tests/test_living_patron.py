from __future__ import annotations

import json
import unittest

from wm.living.patron import PatronConfig, PatronTrigger, build_patron_plan, evaluate_patron
from wm.sources.native_bridge.payload_contract import validate_native_action_payload


class PatronTests(unittest.TestCase):
    def test_zero_completions_not_eligible(self) -> None:
        d = evaluate_patron(PatronTrigger(5406, "Jecia", 0))
        self.assertFalse(d.eligible)

    def test_favor_scales_and_tiers(self) -> None:
        d = evaluate_patron(PatronTrigger(5406, "Jecia", 10))  # 100 favor
        self.assertTrue(d.eligible)
        self.assertEqual(d.plan.favor, 100)
        self.assertEqual(d.plan.tier_name, "Favored")
        self.assertTrue(d.plan.reward_refs)

    def test_below_first_tier_eligible_no_reward(self) -> None:
        d = evaluate_patron(PatronTrigger(5406, "Jecia", 1))  # 10 favor
        self.assertTrue(d.eligible)
        self.assertIsNone(d.plan.tier_name)
        self.assertEqual(d.plan.reward_refs, [])

    def test_plan_contract_valid_and_readiness(self) -> None:
        plan, issues = build_patron_plan(PatronTrigger(5406, "Jecia", 20), PatronConfig())
        self.assertEqual(issues, [])
        for step in plan.scene_steps:
            self.assertEqual(
                validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"]), []
            )
        self.assertIn("wm_counter_set", plan.native_readiness["not_implemented"])
        self.assertFalse(plan.native_readiness["live_ready"])

    def test_json(self) -> None:
        json.dumps(evaluate_patron(PatronTrigger(5406, "Jecia", 20)).to_dict())


if __name__ == "__main__":
    unittest.main()
