"""Tests for CanonicalWMEvent + normalize_native_bridge_event."""
from __future__ import annotations

from datetime import datetime


def test_canonical_event_from_native_bridge_kill():
    from wm.events.normalize import normalize_native_bridge_event, CanonicalWMEvent
    raw = {
        "event_id": 101,
        "event_type": "kill",
        "player_guid": 5406,
        "target_entry": 3100,
        "target_guid": 998877,
        "zone_id": 12,
        "area_id": None,
    }
    event = normalize_native_bridge_event(raw, adapter="native_bridge")
    assert isinstance(event, CanonicalWMEvent)
    assert event.event_type == "kill"
    assert event.player_guid == 5406
    assert event.target_entry == 3100
    assert event.source_adapter == "native_bridge"
    assert isinstance(event.canonical_at, datetime)


def test_canonical_event_subject_entry_defaults_to_target_entry():
    from wm.events.normalize import normalize_native_bridge_event
    raw = {"event_id": 1, "event_type": "kill", "player_guid": 5406,
           "target_entry": 3100, "target_guid": None, "zone_id": 12, "area_id": None}
    event = normalize_native_bridge_event(raw, adapter="native_bridge")
    assert event.subject_entry == 3100


def test_canonical_event_missing_optional_fields_ok():
    from wm.events.normalize import normalize_native_bridge_event
    raw = {"event_id": 2, "event_type": "talk", "player_guid": 5406,
           "target_entry": 1000, "target_guid": None, "zone_id": None, "area_id": None}
    event = normalize_native_bridge_event(raw, adapter="native_bridge")
    assert event.zone_id is None
    assert event.area_id is None
