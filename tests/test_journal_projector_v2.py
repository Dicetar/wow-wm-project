"""Tests for project_event (Phase 2 projector API)."""
from __future__ import annotations


def test_projector_calls_writer_for_kill_event():
    from wm.journal.projector import project_event

    increments = []

    class MockWriter:
        def increment_counter(self, player_guid, subject_entry, counter_key, delta=1):
            increments.append((player_guid, subject_entry, counter_key))

    event = {
        "event_id": 1, "event_type": "kill",
        "player_guid": 5406, "target_entry": 3100,
    }
    project_event(event, writer=MockWriter())
    assert (5406, 3100, "kills") in increments


def test_projector_skips_non_journalable_event():
    from wm.journal.projector import project_event

    increments = []

    class MockWriter:
        def increment_counter(self, *args, **kwargs):
            increments.append(args)

    project_event({"event_id": 1, "event_type": "loot",
                   "player_guid": 5406, "target_entry": 3100},
                  writer=MockWriter())
    assert len(increments) == 0
