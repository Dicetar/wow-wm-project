import json
from pathlib import Path
import pytest
from wm.arcs.story_module import (
    StoryModule, Beat, BeatKind, parse_story_module, ValidationError,
)

_VALID = {
    "schema": "wm.story_module.v1",
    "module_id": "demo_one_v1",
    "character_guid": 5407,
    "character_name": "Demo One",
    "premise": "A new soul takes notice of the WM's regard.",
    "tone": "somber",
    "constraints": {
        "zone_whitelist": [1],
        "level_band": [1, 5],
        "id_ranges": {"quest": [910500, 910599]},
        "ability_themes": ["shadow_warden"],
    },
    "beats": [
        {"id": "b00", "kind": "PINNED",
         "entry_condition": {"event": "wm.attention.granted"},
         "payload": {"quest_release": {"title": "Pinned hook"}},
         "outcome": {"next_beat_ref": "b01", "grant_points": []}},
        {"id": "b01", "kind": "OPEN",
         "entry_condition": {"event": "quest.completed", "ref": "b00"},
         "intent": "Investigate the noise in the woods.",
         "constraints": {"max_objectives": 2},
         "outcome": {
             "next_beat_ref": None,
             "grant_points": [
                 {"grant_kind": "ability", "ability_ref": "shadow_pulse_aura_v1",
                  "when": {"event": "quest.completed", "ref": "b01"},
                  "appropriateness": {"all_of": [{"character_level_at_least": 1}]}}
             ],
         }},
    ],
}

def test_parse_valid_module():
    m = parse_story_module(_VALID)
    assert m.module_id == "demo_one_v1"
    assert len(m.beats) == 2
    assert m.beats[0].kind == BeatKind.PINNED
    assert m.beats[1].kind == BeatKind.OPEN
    assert m.beats[1].outcome.grant_points[0].ability_ref == "shadow_pulse_aura_v1"

def test_rejects_unknown_schema():
    bad = dict(_VALID); bad["schema"] = "wm.other.v1"
    with pytest.raises(ValidationError, match="schema"):
        parse_story_module(bad)

def test_rejects_dangling_beat_ref():
    bad = json.loads(json.dumps(_VALID))
    bad["beats"][0]["outcome"]["next_beat_ref"] = "b99"
    with pytest.raises(ValidationError, match="next_beat_ref"):
        parse_story_module(bad)

def test_rejects_open_beat_without_intent():
    bad = json.loads(json.dumps(_VALID))
    del bad["beats"][1]["intent"]
    with pytest.raises(ValidationError, match="intent"):
        parse_story_module(bad)

def test_rejects_pinned_beat_without_payload():
    bad = json.loads(json.dumps(_VALID))
    del bad["beats"][0]["payload"]
    with pytest.raises(ValidationError, match="payload"):
        parse_story_module(bad)

def test_schema_file_exists_and_self_describes():
    p = Path("control/schemas/wm.story_module.v1.schema.json")
    assert p.exists()
    j = json.loads(p.read_text(encoding="utf-8"))
    assert j["$id"].endswith("wm.story_module.v1")
