import json
from pathlib import Path
import pytest
from wm.abilities.schema import parse_ability
from wm.abilities.grant_compiler import compile_grant_plan, GrantPlanError

def _load(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def test_passive_compiles_to_aura_apply_plan():
    spec = parse_ability(_load("control/examples/abilities/shadow_pulse_aura_v1.json"))
    plan = compile_grant_plan(spec, character_guid=5407)
    kinds = [s.action_kind for s in plan.steps]
    # passive stat_aura ⇒ apply the visible aura (player_apply_aura)
    assert "player_apply_aura" in kinds
    assert plan.character_guid == 5407
    assert plan.ability_id == "shadow_pulse_aura_v1"
    assert plan.idempotency_key.endswith("shadow_pulse_aura_v1:5407")

def test_active_compiles_to_learn_and_aura_plan():
    spec = parse_ability(_load("control/examples/abilities/echo_lash_v1.json"))
    plan = compile_grant_plan(spec, character_guid=5407)
    kinds = [s.action_kind for s in plan.steps]
    # active ⇒ teach the shell spell + apply the visible-aura marker
    assert "player_learn_spell" in kinds
    assert "player_apply_aura" in kinds

def test_missing_shell_binding_raises():
    spec = parse_ability(_load("control/examples/abilities/shadow_pulse_aura_v1.json"))
    spec.shell_binding.visible_aura_spell_id = 0  # unbound
    with pytest.raises(GrantPlanError, match="visible_aura_spell_id"):
        compile_grant_plan(spec, character_guid=5407)
