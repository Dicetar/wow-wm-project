"""Compile an AbilitySpec into a deterministic native-bridge grant plan.

The plan is a list of typed actions for the native bus. The plan is
dry-run-able: nothing is published here — that is the approval gate's
job. Idempotency key + character scope are stamped on the plan.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from wm.abilities.schema import (
    AbilitySpec, AbilityType, EffectStatAura, EffectPeriodicDamage,
    EffectOnHitProc, EffectSpawnActor,
)


class GrantPlanError(ValueError):
    pass


@dataclass(slots=True)
class GrantStep:
    action_kind: str           # matches wm_bridge_action_request.ActionKind
    payload: dict[str, Any]


@dataclass(slots=True)
class GrantPlan:
    ability_id: str
    character_guid: int
    idempotency_key: str
    steps: list[GrantStep]
    revoke_path: str


def compile_grant_plan(spec: AbilitySpec, *, character_guid: int) -> GrantPlan:
    if not spec.shell_binding.visible_aura_spell_id:
        raise GrantPlanError("ability requires shell_binding.visible_aura_spell_id")

    aura_apply = GrantStep(
        action_kind="player_apply_aura",
        payload={
            "spell_id": spec.shell_binding.visible_aura_spell_id,
            "duration": -1 if isinstance(spec.effect, EffectStatAura) and spec.effect.duration == "persistent" else 0,
        },
    )
    steps: list[GrantStep] = []
    if spec.type is AbilityType.ACTIVE:
        # active abilities are taught as the shell spell (the spellbook button) +
        # the visible-aura marker that the runtime keys behavior on
        teach = GrantStep(action_kind="player_learn_spell",
                          payload={"spell_id": spec.shell_binding.visible_aura_spell_id})
        steps.append(teach)
    steps.append(aura_apply)

    if isinstance(spec.effect, (EffectPeriodicDamage, EffectOnHitProc, EffectSpawnActor)):
        # behavior bodies are owned by the existing runtime; the marker aura
        # is what the runtime keys on. nothing additional needed for the slice.
        pass

    idem = f"ability.grant.{spec.id}:{character_guid}"
    return GrantPlan(
        ability_id=spec.id, character_guid=character_guid,
        idempotency_key=idem, steps=steps,
        revoke_path=spec.grant_policy.revoke_path,
    )
