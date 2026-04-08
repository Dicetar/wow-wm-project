from __future__ import annotations

from wm.events.models import ProjectionResult
from wm.events.models import WMEvent
from wm.events.store import EventStore


class JournalProjector:
    def __init__(self, *, store: EventStore) -> None:
        self.store = store

    def apply(self, event: WMEvent) -> ProjectionResult:
        if event.event_class != "observed":
            return ProjectionResult(
                event_id=event.event_id,
                status="skipped",
                note="Only observed events are projected into journal memory.",
            )

        if event.event_id is not None and self.store.is_projected(event_id=event.event_id):
            return ProjectionResult(
                event_id=event.event_id,
                status="already_projected",
                note="Canonical event was already projected.",
            )

        if event.player_guid is None or event.subject_type is None or event.subject_entry is None:
            if event.event_id is not None:
                self.store.mark_projected(event_id=event.event_id)
            return ProjectionResult(
                event_id=event.event_id,
                status="missing_subject",
                note="Event is missing the player or subject fields required for journal projection.",
            )

        subject_id = _subject_id_from_metadata(event)
        if subject_id is None:
            subject_id = self.store.resolve_subject_id(
                subject_type=event.subject_type,
                subject_entry=event.subject_entry,
            )
        if subject_id is None:
            if event.event_id is not None:
                self.store.mark_projected(event_id=event.event_id)
            return ProjectionResult(
                event_id=event.event_id,
                status="missing_subject",
                note="Could not resolve the subject into wm_subject_definition.",
            )

        wrote_raw_history = False
        if not bool(event.metadata.get("raw_history_exists")):
            self.store.insert_journal_event(
                player_guid=event.player_guid,
                subject_id=subject_id,
                event_type=event.event_type,
                event_value=event.event_value,
            )
            wrote_raw_history = True

        projection = self.store.apply_journal_projection(
            player_guid=event.player_guid,
            subject_id=subject_id,
            event_type=event.event_type,
            event_value=event.event_value,
            occurred_at=event.occurred_at,
        )
        projection.event_id = event.event_id
        projection.wrote_raw_history = wrote_raw_history
        if event.event_id is not None:
            self.store.mark_projected(event_id=event.event_id)
        return projection


def _subject_id_from_metadata(event: WMEvent) -> int | None:
    raw_value = event.metadata.get("journal_subject_id")
    if raw_value in (None, ""):
        return None
    return int(raw_value)
