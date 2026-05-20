"""wm.reactive_template.v1 — universal Watcher template schema + match engine.

See docs/superpowers/specs/2026-05-20-wm-vertical-slice-design.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "wm.reactive_template.v1"


class ValidationError(ValueError):
    pass


@dataclass(slots=True)
class CountThreshold:
    min: int
    window_min: int


@dataclass(slots=True)
class TriggerSpec:
    event: str
    params: dict[str, Any]
    scope: str            # "active_character"
    cooldown_min: int
    dedupe_key: str
    count: CountThreshold | None = None


@dataclass(slots=True)
class RecipeSpec:
    kind: str             # "quest" | "scene" | "ability"
    compiler: str
    slots: dict[str, Any]


@dataclass(slots=True)
class GuardSpec:
    feasibility_tier: str
    max_concurrent: int
    idempotency_key_template: str


@dataclass(slots=True)
class ReactiveTemplate:
    id: str
    narrative_hook: str
    trigger: TriggerSpec
    recipe: RecipeSpec
    guards: GuardSpec


@dataclass(slots=True)
class EventEnvelope:
    kind: str
    character_guid: int
    params: dict[str, Any]
    ts: int               # minute granularity is fine for the slice


@dataclass(slots=True)
class MatchResult:
    template_id: str
    params: dict[str, Any]   # resolved (slot → concrete value)
    sample_events: list[EventEnvelope]


def parse_reactive_template(raw: dict[str, Any]) -> ReactiveTemplate:
    if raw.get("schema") != SCHEMA_ID:
        raise ValidationError(f"schema must be {SCHEMA_ID}, got {raw.get('schema')!r}")
    tr = raw["trigger"]
    count_raw = tr.get("params", {}).get("count")
    count = CountThreshold(min=int(count_raw["min"]), window_min=int(count_raw["window_min"])) if count_raw else None
    trigger = TriggerSpec(
        event=str(tr["event"]),
        params={k: v for k, v in tr.get("params", {}).items() if k != "count"},
        scope=str(tr["scope"]),
        cooldown_min=int(tr["cooldown_min"]),
        dedupe_key=str(tr["dedupe_key"]),
        count=count,
    )
    rec = raw["recipe"]
    recipe = RecipeSpec(kind=str(rec["kind"]), compiler=str(rec["compiler"]), slots=dict(rec.get("slots", {})))
    g = raw["guards"]
    guards = GuardSpec(
        feasibility_tier=str(g["feasibility_tier"]),
        max_concurrent=int(g["max_concurrent"]),
        idempotency_key_template=str(g["idempotency_key_template"]),
    )
    return ReactiveTemplate(
        id=str(raw["id"]), narrative_hook=str(raw["narrative_hook"]),
        trigger=trigger, recipe=recipe, guards=guards,
    )


def match_trigger(
    template: ReactiveTemplate, events: list[EventEnvelope],
    *, now_ts: int, character_guid: int,
) -> MatchResult | None:
    """Return a MatchResult if the template's count-threshold over its window
    is satisfied by events of the right kind, owned by the active character,
    grouping by the SLOT params declared in the template (e.g. creature_family,
    zone). Otherwise None. Scope is always active_character in the slice."""
    if template.trigger.scope != "active_character":
        return None  # YAGNI: other scopes not in the slice
    tr = template.trigger
    if tr.count is None:
        return None  # YAGNI: non-count triggers not in this task

    cutoff = now_ts - tr.count.window_min
    slot_keys = [k for k, v in tr.params.items() if isinstance(v, str) and v == "<slot>"]

    groups: dict[tuple, list[EventEnvelope]] = {}
    for e in events:
        if e.kind != tr.event: continue
        if e.character_guid != character_guid: continue
        if e.ts < cutoff: continue
        key = tuple(e.params.get(k) for k in slot_keys)
        if any(part is None for part in key): continue
        groups.setdefault(key, []).append(e)

    for key, group in groups.items():
        if len(group) >= tr.count.min:
            resolved = {k: v for k, v in zip(slot_keys, key)}
            return MatchResult(template_id=template.id, params=resolved, sample_events=group)
    return None
