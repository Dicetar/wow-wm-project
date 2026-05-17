from __future__ import annotations

import json
import unittest

from wm.living.oath import OathTrigger, evaluate_oath
from wm.sources.native_bridge.payload_contract import validate_native_action_payload


def _t(**kw) -> OathTrigger:
    base = dict(
        player_guid=5406,
        player_name="Jecia",
        oath_key="no_death",
        constraint_label="no deaths for 20 kills",
        target_count=20,
    )
    base.update(kw)
    return OathTrigger(**base)


def _assert_contract_valid(plan) -> None:
    for step in plan.scene_steps:
        assert validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"]) == []


class OathTests(unittest.TestCase):
    def test_accept_phase_initializes_counter(self) -> None:
        d = evaluate_oath(_t(phase="accept"))
        self.assertTrue(d.eligible)
        kinds = [s["native_action_kind"] for s in d.plan.scene_steps]
        self.assertIn("wm_counter_set", kinds)
        self.assertIsNone(d.plan.outcome)
        _assert_contract_valid(d.plan)

    def test_resolve_kept_grants_reward(self) -> None:
        d = evaluate_oath(_t(phase="resolve", current_count=20))
        self.assertEqual(d.plan.outcome, "kept")
        self.assertTrue(d.plan.reward_refs)
        _assert_contract_valid(d.plan)

    def test_resolve_broken_fails_quest_when_id_present(self) -> None:
        d = evaluate_oath(_t(phase="resolve", current_count=5, oath_quest_id=910500))
        self.assertEqual(d.plan.outcome, "broken")
        self.assertIn("quest_fail", [s["native_action_kind"] for s in d.plan.scene_steps])
        self.assertEqual(d.plan.reward_refs, [])
        _assert_contract_valid(d.plan)

    def test_resolve_broken_without_quest_id_skips_quest_fail(self) -> None:
        d = evaluate_oath(_t(phase="resolve", current_count=5))
        kinds = [s["native_action_kind"] for s in d.plan.scene_steps]
        self.assertNotIn("quest_fail", kinds)
        self.assertIn("wm_counter_clear", kinds)

    def test_invalid_phase_and_target(self) -> None:
        self.assertFalse(evaluate_oath(_t(phase="bogus")).eligible)
        self.assertFalse(evaluate_oath(_t(target_count=0)).eligible)

    def test_json(self) -> None:
        json.dumps(evaluate_oath(_t(phase="resolve", current_count=25)).to_dict())


if __name__ == "__main__":
    unittest.main()
