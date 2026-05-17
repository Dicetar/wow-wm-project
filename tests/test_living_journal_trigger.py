from __future__ import annotations

import unittest

from wm.journal.models import JournalCounters, SubjectCard
from wm.journal.reader import SubjectJournalBundle
from wm.living.journal_trigger import (
    build_nemesis_trigger_from_journal,
    build_rumor_trigger_from_journal,
    load_subject_journal_counts,
)


class _FakeReader:
    def __init__(self, bundle: SubjectJournalBundle) -> None:
        self._bundle = bundle
        self.calls: list[tuple[int, int]] = []

    def load_for_creature(self, *, player_guid: int, creature_entry: int):
        self.calls.append((player_guid, creature_entry))
        return self._bundle


def _bundle(kill_count: int | None, name: str | None) -> SubjectJournalBundle:
    counters = None if kill_count is None else JournalCounters(kill_count=kill_count)
    card = None if name is None else SubjectCard(subject_name=name)
    return SubjectJournalBundle(
        subject_id=1 if name else None,
        subject_card=card,
        counters=counters,
        events=[],
        summary=None,
        status="WORKING" if name else "UNKNOWN",
    )


class JournalTriggerTests(unittest.TestCase):
    def test_counts_and_name_from_bundle(self) -> None:
        reader = _FakeReader(_bundle(12, "Murloc Forager"))
        kills, name = load_subject_journal_counts(reader=reader, player_guid=5406, subject_entry=46)
        self.assertEqual(kills, 12)
        self.assertEqual(name, "Murloc Forager")
        self.assertEqual(reader.calls, [(5406, 46)])

    def test_missing_counters_degrade_to_zero(self) -> None:
        kills, name = load_subject_journal_counts(
            reader=_FakeReader(_bundle(None, None)), player_guid=5406, subject_entry=46
        )
        self.assertEqual(kills, 0)
        self.assertIsNone(name)

    def test_nemesis_trigger_uses_journal_kill_count(self) -> None:
        t = build_nemesis_trigger_from_journal(
            reader=_FakeReader(_bundle(25, "Defias Thug")),
            player_guid=5406,
            subject_entry=99,
            player_name="Jecia",
        )
        self.assertEqual(t.kill_count, 25)
        self.assertEqual(t.subject_name, "Defias Thug")
        self.assertEqual(t.subject_entry, 99)

    def test_nemesis_trigger_explicit_name_overrides_journal(self) -> None:
        t = build_nemesis_trigger_from_journal(
            reader=_FakeReader(_bundle(5, "Journal Name")),
            player_guid=1,
            subject_entry=2,
            subject_name="Override",
        )
        self.assertEqual(t.subject_name, "Override")

    def test_nemesis_trigger_fallback_name_when_unknown(self) -> None:
        t = build_nemesis_trigger_from_journal(
            reader=_FakeReader(_bundle(None, None)), player_guid=1, subject_entry=7
        )
        self.assertEqual(t.subject_name, "creature:7")
        self.assertEqual(t.kill_count, 0)

    def test_rumor_trigger_from_journal(self) -> None:
        t = build_rumor_trigger_from_journal(
            reader=_FakeReader(_bundle(8, "Kobold")),
            player_guid=5406,
            player_name="Jecia",
            subject_entry=12,
            zone_name="Elwynn",
        )
        self.assertEqual(t.deed_count, 8)
        self.assertEqual(t.subject_name, "Kobold")
        self.assertEqual(t.zone_name, "Elwynn")


if __name__ == "__main__":
    unittest.main()
