from __future__ import annotations

import json
import unittest

from wm.living.legend import LegendTrigger, build_legend_plan, evaluate_legend
from wm.living.legend import LegendConfig, _current_tier
from wm.sources.native_bridge.payload_contract import validate_native_action_payload


def _t(deeds: int) -> LegendTrigger:
    return LegendTrigger(player_guid=5406, player_name="Jecia", zone_name="Westfall", deed_count=deeds)


class LegendTests(unittest.TestCase):
    def test_below_first_tier_not_eligible(self) -> None:
        d = evaluate_legend(_t(10))
        self.assertFalse(d.eligible)
        self.assertIsNone(d.plan)

    def test_tier_selection_is_highest_reached(self) -> None:
        cfg = LegendConfig()
        self.assertEqual(_current_tier(15, cfg).tier_name, "Known")
        self.assertEqual(_current_tier(85, cfg).tier_name, "Local Legend")

    def test_eligible_plan_is_contract_valid(self) -> None:
        d = evaluate_legend(_t(80))
        self.assertTrue(d.eligible)
        self.assertEqual(d.contract_issues, [])
        for step in d.plan.scene_steps:
            self.assertEqual(
                validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"]), []
            )

    def test_native_readiness_honest(self) -> None:
        plan, _ = build_legend_plan(_t(80), LegendConfig().tiers[2])
        nr = plan.native_readiness
        self.assertIn("world_announce_to_player", nr["implemented"])
        self.assertIn("player_add_title", nr["not_implemented"])
        self.assertFalse(nr["live_ready"])

    def test_reward_refs_and_json(self) -> None:
        d = evaluate_legend(_t(40))
        self.assertTrue(any(r.startswith("title:") for r in d.plan.reward_refs))
        json.dumps(d.to_dict())


if __name__ == "__main__":
    unittest.main()
