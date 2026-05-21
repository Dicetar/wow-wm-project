"""Tests for the BridgeEventPump — translates wm_bridge_event rows to runtime events."""
from __future__ import annotations
import json
from wm.cli.bridge_event_pump import BridgeEventPump, BridgeEventRow


class _FakeRuntime:
    """Records calls instead of mutating real state."""
    def __init__(self, character_guid: int):
        self.runner = type("R", (), {"module": type("M", (), {"character_guid": character_guid})})()
        self.use_items: list[int] = []
        self.quest_completions: list[tuple[str, int]] = []
        self.kills: list[tuple[str, str, int]] = []
        self.attentions: list[int] = []
    def feed_use_item(self, *, item_entry: int): self.use_items.append(item_entry)
    def feed_quest_completed(self, *, beat_ref: str, character_level: int = 1):
        self.quest_completions.append((beat_ref, character_level))
    def feed_kill(self, *, creature_family: str, zone: str, ts: int):
        self.kills.append((creature_family, zone, ts))
    def feed_attention(self, *, character_guid: int): self.attentions.append(character_guid)


def _row(eid, etype, **kw) -> BridgeEventRow:
    return BridgeEventRow(
        bridge_event_id=eid, event_family=kw.pop("family", "observed"),
        event_type=etype, player_guid=kw.pop("player_guid", 5407),
        zone_id=kw.pop("zone_id", 12), occurred_at_ts=kw.pop("ts", eid),
        payload=kw.pop("payload", {}),
        object_entry=kw.pop("object_entry", None),
        subject_entry=kw.pop("subject_entry", None),
    )


def test_item_use_dispatches_to_onboarding():
    rt = _FakeRuntime(5407)
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: [
        _row(1, "item_use", payload={"item_entry": 910500}),
    ])
    pump.poll_once()
    assert rt.use_items == [910500]
    assert pump.last_seen_event_id == 1


def test_quest_completed_dispatches_with_beat_ref():
    rt = _FakeRuntime(5407)
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: [
        _row(2, "quest_completed", payload={"beat_ref": "b00_onboarding", "character_level": 1}),
    ])
    pump.poll_once()
    assert rt.quest_completions == [("b00_onboarding", 1)]


def test_kill_dispatches_to_watcher_with_zone():
    rt = _FakeRuntime(5407)
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: [
        _row(3, "kill", payload={"creature_family": "wolf"}, zone_id=12, ts=5),
    ])
    pump.poll_once()
    assert rt.kills == [("wolf", "12", 5)]


def test_other_character_events_ignored():
    rt = _FakeRuntime(5407)
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: [
        _row(4, "item_use", player_guid=9999, payload={"item_entry": 910500}),
    ])
    pump.poll_once()
    assert rt.use_items == []
    # but watermark still advances so we don't reread
    assert pump.last_seen_event_id == 4


def test_watermark_advances_across_polls():
    rt = _FakeRuntime(5407)
    batches = iter([
        [_row(10, "kill", payload={"creature_family": "wolf"}, ts=1)],
        [_row(11, "kill", payload={"creature_family": "wolf"}, ts=2)],
        [],
    ])
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: next(batches))
    pump.poll_once(); pump.poll_once(); pump.poll_once()
    assert pump.last_seen_event_id == 11
    assert len(rt.kills) == 2


def test_unknown_event_type_skipped_quietly():
    rt = _FakeRuntime(5407)
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: [
        _row(5, "weather_changed", payload={}),
    ])
    pump.poll_once()  # must not crash
    assert pump.last_seen_event_id == 5


def test_marker_aura_applied_fires_attention():
    rt = _FakeRuntime(5408)
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: [
        _row(42929, "applied", family="aura", player_guid=5408,
             payload={"spell_id": 946500, "player_guid": 5408}),
    ])
    pump.poll_once()
    assert rt.attentions == [5408]
    assert pump.last_seen_event_id == 42929


def test_non_marker_aura_applied_ignored():
    rt = _FakeRuntime(5408)
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: [
        _row(50, "applied", family="aura", player_guid=5408,
             payload={"spell_id": 12345}),
    ])
    pump.poll_once()
    assert rt.attentions == []
    assert pump.last_seen_event_id == 50


def test_marker_aura_fires_attention_only_once_per_character():
    rt = _FakeRuntime(5408)
    batches = iter([
        [_row(42929, "applied", family="aura", player_guid=5408,
              payload={"spell_id": 946500})],
        # a later poll re-observes a marker apply for the same char (replay/re-cast)
        [_row(42999, "applied", family="aura", player_guid=5408,
              payload={"spell_id": 946500})],
    ])
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: next(batches))
    pump.poll_once(); pump.poll_once()
    assert rt.attentions == [5408]  # one-shot guard


def test_marker_aura_for_other_character_ignored():
    rt = _FakeRuntime(5408)
    pump = BridgeEventPump(runtime=rt, fetch=lambda after: [
        _row(60, "applied", family="aura", player_guid=9999,
             payload={"spell_id": 946500}),
    ])
    pump.poll_once()
    assert rt.attentions == []
