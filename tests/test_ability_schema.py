import json
from pathlib import Path
import pytest
from wm.abilities.schema import (
    AbilitySpec, AbilityType, AbilityTarget, parse_ability,
    EffectStatAura, EffectPeriodicDamage, EffectOnHitProc, EffectSpawnActor,
    ValidationError,
)

_PASSIVE_AURA = {
    "schema": "wm.ability.v1", "id": "shadow_pulse_aura_v1", "name": "Shadow Pulse",
    "version": 1, "client_tier": "T2", "feasibility_notes": "shell-bank visible aura",
    "type": "passive", "target": "self",
    "effect": {"kind": "stat_aura", "stat": "spell_power_shadow", "amount": 24, "duration": "persistent"},
    "shell_binding": {"shell_bank_ref": "shell_demo_passive_1", "visible_aura_spell_id": 946700},
    "grant_policy": {"scope": "active_character", "persistence": "persistent", "revoke_path": "managed.rollback.shadow_pulse_aura_v1"},
}

_ACTIVE_PERIODIC = {
    "schema": "wm.ability.v1", "id": "echo_lash_v1", "name": "Echo Lash",
    "version": 1, "client_tier": "T2", "feasibility_notes": "shell-bank active",
    "type": "active", "target": "single_enemy",
    "effect": {"kind": "periodic_damage", "school": "shadow", "base": 12, "scaling": 0.0, "period_ms": 2000},
    "shell_binding": {"shell_bank_ref": "shell_demo_active_1", "visible_aura_spell_id": 946701},
    "grant_policy": {"scope": "active_character", "persistence": "persistent", "revoke_path": "managed.rollback.echo_lash_v1"},
}

def test_parse_passive_stat_aura():
    a = parse_ability(_PASSIVE_AURA)
    assert a.type is AbilityType.PASSIVE
    assert a.target is AbilityTarget.SELF
    assert isinstance(a.effect, EffectStatAura)
    assert a.effect.stat == "spell_power_shadow"
    assert a.effect.amount == 24

def test_parse_active_periodic_damage():
    a = parse_ability(_ACTIVE_PERIODIC)
    assert a.type is AbilityType.ACTIVE
    assert a.target is AbilityTarget.SINGLE_ENEMY
    assert isinstance(a.effect, EffectPeriodicDamage)
    assert a.effect.period_ms == 2000

def test_rejects_unknown_schema():
    bad = dict(_PASSIVE_AURA); bad["schema"] = "x"
    with pytest.raises(ValidationError, match="schema"):
        parse_ability(bad)

def test_rejects_unknown_effect_kind():
    bad = dict(_PASSIVE_AURA); bad["effect"] = {"kind": "make_dragon", "size": "big"}
    with pytest.raises(ValidationError, match="effect"):
        parse_ability(bad)

def test_rejects_missing_shell_binding():
    bad = dict(_PASSIVE_AURA); del bad["shell_binding"]
    with pytest.raises(ValidationError, match="shell_binding"):
        parse_ability(bad)

def test_schema_file_exists():
    p = Path("control/schemas/wm.ability.v1.schema.json")
    assert p.exists()
    j = json.loads(p.read_text(encoding="utf-8"))
    assert j["$id"].endswith("wm.ability.v1")
