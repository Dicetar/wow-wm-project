import json
from pathlib import Path
import pytest
from wm.reactive.reactive_template import (
    ReactiveTemplate, parse_reactive_template, ValidationError,
    match_trigger, EventEnvelope,
)

_VALID = {
    "schema": "wm.reactive_template.v1",
    "id": "zone_kill_bounty",
    "narrative_hook": "WM notices you've been thinning the <creature_family> in <zone>.",
    "trigger": {
        "event": "kill",
        "params": {"creature_family": "<slot>", "zone": "<slot>",
                   "count": {"min": 8, "window_min": 15}},
        "scope": "active_character",
        "cooldown_min": 60,
        "dedupe_key": "zone_kill:{zone}:{creature_family}"
    },
    "recipe": {
        "kind": "quest",
        "compiler": "wm.content.release/repeatable_bounty",
        "slots": {"creature_family": "trigger.creature_family",
                  "zone": "trigger.zone",
                  "reward_theme": "<llm-filled>",
                  "title": "<llm-filled>",
                  "description": "<llm-filled>"}
    },
    "guards": {
        "feasibility_tier": "T1",
        "max_concurrent": 1,
        "idempotency_key_template": "watch:zone_kill_bounty:{character_guid}:{zone}:{creature_family}"
    }
}

def test_parse_valid():
    t = parse_reactive_template(_VALID)
    assert t.id == "zone_kill_bounty"
    assert t.trigger.event == "kill"
    assert t.guards.feasibility_tier == "T1"

def test_rejects_unknown_schema():
    bad = dict(_VALID); bad["schema"] = "x"
    with pytest.raises(ValidationError, match="schema"):
        parse_reactive_template(bad)

def test_match_meets_count_threshold():
    t = parse_reactive_template(_VALID)
    events = [
        EventEnvelope(kind="kill", character_guid=5407, params={"creature_family": "murloc", "zone": "elwynn"}, ts=i)
        for i in range(8)
    ]
    m = match_trigger(t, events, now_ts=8, character_guid=5407)
    assert m is not None
    assert m.params["creature_family"] == "murloc"
    assert m.params["zone"] == "elwynn"

def test_match_below_threshold_returns_none():
    t = parse_reactive_template(_VALID)
    events = [
        EventEnvelope(kind="kill", character_guid=5407, params={"creature_family": "murloc", "zone": "elwynn"}, ts=i)
        for i in range(3)
    ]
    assert match_trigger(t, events, now_ts=3, character_guid=5407) is None

def test_match_respects_window():
    t = parse_reactive_template(_VALID)
    # 8 events but spread across 35 minutes — only last 15 minutes count.
    events = [
        EventEnvelope(kind="kill", character_guid=5407, params={"creature_family": "murloc", "zone": "elwynn"}, ts=i*5)
        for i in range(8)
    ]
    # window_min=15, now_ts=40 (= 40 minutes after first kill). Only kills with ts >= 25 count.
    assert match_trigger(t, events, now_ts=40, character_guid=5407) is None

def test_match_scopes_to_active_character():
    t = parse_reactive_template(_VALID)
    events = [
        EventEnvelope(kind="kill", character_guid=9999, params={"creature_family": "murloc", "zone": "elwynn"}, ts=i)
        for i in range(8)
    ]
    # other character's kills must not trigger active character's template
    assert match_trigger(t, events, now_ts=8, character_guid=5407) is None

def test_schema_file_exists():
    p = Path("control/schemas/wm.reactive_template.v1.schema.json")
    assert p.exists()
    j = json.loads(p.read_text(encoding="utf-8"))
    assert j["$id"].endswith("wm.reactive_template.v1")
