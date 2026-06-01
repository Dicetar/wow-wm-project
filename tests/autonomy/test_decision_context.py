from __future__ import annotations

from wm.autonomy.decision_context import build_decision_context


def _world_context():
    return {
        "speaker": {"guid": 5408, "name": "Astel"},
        "live_location": {"zone_name": "Westfall", "area_name": "Sentinel Hill", "zone_id": 40,
                          "area_id": 108, "fresh": True, "in_combat": False, "level": 13, "online": 1},
        "perception": {"creature_count": 7, "gameobject_count": 2, "detail_note": "x"},
    }


def _pack():
    return {
        "profile": {"character_name": "Astel", "wm_persona": "stern"},
        "arc_states": [{"arc_key": "undead", "stage_key": "beat1"}],
        "unlocks": [{"unlock_key": "u1"}],
        "conversation_steering": [{"steering_key": "prefers_undead", "body": "likes undead"}],
    }


def test_assembles_bounded_packet():
    ctx = build_decision_context(
        player_guid=5408, world_context=_world_context(), session_context_pack=_pack(),
        recent_events=[{"event_type": "kill", "subject_entry": 100, "occurred_at": "t1"}],
        journal_summary="Astel has slain many wolves.",
    )
    assert ctx["schema_version"] == "wm.autonomy.decision_context.v1"
    assert ctx["player_guid"] == 5408
    assert ctx["player"]["name"] == "Astel"
    assert ctx["location"]["zone_name"] == "Westfall" and ctx["location"]["fresh"] is True
    assert ctx["nearby"] == {"creatures": 7, "objects": 2}
    assert ctx["character_state"]["arc_states"][0]["arc_key"] == "undead"
    assert ctx["recent_events"][0]["type"] == "kill"
    assert ctx["journal_summary"] == "Astel has slain many wolves."


def test_caps_lists_and_summary():
    events = [{"event_type": "kill", "occurred_at": f"t{i}"} for i in range(50)]
    ctx = build_decision_context(
        player_guid=5408, world_context=_world_context(), session_context_pack=_pack(),
        recent_events=events, journal_summary="x" * 5000,
    )
    assert len(ctx["recent_events"]) == 8
    assert len(ctx["journal_summary"]) == 600


def test_tolerates_missing_pieces():
    ctx = build_decision_context(player_guid=5408)
    assert ctx["player_guid"] == 5408
    assert ctx["location"]["zone_name"] is None
    assert ctx["recent_events"] == []
    assert ctx["journal_summary"] is None
    assert ctx["character_state"]["arc_states"] == []


def test_event_objects_with_to_dict_supported():
    class Evt:
        def to_dict(self):
            return {"event_type": "level_up", "event_value": "14", "occurred_at": "t"}
    ctx = build_decision_context(player_guid=5408, recent_events=[Evt()])
    assert ctx["recent_events"][0]["type"] == "level_up"
    assert ctx["recent_events"][0]["value"] == "14"
