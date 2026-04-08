import unittest

from wm.events.models import ProjectionResult
from wm.events.models import WMEvent
from wm.events.projector import JournalProjector


class FakeProjectionStore:
    def __init__(self) -> None:
        self.projected_ids: set[int] = set()
        self.inserted_journal_events: list[tuple[int, int, str, str | None]] = []
        self.projection_calls: list[tuple[int, int, str, str | None]] = []
        self.resolved_subject_id = 9001

    def is_projected(self, *, event_id: int) -> bool:
        return event_id in self.projected_ids

    def mark_projected(self, *, event_id: int) -> None:
        self.projected_ids.add(event_id)

    def resolve_subject_id(self, *, subject_type: str, subject_entry: int) -> int | None:
        del subject_type, subject_entry
        return self.resolved_subject_id

    def insert_journal_event(self, *, player_guid: int, subject_id: int, event_type: str, event_value: str | None = None) -> None:
        self.inserted_journal_events.append((player_guid, subject_id, event_type, event_value))

    def apply_journal_projection(
        self,
        *,
        player_guid: int,
        subject_id: int,
        event_type: str,
        event_value: str | None,
        occurred_at: str | None,
    ) -> ProjectionResult:
        del occurred_at
        self.projection_calls.append((player_guid, subject_id, event_type, event_value))
        return ProjectionResult(
            event_id=None,
            status="projected",
            subject_id=subject_id,
            journal_counter_updates={"KillCount": 1} if event_type == "kill" else {},
        )


class JournalProjectorTests(unittest.TestCase):
    def test_projection_writes_journal_history_for_new_observed_event(self) -> None:
        store = FakeProjectionStore()
        projector = JournalProjector(store=store)
        event = WMEvent(
            event_id=11,
            event_class="observed",
            event_type="kill",
            source="manual",
            source_event_key="evt-11",
            occurred_at="2026-04-08 12:00:00",
            player_guid=42,
            subject_type="creature",
            subject_entry=46,
            metadata={},
        )

        result = projector.apply(event)

        self.assertEqual(result.status, "projected")
        self.assertTrue(result.wrote_raw_history)
        self.assertEqual(store.inserted_journal_events, [(42, 9001, "kill", None)])
        self.assertIn(11, store.projected_ids)

    def test_projection_is_replay_safe_for_already_projected_event(self) -> None:
        store = FakeProjectionStore()
        projector = JournalProjector(store=store)
        event = WMEvent(
            event_id=12,
            event_class="observed",
            event_type="kill",
            source="db_poll",
            source_event_key="evt-12",
            occurred_at="2026-04-08 12:00:00",
            player_guid=42,
            subject_type="creature",
            subject_entry=46,
            metadata={"raw_history_exists": True},
        )

        first = projector.apply(event)
        second = projector.apply(event)

        self.assertEqual(first.status, "projected")
        self.assertFalse(first.wrote_raw_history)
        self.assertEqual(second.status, "already_projected")
        self.assertEqual(len(store.projection_calls), 1)
        self.assertEqual(store.inserted_journal_events, [])


if __name__ == "__main__":
    unittest.main()
