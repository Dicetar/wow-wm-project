from __future__ import annotations

import unittest

from wm.character.eligibility import build_journey_eligibility
from wm.character.models import (
    ArcState,
    CharacterProfile,
    CharacterUnlock,
    ConversationSteeringNote,
    PromptQueueEntry,
    RewardInstance,
)
from wm.character.reader import CharacterStateBundle


class CharacterEligibilityTests(unittest.TestCase):
    def test_builds_ready_snapshot_from_character_bundle(self) -> None:
        bundle = CharacterStateBundle(
            profile=CharacterProfile(character_guid=5406, character_name="Jecia"),
            arc_states=[
                ArcState(character_guid=5406, arc_key="wild_arc", stage_key="active"),
                ArcState(character_guid=5406, arc_key="old_arc", stage_key="done", status="completed"),
            ],
            unlocks=[
                CharacterUnlock(character_guid=5406, unlock_kind="shell_spell", unlock_id=940001),
                CharacterUnlock(character_guid=5406, unlock_kind="combat_proficiency", unlock_id=118),
            ],
            rewards=[RewardInstance(character_guid=5406, reward_kind="item", template_id=910006)],
            conversation_steering=[
                ConversationSteeringNote(
                    character_guid=5406,
                    steering_key="wild_powers_visible_first",
                    body="Prefer visible powers.",
                )
            ],
            prompt_queue=[
                PromptQueueEntry(character_guid=5406, prompt_kind="roadmap_branch_choice", body="Pick a branch.")
            ],
            status="WORKING",
        )

        snapshot = build_journey_eligibility(bundle)

        self.assertTrue(snapshot.ready_for_arc_factory)
        self.assertTrue(snapshot.has_active_arc("wild_arc"))
        self.assertTrue(snapshot.has_unlock("shell_spell", 940001))
        self.assertTrue(snapshot.has_reward("item", 910006))
        self.assertEqual(snapshot.completed_arc_keys, ["old_arc"])
        self.assertEqual(snapshot.steering_keys, ["wild_powers_visible_first"])
        self.assertEqual(snapshot.prompt_kinds, ["roadmap_branch_choice"])
        self.assertEqual(snapshot.to_dict()["ready_for_arc_factory"], True)

    def test_missing_profile_blocks_arc_factory(self) -> None:
        snapshot = build_journey_eligibility({"status": "PARTIAL", "notes": ["No profile"]})

        self.assertFalse(snapshot.ready_for_arc_factory)
        self.assertIn("profile_missing", snapshot.blocked_reasons)
        self.assertIn("No profile", snapshot.blocked_reasons)

    def test_accepts_dict_shape_from_context_pack(self) -> None:
        snapshot = build_journey_eligibility(
            {
                "status": "WORKING",
                "profile": {"character_guid": 5406, "character_name": "Jecia"},
                "arc_states": [{"arc_key": "wild_arc", "status": "active"}],
                "unlocks": [{"unlock_kind": "shell_spell", "unlock_id": "940001"}],
                "reward_instances": [{"reward_kind": "item", "template_id": "910006"}],
                "conversation_steering": [{"steering_key": "active", "is_active": "1"}],
                "prompt_queue": [{"prompt_kind": "pending", "is_consumed": "0"}],
            }
        )

        self.assertTrue(snapshot.ready_for_arc_factory)
        self.assertTrue(snapshot.has_unlock("shell_spell", 940001))
        self.assertTrue(snapshot.has_reward("item", 910006))
        self.assertEqual(snapshot.steering_keys, ["active"])
        self.assertEqual(snapshot.prompt_kinds, ["pending"])


if __name__ == "__main__":
    unittest.main()
