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
from wm.character.reader import CharacterStateBundle
from wm.journal.models import JournalCounters, JournalEvent, SubjectCard
from wm.journal.reader import SubjectJournalBundle
from wm.journal.summarizer import summarize_subject_journal
from wm.prompt.package import build_prompt_package
from wm.targets.resolver import TargetProfile


class PromptPackageTests(unittest.TestCase):
    def test_build_prompt_package(self) -> None:
        target_profile = TargetProfile(
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
        character_state = CharacterStateBundle(
            profile=CharacterProfile(character_guid=42, character_name="Aldren"),
            arc_states=[ArcState(character_guid=42, arc_key="arc_a", stage_key="stage_1")],
            unlocks=[CharacterUnlock(character_guid=42, unlock_kind="spell", unlock_id=900001)],
            rewards=[RewardInstance(character_guid=42, reward_kind="item", template_id=910101)],
            conversation_steering=[
                ConversationSteeringNote(character_guid=42, steering_key="visible_first", body="Prefer visible effects.")
            ],
            prompt_queue=[PromptQueueEntry(character_guid=42, prompt_kind="branch_choice", body="How do you proceed?")],
        )
        subject = SubjectCard(subject_name="Grey Wolf", short_description="Shabby looking wild beast")
        counters = JournalCounters(kill_count=18, skin_count=10)
        events = [JournalEvent(event_type="note", event_value="The beast is becoming familiar.")]
        summary = summarize_subject_journal(subject, counters, events)
        subject_journal = SubjectJournalBundle(
            subject_id=1,
            subject_card=subject,
            counters=counters,
            events=events,
            summary=summary,
        )

        package = build_prompt_package(
            character_guid=42,
            target_entry=46,
            target_profile=target_profile,
            character_state=character_state,
            subject_journal=subject_journal,
        )
        data = package.to_dict()

        self.assertEqual(data["character_guid"], 42)
        self.assertEqual(data["target_entry"], 46)
        self.assertEqual(data["target_profile"]["name"], "Murloc Forager")
        self.assertEqual(data["character_profile"]["character_name"], "Aldren")
        self.assertEqual(data["conversation_steering"][0]["steering_key"], "visible_first")
        self.assertEqual(data["journal_summary"]["title"], "Grey Wolf")
        self.assertIn("Player killed 18", data["journal_summary"]["history_lines"])


if __name__ == "__main__":
    unittest.main()
