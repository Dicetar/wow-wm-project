"""Starter-item onboarding.

build_starter_item_grant_plan: deterministic plan to grant the WM starter
item to the active character (one player_add_item bridge action).

OnboardingHandler: in-process converter — on `use_item` event for the
starter item by the active character, emit `wm.attention.granted` (the
runner's entry condition for b00). The handler exists in-process for the
slice; future work moves this into a native script.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
from wm.abilities.grant_compiler import GrantStep, GrantPlan


@dataclass(slots=True)
class OnboardingEvent:
    kind: str
    character_guid: int
    params: dict[str, Any] = field(default_factory=dict)


def build_starter_item_grant_plan(*, character_guid: int, item_entry: int) -> GrantPlan:
    step = GrantStep(action_kind="player_add_item",
                     payload={"item_id": item_entry, "count": 1})
    return GrantPlan(
        ability_id=f"starter_item_{item_entry}",
        character_guid=character_guid,
        idempotency_key=f"onboarding.starter_item:{item_entry}:{character_guid}",
        steps=[step],
        revoke_path=f"onboarding.revoke.starter_item:{item_entry}:{character_guid}",
    )


class OnboardingHandler:
    def __init__(self, *, starter_item_entry: int, active_character_guid: int,
                 emit: Callable[[OnboardingEvent], None]) -> None:
        self.starter_item_entry = starter_item_entry
        self.active_character_guid = active_character_guid
        self._emit = emit
        self._fired = False

    def on_event(self, evt: OnboardingEvent) -> None:
        if self._fired: return
        if evt.character_guid != self.active_character_guid: return
        if evt.kind != "use_item": return
        if int(evt.params.get("item_entry", -1)) != self.starter_item_entry: return
        self._emit(OnboardingEvent(kind="wm.attention.granted",
                                   character_guid=evt.character_guid, params={}))
        self._fired = True
