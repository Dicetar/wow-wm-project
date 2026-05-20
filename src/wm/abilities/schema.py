"""wm.ability.v1 — minimal real ability schema (4 primitives).

See docs/superpowers/specs/2026-05-20-wm-vertical-slice-design.md.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

SCHEMA_ID = "wm.ability.v1"


class ValidationError(ValueError):
    pass


class AbilityType(str, Enum):
    PASSIVE = "passive"
    ACTIVE = "active"
    STANCE = "stance"


class AbilityTarget(str, Enum):
    SELF = "self"
    SELF_AOE = "self_aoe"
    SINGLE_FRIEND = "single_friend"
    SINGLE_ENEMY = "single_enemy"


@dataclass(slots=True)
class EffectStatAura:
    stat: str
    amount: int
    duration: str | int  # "persistent" or seconds


@dataclass(slots=True)
class EffectPeriodicDamage:
    school: str
    base: int
    scaling: float
    period_ms: int


@dataclass(slots=True)
class EffectOnHitProc:
    chance_pct: float
    effect_ref: str  # references another ability id


@dataclass(slots=True)
class EffectSpawnActor:
    actor_ref: str
    lifetime_ms: int
    behavior: str


Effect = EffectStatAura | EffectPeriodicDamage | EffectOnHitProc | EffectSpawnActor


@dataclass(slots=True)
class ShellBinding:
    shell_bank_ref: str
    visible_aura_spell_id: int


@dataclass(slots=True)
class GrantPolicy:
    scope: str
    persistence: str
    revoke_path: str


@dataclass(slots=True)
class AbilitySpec:
    id: str
    name: str
    version: int
    client_tier: str  # "T1"|"T2"|"T3"
    feasibility_notes: str
    type: AbilityType
    target: AbilityTarget
    effect: Effect
    shell_binding: ShellBinding
    grant_policy: GrantPolicy


def _parse_effect(raw: dict[str, Any]) -> Effect:
    k = raw.get("kind")
    if k == "stat_aura":
        return EffectStatAura(stat=str(raw["stat"]), amount=int(raw["amount"]), duration=raw["duration"])
    if k == "periodic_damage":
        return EffectPeriodicDamage(school=str(raw["school"]), base=int(raw["base"]),
                                    scaling=float(raw["scaling"]), period_ms=int(raw["period_ms"]))
    if k == "on_hit_proc":
        return EffectOnHitProc(chance_pct=float(raw["chance_pct"]), effect_ref=str(raw["effect_ref"]))
    if k == "spawn_actor":
        return EffectSpawnActor(actor_ref=str(raw["actor_ref"]),
                                lifetime_ms=int(raw["lifetime_ms"]),
                                behavior=str(raw["behavior"]))
    raise ValidationError(f"unknown effect.kind={k!r}; allowed: stat_aura|periodic_damage|on_hit_proc|spawn_actor")


def parse_ability(raw: dict[str, Any]) -> AbilitySpec:
    if raw.get("schema") != SCHEMA_ID:
        raise ValidationError(f"schema must be {SCHEMA_ID}, got {raw.get('schema')!r}")
    if "shell_binding" not in raw:
        raise ValidationError("shell_binding is required")
    sb_raw = raw["shell_binding"]
    gp_raw = raw["grant_policy"]
    return AbilitySpec(
        id=str(raw["id"]), name=str(raw["name"]), version=int(raw["version"]),
        client_tier=str(raw["client_tier"]), feasibility_notes=str(raw.get("feasibility_notes", "")),
        type=AbilityType(raw["type"]), target=AbilityTarget(raw["target"]),
        effect=_parse_effect(raw["effect"]),
        shell_binding=ShellBinding(shell_bank_ref=str(sb_raw["shell_bank_ref"]),
                                   visible_aura_spell_id=int(sb_raw["visible_aura_spell_id"])),
        grant_policy=GrantPolicy(scope=str(gp_raw["scope"]),
                                 persistence=str(gp_raw["persistence"]),
                                 revoke_path=str(gp_raw["revoke_path"])),
    )
