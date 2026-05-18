"""Tests for JournalWriter — upsert counter + special event insert."""
from __future__ import annotations


def test_writer_increment_generates_correct_sql():
    from wm.journal.writer import JournalWriter

    executed_calls = []

    class MockDB:
        def execute(self, sql, params):
            executed_calls.append((sql, params))

    writer = JournalWriter(db_client=MockDB())
    writer.increment_counter(player_guid=5406, subject_entry=3100,
                             counter_key="kills", delta=1)

    assert len(executed_calls) == 1
    sql, params = executed_calls[0]
    assert "wm_journal_counter" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert params[0] == 5406
    assert params[1] == 3100
    assert params[2] == "kills"
    assert params[3] == 1


def test_writer_record_special_event_generates_insert():
    from wm.journal.writer import JournalWriter

    executed_calls = []

    class MockDB:
        def execute(self, sql, params):
            executed_calls.append((sql, params))
            return 42

    writer = JournalWriter(db_client=MockDB())
    writer.record_special_event(
        player_guid=5406, event_type="first_kill",
        subject_entry=3100, narrative_key="wolf_nemesis_born"
    )
    assert len(executed_calls) == 1
    sql, params = executed_calls[0]
    assert "wm_journal_special_event" in sql
    assert "INSERT" in sql.upper()
    assert 5406 in params
    assert "first_kill" in params


def test_writer_delta_default_is_one():
    from wm.journal.writer import JournalWriter

    deltas = []

    class MockDB:
        def execute(self, sql, params):
            deltas.append(params[3])

    writer = JournalWriter(db_client=MockDB())
    writer.increment_counter(5406, 3100, "kills")
    assert deltas[0] == 1
