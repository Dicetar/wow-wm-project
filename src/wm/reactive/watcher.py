"""The Watcher — reactive content loop.

Subscribes to the event spine, keeps a rolling event window per active
character, and on each event re-evaluates each ReactiveTemplate via
match_trigger(). On match with cooldown+dedupe honored, ask the adapter
for a structured proposal and submit to the approval gate.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from wm.reactive.reactive_template import (
    ReactiveTemplate, match_trigger, EventEnvelope,
)
from wm.llm.proposal_adapter import (
    Proposal, ProposalKind, ProposalRequest, ProposalAdapter,
)
from wm.panel.approval_gate import ApprovalGate


@dataclass(slots=True)
class WatcherEvent:
    kind: str
    character_guid: int
    params: dict[str, Any] = field(default_factory=dict)
    ts: int = 0


class Watcher:
    def __init__(self, *, templates: list[ReactiveTemplate], adapter: ProposalAdapter,
                 gate: ApprovalGate, active_character_guid: int) -> None:
        self.templates = templates
        self.adapter = adapter
        self.gate = gate
        self.active_character_guid = active_character_guid
        self._events: list[EventEnvelope] = []
        # dedupe_key (resolved) → last_fired_ts
        self._last_fired: dict[str, int] = {}

    def on_event(self, evt: WatcherEvent) -> None:
        if evt.character_guid != self.active_character_guid:
            return
        self._events.append(EventEnvelope(
            kind=evt.kind, character_guid=evt.character_guid,
            params=dict(evt.params), ts=evt.ts,
        ))
        for tmpl in self.templates:
            m = match_trigger(tmpl, self._events, now_ts=evt.ts,
                              character_guid=self.active_character_guid)
            if m is None: continue
            dk = self._resolve(tmpl.trigger.dedupe_key, m.params)
            last = self._last_fired.get(dk)
            if last is not None and (evt.ts - last) < tmpl.trigger.cooldown_min:
                continue
            self._fire(tmpl, m.params, now_ts=evt.ts)
            self._last_fired[dk] = evt.ts

    def _resolve(self, template_str: str, params: dict[str, Any]) -> str:
        out = template_str
        for k, v in params.items():
            out = out.replace("{" + k + "}", str(v))
        return out

    def _fire(self, tmpl: ReactiveTemplate, params: dict[str, Any], *, now_ts: int) -> None:
        intent = self._resolve(tmpl.narrative_hook, params)
        slots = {k: (params.get(v.replace("trigger.","")) if isinstance(v, str) and v.startswith("trigger.") else v)
                 for k, v in tmpl.recipe.slots.items()}
        req = ProposalRequest(
            kind=ProposalKind.QUEST if tmpl.recipe.kind == "quest" else ProposalKind.SCENE,
            context={"character": {"guid": self.active_character_guid},
                     "watcher": {"template_id": tmpl.id, "narrative_hook": intent,
                                 "slots": slots}},
            intent=intent,
            constraints={"compiler": tmpl.recipe.compiler, "slots": slots,
                         "idempotency_key": self._resolve(
                             tmpl.guards.idempotency_key_template,
                             {**params, "character_guid": self.active_character_guid}),
                         "feasibility_tier": tmpl.guards.feasibility_tier},
        )
        prop = self.adapter.propose(req)
        prop.provenance.setdefault("watcher_template", tmpl.id)
        self.gate.submit(prop)
