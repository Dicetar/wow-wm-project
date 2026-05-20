import json
from pathlib import Path
from wm.arcs.story_module import parse_story_module
from wm.reactive.reactive_template import parse_reactive_template
from wm.abilities.schema import parse_ability

TEMPLATE_IDS = {
    "zone_kill_bounty","repeated_death_nemesis","opportunity_caravan","idle_ambush",
    "lore_artifact_finder","escalation_rival","escort_runner","hunter_spirit",
    "stash_pinger","outbreak_warden",
}

def _load(p: Path) -> dict: return json.loads(p.read_text(encoding="utf-8"))

def test_story_module_loads():
    m = parse_story_module(_load(Path("control/examples/story_modules/demo_one.story_module.json")))
    assert m.module_id and m.beats
    assert any(b.kind.name == "OPEN" for b in m.beats)
    assert any(b.kind.name == "PINNED" for b in m.beats)

def test_reactive_template_catalog_loads():
    d = Path("control/examples/reactive_templates")
    files = sorted(p for p in d.iterdir() if p.suffix == ".json")
    ids = set()
    for p in files:
        t = parse_reactive_template(_load(p))
        ids.add(t.id)
    assert ids == TEMPLATE_IDS, f"missing or extra: {ids ^ TEMPLATE_IDS}"

def test_abilities_load():
    a1 = parse_ability(_load(Path("control/examples/abilities/shadow_pulse_aura_v1.json")))
    a2 = parse_ability(_load(Path("control/examples/abilities/echo_lash_v1.json")))
    assert a1.type.name == "PASSIVE"
    assert a2.type.name == "ACTIVE"
