from __future__ import annotations

import unittest

from wm.character.models import (
    ArcState,
    CharacterProfile,
    CharacterUnlock,
    ConversationSteeringNote,
    PromptQueueEntry,
    RewardInstance,
)


class CharacterStateModelTests(unittest.TestCase):
    def test_profile_defaults(self) -> None:
        profile = CharacterProfile(character_guid=1, character_name="Test")
        self.assertEqual(profile.wm_persona, "default")
        self.assertEqual(profile.tone, "adaptive")
        self.assertEqual(profile.preferred_themes, [])
        self.assertEqual(profile.avoided_themes, [])

    def test_unlock_is_not_bot_eligible_by_default(self) -> None:
        unlock = CharacterUnlock(character_guid=1, unlock_kind="spell", unlock_id=900001)
        self.assertFalse(unlock.bot_eligible)
        self.assertEqual(unlock.grant_method, "control")

    def test_reward_instance_can_represent_equipped_gate(self) -> None:
        reward = RewardInstance(character_guid=1, reward_kind="item", template_id=910101, is_equipped_gate=True)
        self.assertTrue(reward.is_equipped_gate)

    def test_arc_and_prompt_are_constructible(self) -> None:
        arc = ArcState(character_guid=1, arc_key="arc_a", stage_key="stage_1")
        prompt = PromptQueueEntry(character_guid=1, prompt_kind="branch_choice", body="Choose your path")
        self.assertEqual(arc.status, "active")
        self.assertEqual(prompt.prompt_kind, "branch_choice")

    def test_conversation_steering_defaults_to_active_operator_note(self) -> None:
        note = ConversationSteeringNote(character_guid=1, steering_key="tone", body="Prefer direct choices.")
        self.assertTrue(note.is_active)
        self.assertEqual(note.steering_kind, "player_preference")
        self.assertEqual(note.source, "operator")


if __name__ == "__main__":
    unittest.main()
