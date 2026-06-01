from __future__ import annotations

from wm.autoplay.ambient import (
    AmbientCue,
    build_ambient_messages,
    classify_ambient_event,
)


def _event(**over):
    base = {
        "event_type": "enter_area",
        "player_guid": 5408,
        "zone_id": 40,
        "area_id": 108,
        "subject_type": "area",
        "subject_entry": 108,
        "event_value": "Sentinel Hill",
        "source_event_key": "evt-1",
        "occurred_at": "2026-05-31T12:00:00Z",
    }
    base.update(over)
    return base


def test_enter_area_is_notable():
    cue = classify_ambient_event(_event(event_type="enter_area"))
    assert isinstance(cue, AmbientCue)
    assert cue.kind == "enter_area"
    assert cue.source_event_key == "evt-1"
    assert cue.zone_id == 40
    assert cue.area_id == 108
    assert "Sentinel Hill" in cue.descriptor


def test_quest_completed_and_rewarded_are_notable():
    completed = classify_ambient_event(_event(event_type="quest_completed", event_value="Defend Sentinel Hill"))
    rewarded = classify_ambient_event(_event(event_type="quest_rewarded", event_value="Defend Sentinel Hill"))
    assert completed is not None and completed.kind == "quest_completed"
    assert rewarded is not None and rewarded.kind == "quest_rewarded"
    assert "Defend Sentinel Hill" in completed.descriptor


def test_level_up_is_notable():
    cue = classify_ambient_event(_event(event_type="level_up", event_value="12", subject_type="player"))
    assert cue is not None and cue.kind == "level_up"
    assert cue.descriptor == "reached level 12"


def test_death_is_notable():
    cue = classify_ambient_event(_event(event_type="death", event_value="Westfall", subject_type="player"))
    assert cue is not None and cue.kind == "death"
    assert "Westfall" in cue.descriptor


def test_ordinary_events_are_not_notable():
    # Trash kills, chat, loot, gossip, casts must not trigger ambient narration
    for kind in ("kill", "wm_chat", "loot_item", "talk", "gossip_select", "spell_cast", "quest_accept"):
        assert classify_ambient_event(_event(event_type=kind)) is None


def test_missing_event_type_is_not_notable():
    assert classify_ambient_event({"player_guid": 5408}) is None
    assert classify_ambient_event(None) is None


def test_build_ambient_messages_shapes_prompt():
    cue = classify_ambient_event(_event())
    identity = {"character_name": "Astel", "zone_name": "Westfall", "area_name": "Sentinel Hill"}
    messages = build_ambient_messages(cue, identity)
    assert isinstance(messages, list) and messages
    system = messages[0]
    assert system["role"] == "system"
    # The narrator must be constrained: short, in-world, no fabricated rewards
    assert "World Master" in system["content"]
    assert "one" in system["content"].lower()
    # The cue + identity travel in the user turn as structured context
    user = messages[-1]
    assert user["role"] == "user"
    assert "enter_area" in user["content"]
    assert "Astel" in user["content"]
