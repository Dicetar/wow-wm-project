from unittest.mock import patch
import unittest

from wm.events.models import WMEvent
from wm.events.rules import DeterministicRuleEngine
from wm.journal.models import JournalCounters
from wm.journal.models import JournalSummary
from wm.journal.models import SubjectCard
from wm.journal.reader import SubjectJournalBundle


class _DummyClient:
    pass


class FakeRuleStore:
    def __init__(self) -> None:
        self.marked_evaluated: list[int] = []
        self.cooldown_active = False

    def is_evaluated(self, *, event_id: int) -> bool:
        return event_id in self.marked_evaluated

    def mark_evaluated(self, *, event_id: int) -> None:
        self.marked_evaluated.append(event_id)

    def is_cooldown_active(self, key, *, at: str | None = None) -> bool:
        del key, at
        return self.cooldown_active


class DeterministicRuleEngineTests(unittest.TestCase):
    def _bundle(self, *, kill_count: int = 0, talk_count: int = 0) -> SubjectJournalBundle:
        return SubjectJournalBundle(
            subject_id=9001,
            subject_card=SubjectCard(subject_name="Murloc Forager", short_description="A shoreline pest."),
            counters=JournalCounters(kill_count=kill_count, talk_count=talk_count),
            events=[],
            summary=JournalSummary(
                title="Murloc Forager",
                description="A shoreline pest.",
                history_lines=["Player killed 10"],
                raw={"kill_count": kill_count, "talk_count": talk_count},
            ),
        )

    def test_kill_threshold_emits_derived_events_and_opportunity(self) -> None:
        store = FakeRuleStore()
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=None,  # type: ignore[arg-type]
            store=store,
            repeat_kill_threshold=10,
        )
        event = WMEvent(
            event_id=5,
            event_class="observed",
            event_type="kill",
            source="db_poll",
            source_event_key="5",
            occurred_at="2026-04-08 12:00:00",
            player_guid=42,
            subject_type="creature",
            subject_entry=46,
        )

        with patch("wm.events.rules.load_subject_journal_for_creature", return_value=self._bundle(kill_count=10)):
            result = engine.evaluate(event)

        self.assertEqual({item.event_type for item in result.derived_events}, {"repeat_hunt_detected", "followup_eligible"})
        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(result.opportunities[0].rule_type, "repeat_hunt_followup")
        self.assertEqual(store.marked_evaluated, [5])

    def test_cooldown_suppresses_opportunity(self) -> None:
        store = FakeRuleStore()
        store.cooldown_active = True
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=None,  # type: ignore[arg-type]
            store=store,
            repeat_kill_threshold=10,
        )
        event = WMEvent(
            event_id=6,
            event_class="observed",
            event_type="kill",
            source="db_poll",
            source_event_key="6",
            occurred_at="2026-04-08 12:00:00",
            player_guid=42,
            subject_type="creature",
            subject_entry=46,
        )

        with patch("wm.events.rules.load_subject_journal_for_creature", return_value=self._bundle(kill_count=10)):
            result = engine.evaluate(event)

        self.assertEqual(len(result.derived_events), 2)
        self.assertEqual(result.opportunities, [])


if __name__ == "__main__":
    unittest.main()
