from __future__ import annotations

import unittest

from wm.journal.models import JournalCounters, JournalEvent, SubjectCard
from wm.journal.summarizer import format_summary_markdown, summarize_subject_journal


class JournalSummarizerTests(unittest.TestCase):
    def test_stieve_summary_contains_training_and_quest(self) -> None:
        subject = SubjectCard(
            subject_name="Stieve",
            short_description="Miner living in Goldshire",
        )
        counters = JournalCounters(
            talk_count=2,
            quest_complete_count=1,
            last_quest_title="A Miner's Burden",
        )
        events = [JournalEvent(event_type="trainer_learn", event_value="Mining")]

        summary = summarize_subject_journal(subject, counters, events)
        text = format_summary_markdown(summary)

        self.assertIn("Stieve", text)
        self.assertIn("Miner living in Goldshire", text)
        self.assertIn('Player completed quest: "A Miner\'s Burden"', text)
        self.assertIn("Player learned Mining from Stieve", text)

    def test_wolf_summary_contains_kill_skin_and_feed(self) -> None:
        subject = SubjectCard(
            subject_name="Grey Wolf",
            short_description="Shabby looking wild beast",
        )
        counters = JournalCounters(kill_count=18, skin_count=10, feed_count=1)
        events = [
            JournalEvent(event_type="feed_trigger_quest", event_value="A Cautious Truce")
        ]

        summary = summarize_subject_journal(subject, counters, events)
        text = format_summary_markdown(summary)

        self.assertIn("Player killed 18", text)
        self.assertIn("Player skinned 10", text)
        self.assertIn("Player fed Grey Wolf 1 time(s)", text)
        self.assertIn('Player fed Grey Wolf and unlocked quest: "A Cautious Truce"', text)


if __name__ == "__main__":
    unittest.main()
