from __future__ import annotations

import json
import unittest

from wm.living.rumor import RumorConfig, RumorTrigger, build_rumor_plan, evaluate_rumor
from wm.sources.native_bridge.payload_contract import validate_native_action_payload


def _t(deeds: int, zone: str | None = "Westfall") -> RumorTrigger:
    return RumorTrigger(player_guid=5406, player_name="Jecia", subject_name="Defias", deed_count=deeds, zone_name=zone)


class RumorTests(unittest.TestCase):
    def test_below_min_not_eligible(self) -> None:
        d = evaluate_rumor(_t(2))
        self.assertFalse(d.eligible)
        self.assertIsNone(d.plan)

    def test_eligible_and_contract_valid(self) -> None:
        d = evaluate_rumor(_t(5))
        self.assertTrue(d.eligible)
        self.assertEqual(d.contract_issues, [])
        step = d.plan.scene_steps[0]
        self.assertEqual(
            validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"]), []
        )

    def test_live_ready_true(self) -> None:
        plan, _ = build_rumor_plan(_t(5))
        self.assertTrue(plan.native_readiness["live_ready"])
        self.assertIn("world_announce_to_player", plan.native_readiness["implemented"])

    def test_tier_escalation(self) -> None:
        low = build_rumor_plan(_t(3))[0].line
        high = build_rumor_plan(_t(30))[0].line
        self.assertNotEqual(low, high)
        self.assertIn("Jecia", high)
        self.assertIn("Westfall", high)

    def test_deterministic_and_json(self) -> None:
        self.assertEqual(build_rumor_plan(_t(12))[0].line, build_rumor_plan(_t(12))[0].line)
        json.dumps(evaluate_rumor(_t(12)).to_dict())

    def test_custom_min(self) -> None:
        self.assertTrue(evaluate_rumor(_t(1), RumorConfig(min_deeds=1)).eligible)


if __name__ == "__main__":
    unittest.main()
