"""Tests for apply_journal_write in events/watch.py."""
from __future__ import annotations


def test_watch_calls_journal_on_kill_event():
    increments = []

    class MockJournalWriter:
        def increment_counter(self, player_guid, subject_entry, counter_key, delta=1):
            increments.append((player_guid, subject_entry, counter_key, delta))

    from wm.events.watch import apply_journal_write
    fake_event = type("Event", (), {
        "player_guid": 5406,
        "target_entry": 3100,
        "event_type": "kill",
    })()
    apply_journal_write(fake_event, MockJournalWriter())
    assert len(increments) == 1
    assert increments[0] == (5406, 3100, "kills", 1)


def test_non_journalable_event_skipped():
    increments = []

    class MockJournalWriter:
        def increment_counter(self, *args, **kwargs):
            increments.append(args)

    from wm.events.watch import apply_journal_write
    fake_event = type("Event", (), {
        "player_guid": 5406,
        "target_entry": 3100,
        "event_type": "loot",  # not in JOURNALABLE_EVENTS
    })()
    apply_journal_write(fake_event, MockJournalWriter())
    assert len(increments) == 0


def test_event_without_player_guid_skipped():
    increments = []

    class MockJournalWriter:
        def increment_counter(self, *args, **kwargs):
            increments.append(args)

    from wm.events.watch import apply_journal_write
    fake_event = type("Event", (), {
        "player_guid": None,
        "target_entry": 3100,
        "event_type": "kill",
    })()
    apply_journal_write(fake_event, MockJournalWriter())
    assert len(increments) == 0
