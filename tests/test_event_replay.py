"""Tests for ReplayResult + replay_event_range."""
from __future__ import annotations


def test_replay_result_structure():
    from wm.events.replay import ReplayResult
    result = ReplayResult(from_event_id=0, to_event_id=10, events_processed=3,
                          would_trigger=["reactive_bounty:wolf_slayer"],
                          dry_run=True)
    assert result.events_processed == 3
    assert result.dry_run is True


def test_replay_range_dry_run_does_not_write():
    from wm.events.replay import replay_event_range

    class MockDB:
        def query(self, sql, params=None):
            return [
                {"event_id": 1, "event_type": "kill", "player_guid": 5406,
                 "target_entry": 3100, "target_guid": None,
                 "zone_id": 12, "area_id": None},
            ]
        def execute(self, sql, params=None):
            raise AssertionError("dry_run must not call db.execute()")

    result = replay_event_range(from_event_id=0, to_event_id=5,
                                db_client=MockDB(), dry_run=True)
    assert result.dry_run is True
    assert result.events_processed == 1
