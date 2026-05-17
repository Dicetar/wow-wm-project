from __future__ import annotations

import json
import unittest

from wm.living.nemesis import (
    NemesisConfig,
    NemesisTrigger,
    build_nemesis_plan,
    evaluate_nemesis,
)
from wm.sources.native_bridge.payload_contract import validate_native_action_payload


def _trigger(kills: int) -> NemesisTrigger:
    return NemesisTrigger(
        player_guid=5406,
        subject_entry=46,
        subject_name="Murloc Forager",
        kill_count=kills,
        player_name="Jecia",
        turn_in_npc_entry=197,
    )


class NemesisDecisionTests(unittest.TestCase):
    def test_below_threshold_not_eligible_no_plan(self) -> None:
        d = evaluate_nemesis(_trigger(9))
        self.assertFalse(d.eligible)
        self.assertIsNone(d.plan)
        self.assertIn("not yet awakened", d.reason)

    def test_at_threshold_eligible_with_plan(self) -> None:
        d = evaluate_nemesis(_trigger(10))
        self.assertTrue(d.eligible)
        self.assertIsNotNone(d.plan)
        self.assertEqual(d.contract_issues, [])

    def test_custom_threshold_respected(self) -> None:
        d = evaluate_nemesis(_trigger(4), NemesisConfig(kill_threshold=4))
        self.assertTrue(d.eligible)


class NemesisPlanContractTests(unittest.TestCase):
    def test_every_scene_step_is_contract_valid(self) -> None:
        plan, issues = build_nemesis_plan(_trigger(12))
        self.assertEqual(issues, [])
        for step in plan.scene_steps:
            self.assertEqual(
                validate_native_action_payload(
                    action_kind=step["native_action_kind"], payload=step["payload"]
                ),
                [],
                f"{step['native_action_kind']} payload violates its contract",
            )

    def test_every_followup_step_carries_arc_key_scope(self) -> None:
        plan, _ = build_nemesis_plan(_trigger(12))
        for step in plan.scene_steps:
            self.assertEqual(step["payload"].get("arc_key"), plan.arc_key)

    def test_scene_uses_batch1_verbs(self) -> None:
        plan, _ = build_nemesis_plan(_trigger(12))
        kinds = [s["native_action_kind"] for s in plan.scene_steps]
        for expected in (
            "creature_spawn",
            "creature_set_name",
            "creature_set_faction",
            "creature_set_health_pct",
            "creature_yell",
            "creature_attack_player",
        ):
            self.assertIn(expected, kinds)

    def test_native_readiness_reports_pending_cpp_honestly(self) -> None:
        plan, _ = build_nemesis_plan(_trigger(12))
        nr = plan.native_readiness
        # creature_spawn is implemented today; the rest are lab-gated.
        self.assertIn("creature_spawn", nr["implemented"])
        self.assertIn("creature_set_name", nr["not_implemented"])
        self.assertFalse(nr["live_ready"])

    def test_revenge_bounty_spec_shape(self) -> None:
        plan, _ = build_nemesis_plan(_trigger(11))
        rb = plan.revenge_bounty
        self.assertEqual(rb["subject_entry"], 46)
        self.assertEqual(rb["kill_threshold"], 1)
        self.assertTrue(rb["requires_slot_allocation"])
        self.assertIsNone(rb["quest_id"])
        self.assertTrue(rb["metadata"]["nemesis"])

    def test_deterministic_identity(self) -> None:
        a, _ = build_nemesis_plan(_trigger(15))
        b, _ = build_nemesis_plan(_trigger(15))
        self.assertEqual(a.arc_key, b.arc_key)
        self.assertEqual(a.nemesis_name, b.nemesis_name)
        self.assertEqual(a.arc_key, "nemesis:5406:46")

    def test_decision_json_serializable(self) -> None:
        json.dumps(evaluate_nemesis(_trigger(20)).to_dict())


if __name__ == "__main__":
    unittest.main()
