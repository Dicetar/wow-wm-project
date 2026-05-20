# WM Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an end-to-end demo of the WM (World Master) loop for one new character: authored Story Module + reactive Watcher both funnel proposals through one LLM-propose → operator-approve → deterministic-compile → native-bus gate, perceivable in BridgeLab.

**Architecture:** Strict reuse of the existing infra (`src/wm/{arcs,reactive,events,abilities,llm,panel,journal,context,spells}`, the native action bus, content-release pipeline, shell bank). Three new `control/`-lane schemas (`wm.story_module.v1`, `wm.reactive_template.v1`, `wm.ability.v1`), one Arc Runner state machine, one Watcher loop, one approval gate, one minimal ability grant compiler bound to the existing shell bank. **No spell-monolith refactor.** Errors catch-and-park into an issues queue.

**Tech Stack:** Python 3.13 + pytest; existing `src/wm/` packages; LM Studio via `src/wm/llm/lmstudio.py`; AzerothCore 3.3.5a via `wm_bridge_action_request`/event spine on BridgeLab (MySQL 127.0.0.1:33307; scoped player TBD at module-author time, not 5406).

**Spec:** [docs/superpowers/specs/2026-05-20-wm-vertical-slice-design.md](../specs/2026-05-20-wm-vertical-slice-design.md)

**Non-negotiables (every task):**
- TDD: failing test first → minimal code → green → commit.
- DRY: extend existing modules — never duplicate `release.py`/`auto_bounty.py`/`lmstudio.py` logic.
- YAGNI: do not implement primitives/templates/beats beyond the slice scope; the catalog grows by data, not code.
- Conventional Commits; scope is the touched module (`feat(arcs)`, `feat(reactive)`, `feat(abilities)`, `feat(panel)`, `feat(llm)`, `docs`, `chore`, `test`).
- No spell-monolith edits.
- Failures park into the issues queue, never crash the loop.

---

## File Structure

**New Python modules:**
- `src/wm/arcs/story_module.py` — `wm.story_module.v1` dataclasses + validator
- `src/wm/arcs/runner.py` — Arc Runner state machine
- `src/wm/reactive/reactive_template.py` — `wm.reactive_template.v1` dataclasses + validator + trigger-match engine
- `src/wm/reactive/watcher.py` — Watcher loop (subscribes to event spine, matches templates, produces proposals)
- `src/wm/abilities/schema.py` — `wm.ability.v1` dataclasses + validator
- `src/wm/abilities/grant_compiler.py` — ability grant compiler → existing shell bank
- `src/wm/llm/proposal_adapter.py` — context pack + intent → structured proposal (uses existing `lmstudio.py`, `proposal_parser.py`, `prompts.py`)
- `src/wm/panel/approval_gate.py` — pending proposals + approve/reject endpoints
- `src/wm/panel/issues_queue.py` — blocked-proposal queue + endpoints
- `src/wm/onboarding/__init__.py`, `src/wm/onboarding/starter_item.py` — onboarding (issue item, sense use, emit `wm.attention.granted`)
- `src/wm/cli/slice_demo.py` — the demo command (boot module, advance loop, print state)

**New data files:**
- `control/schemas/wm.story_module.v1.schema.json`
- `control/schemas/wm.reactive_template.v1.schema.json`
- `control/schemas/wm.ability.v1.schema.json`
- `control/examples/story_modules/demo_one.story_module.json` — the demo character's module
- `control/examples/reactive_templates/{zone_kill_bounty,repeated_death_nemesis,opportunity_caravan,idle_ambush,lore_artifact_finder,escalation_rival,escort_runner,hunter_spirit,stash_pinger,outbreak_warden}.json` — 10 catalog entries
- `control/examples/abilities/{shadow_pulse_aura_v1,echo_lash_v1}.json` — 2 (1 passive, 1 active)

**New tests** (flat `tests/test_*.py` per project convention):
- `tests/test_story_module_schema.py`
- `tests/test_reactive_template_schema.py`
- `tests/test_ability_schema.py`
- `tests/test_arc_runner.py`
- `tests/test_watcher.py`
- `tests/test_ability_grant_compiler.py`
- `tests/test_approval_gate.py`
- `tests/test_proposal_adapter.py`
- `tests/test_onboarding_starter_item.py`
- `tests/test_slice_demo.py` — integration test against mocked native bridge

**New runbook:**
- `docs/WM_VERTICAL_SLICE_RUNBOOK.md` — operator runbook for the live BridgeLab proof

---

## Task ordering rationale

Schemas first (foundation, no runtime); then example data (the demo content); then the seams (ability grant compiler, LLM proposal adapter, approval gate); then the two loops (Arc Runner, Watcher); then onboarding; then the demo glue + runbook + live-proof entry. Each task ends green + committed.

---

### Task 1: `wm.story_module.v1` schema + validator

**Files:**
- Create: `src/wm/arcs/story_module.py`
- Create: `control/schemas/wm.story_module.v1.schema.json`
- Create: `tests/test_story_module_schema.py`

**Pattern reference:** mirror the dataclass + validator style of `src/wm/content/release.py` (existing `wm.content.release` pipeline).

- [ ] **Step 1: Write `tests/test_story_module_schema.py` with failing cases**

```python
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
```

- [ ] **Step 2: Run test, confirm it fails (import error / missing module)**

Run: `pytest tests/test_story_module_schema.py -v`
Expected: ImportError / ModuleNotFoundError for `wm.arcs.story_module`.

- [ ] **Step 3: Implement `src/wm/arcs/story_module.py` (minimum to make tests pass)**

```python
"""wm.story_module.v1 — per-character authored story spine.

See docs/superpowers/specs/2026-05-20-wm-vertical-slice-design.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "wm.story_module.v1"


class ValidationError(ValueError):
    pass


class BeatKind(str, Enum):
    PINNED = "PINNED"
    OPEN = "OPEN"


@dataclass(slots=True)
class GrantPoint:
    grant_kind: str          # "ability" only for the slice
    ability_ref: str
    when: dict[str, Any]     # {"event": str, "ref": str}
    appropriateness: dict[str, Any]  # {"all_of": [...]} | {"any_of": [...]}


@dataclass(slots=True)
class BeatOutcome:
    next_beat_ref: str | None
    grant_points: list[GrantPoint] = field(default_factory=list)


@dataclass(slots=True)
class Beat:
    id: str
    kind: BeatKind
    entry_condition: dict[str, Any]
    outcome: BeatOutcome
    intent: str | None = None          # OPEN
    constraints: dict[str, Any] = field(default_factory=dict)  # OPEN
    payload: dict[str, Any] | None = None    # PINNED


@dataclass(slots=True)
class StoryModule:
    module_id: str
    character_guid: int
    character_name: str
    premise: str
    tone: str
    constraints: dict[str, Any]
    beats: list[Beat]
    journal_template: str | None = None


def parse_story_module(raw: dict[str, Any]) -> StoryModule:
    if raw.get("schema") != SCHEMA_ID:
        raise ValidationError(f"schema must be {SCHEMA_ID}, got {raw.get('schema')!r}")
    try:
        beats_raw = raw["beats"]
        beat_ids = {b["id"] for b in beats_raw}
    except (KeyError, TypeError) as e:
        raise ValidationError(f"beats missing or malformed: {e}") from e

    beats: list[Beat] = []
    for b in beats_raw:
        kind = BeatKind(b["kind"])
        if kind is BeatKind.OPEN and "intent" not in b:
            raise ValidationError(f"OPEN beat {b['id']!r} missing intent")
        if kind is BeatKind.PINNED and "payload" not in b:
            raise ValidationError(f"PINNED beat {b['id']!r} missing payload")
        outcome_raw = b["outcome"]
        next_ref = outcome_raw.get("next_beat_ref")
        if next_ref is not None and next_ref not in beat_ids:
            raise ValidationError(f"next_beat_ref {next_ref!r} in beat {b['id']!r} is not a known beat id")
        outcome = BeatOutcome(
            next_beat_ref=next_ref,
            grant_points=[
                GrantPoint(
                    grant_kind=g["grant_kind"],
                    ability_ref=g["ability_ref"],
                    when=g["when"],
                    appropriateness=g["appropriateness"],
                )
                for g in outcome_raw.get("grant_points", [])
            ],
        )
        beats.append(Beat(
            id=b["id"], kind=kind,
            entry_condition=b["entry_condition"], outcome=outcome,
            intent=b.get("intent"), constraints=b.get("constraints", {}),
            payload=b.get("payload"),
        ))

    return StoryModule(
        module_id=raw["module_id"],
        character_guid=int(raw["character_guid"]),
        character_name=str(raw["character_name"]),
        premise=str(raw["premise"]),
        tone=str(raw["tone"]),
        constraints=raw.get("constraints", {}),
        beats=beats,
        journal_template=raw.get("journal_template"),
    )
```

- [ ] **Step 4: Create `control/schemas/wm.story_module.v1.schema.json`**

```json
{
  "$id": "wm.story_module.v1",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WM Story Module v1",
  "description": "Per-character authored story spine. See docs/superpowers/specs/2026-05-20-wm-vertical-slice-design.md.",
  "type": "object",
  "required": ["schema", "module_id", "character_guid", "character_name", "premise", "tone", "constraints", "beats"],
  "properties": {
    "schema": {"const": "wm.story_module.v1"},
    "module_id": {"type": "string"},
    "character_guid": {"type": "integer", "minimum": 1},
    "character_name": {"type": "string"},
    "premise": {"type": "string"},
    "tone": {"type": "string"},
    "constraints": {"type": "object"},
    "beats": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/beat"}},
    "journal_template": {"type": ["string", "null"]}
  },
  "$defs": {
    "beat": {
      "type": "object",
      "required": ["id", "kind", "entry_condition", "outcome"],
      "properties": {
        "id": {"type": "string"},
        "kind": {"enum": ["PINNED", "OPEN"]},
        "entry_condition": {"type": "object"},
        "intent": {"type": "string"},
        "constraints": {"type": "object"},
        "payload": {"type": "object"},
        "outcome": {
          "type": "object",
          "required": ["next_beat_ref", "grant_points"],
          "properties": {
            "next_beat_ref": {"type": ["string", "null"]},
            "grant_points": {"type": "array", "items": {"$ref": "#/$defs/grant_point"}}
          }
        }
      }
    },
    "grant_point": {
      "type": "object",
      "required": ["grant_kind", "ability_ref", "when", "appropriateness"],
      "properties": {
        "grant_kind": {"const": "ability"},
        "ability_ref": {"type": "string"},
        "when": {"type": "object"},
        "appropriateness": {"type": "object"}
      }
    }
  }
}
```

- [ ] **Step 5: Run tests, confirm green**

Run: `pytest tests/test_story_module_schema.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/wm/arcs/story_module.py control/schemas/wm.story_module.v1.schema.json tests/test_story_module_schema.py
git -c core.autocrlf=false commit -m "feat(arcs): wm.story_module.v1 dataclasses + validator + json schema"
```

---

### Task 2: `wm.reactive_template.v1` schema + validator + trigger-match

**Files:**
- Create: `src/wm/reactive/reactive_template.py`
- Create: `control/schemas/wm.reactive_template.v1.schema.json`
- Create: `tests/test_reactive_template_schema.py`

**Pattern reference:** mirror `src/wm/reactive/auto_bounty.py`/`templates.py` style (existing reactive system). The new `reactive_template.py` is the universal *schema*; the existing `templates.py` is unrelated (it predates the slice). Do not modify `templates.py` in this task.

- [ ] **Step 1: Write `tests/test_reactive_template_schema.py`**

```python
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
    # 8 events but spread across 30 minutes — only last 15 minutes count.
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
```

- [ ] **Step 2: Run test, confirm failure**

Run: `pytest tests/test_reactive_template_schema.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `src/wm/reactive/reactive_template.py`**

```python
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
```

- [ ] **Step 4: Create `control/schemas/wm.reactive_template.v1.schema.json`**

```json
{
  "$id": "wm.reactive_template.v1",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WM Reactive Template v1",
  "type": "object",
  "required": ["schema", "id", "narrative_hook", "trigger", "recipe", "guards"],
  "properties": {
    "schema": {"const": "wm.reactive_template.v1"},
    "id": {"type": "string"},
    "narrative_hook": {"type": "string"},
    "trigger": {
      "type": "object",
      "required": ["event", "params", "scope", "cooldown_min", "dedupe_key"],
      "properties": {
        "event": {"type": "string"},
        "params": {"type": "object"},
        "scope": {"const": "active_character"},
        "cooldown_min": {"type": "integer", "minimum": 0},
        "dedupe_key": {"type": "string"}
      }
    },
    "recipe": {
      "type": "object",
      "required": ["kind", "compiler", "slots"],
      "properties": {
        "kind": {"enum": ["quest", "scene", "ability"]},
        "compiler": {"type": "string"},
        "slots": {"type": "object"}
      }
    },
    "guards": {
      "type": "object",
      "required": ["feasibility_tier", "max_concurrent", "idempotency_key_template"],
      "properties": {
        "feasibility_tier": {"enum": ["T1", "T2", "T3"]},
        "max_concurrent": {"type": "integer", "minimum": 1},
        "idempotency_key_template": {"type": "string"}
      }
    }
  }
}
```

- [ ] **Step 5: Run tests + commit**

```bash
pytest tests/test_reactive_template_schema.py -v
# expect: 7 passed
git add src/wm/reactive/reactive_template.py control/schemas/wm.reactive_template.v1.schema.json tests/test_reactive_template_schema.py
git -c core.autocrlf=false commit -m "feat(reactive): wm.reactive_template.v1 + trigger-match engine"
```

---

### Task 3: `wm.ability.v1` schema + validator

**Files:**
- Create: `src/wm/abilities/schema.py`
- Create: `control/schemas/wm.ability.v1.schema.json`
- Create: `tests/test_ability_schema.py`

- [ ] **Step 1: Write `tests/test_ability_schema.py`**

```python
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
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/test_ability_schema.py -v` → ImportError.

- [ ] **Step 3: Implement `src/wm/abilities/schema.py`**

```python
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
```

- [ ] **Step 4: Create `control/schemas/wm.ability.v1.schema.json`**

```json
{
  "$id": "wm.ability.v1",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WM Ability v1",
  "type": "object",
  "required": ["schema","id","name","version","client_tier","type","target","effect","shell_binding","grant_policy"],
  "properties": {
    "schema": {"const": "wm.ability.v1"},
    "id": {"type": "string"},
    "name": {"type": "string"},
    "version": {"type": "integer", "minimum": 1},
    "client_tier": {"enum": ["T1","T2","T3"]},
    "feasibility_notes": {"type": "string"},
    "type": {"enum": ["passive","active","stance"]},
    "target": {"enum": ["self","self_aoe","single_friend","single_enemy"]},
    "effect": {
      "oneOf": [
        {"type":"object","required":["kind","stat","amount","duration"],"properties":{"kind":{"const":"stat_aura"}}},
        {"type":"object","required":["kind","school","base","scaling","period_ms"],"properties":{"kind":{"const":"periodic_damage"}}},
        {"type":"object","required":["kind","chance_pct","effect_ref"],"properties":{"kind":{"const":"on_hit_proc"}}},
        {"type":"object","required":["kind","actor_ref","lifetime_ms","behavior"],"properties":{"kind":{"const":"spawn_actor"}}}
      ]
    },
    "shell_binding": {"type":"object","required":["shell_bank_ref","visible_aura_spell_id"]},
    "grant_policy": {"type":"object","required":["scope","persistence","revoke_path"]}
  }
}
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_ability_schema.py -v   # expect 6 passed
git add src/wm/abilities/schema.py control/schemas/wm.ability.v1.schema.json tests/test_ability_schema.py
git -c core.autocrlf=false commit -m "feat(abilities): wm.ability.v1 schema + validator (4 primitives)"
```

---

### Task 4: Demo data — story module + 10 reactive templates + 2 abilities

**Files:**
- Create: `control/examples/story_modules/demo_one.story_module.json`
- Create: `control/examples/reactive_templates/<10 files>.json`
- Create: `control/examples/abilities/{shadow_pulse_aura_v1,echo_lash_v1}.json`
- Create: `tests/test_demo_data_loads.py`

- [ ] **Step 1: Write `tests/test_demo_data_loads.py` (red)**

```python
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
```

- [ ] **Step 2: Author `control/examples/story_modules/demo_one.story_module.json`**

```json
{
  "schema": "wm.story_module.v1",
  "module_id": "demo_one_v1",
  "character_guid": 5407,
  "character_name": "Demo One",
  "premise": "A newcomer arrives in Northshire and draws the WM's regard through an old token.",
  "tone": "somber-curious",
  "constraints": {
    "zone_whitelist": [12],
    "level_band": [1, 5],
    "id_ranges": {"quest": [910500, 910549], "creature": [920500, 920549], "item": [910500, 910549]},
    "ability_themes": ["shadow_warden"]
  },
  "beats": [
    {
      "id": "b00_onboarding", "kind": "PINNED",
      "entry_condition": {"event": "wm.attention.granted"},
      "payload": {
        "quest_release": {
          "title": "An Unfamiliar Weight",
          "objective": "Speak with Marshal McBride in Northshire Abbey.",
          "description": "The token in your pack hums faintly. Marshal McBride may know its meaning.",
          "giver_creature_entry": 197,
          "objective_kind": "talk_to_npc",
          "objective_target_entry": 197,
          "rewards": {"xp": 80}
        }
      },
      "outcome": {"next_beat_ref": "b01_zone_intro", "grant_points": []}
    },
    {
      "id": "b01_zone_intro", "kind": "OPEN",
      "entry_condition": {"event": "quest.completed", "ref": "b00_onboarding"},
      "intent": "A short Northshire quest from McBride that frames the token as a watcher's mark. One objective, ideally clearing a nearby threat (kobolds or wolves). Tone: cautious, curious.",
      "constraints": {
        "giver_pool": [197],
        "location_pool": [12],
        "ability_theme_hint": "shadow_warden",
        "max_objectives": 1
      },
      "outcome": {
        "next_beat_ref": "b02_complication",
        "grant_points": [
          {"grant_kind": "ability", "ability_ref": "shadow_pulse_aura_v1",
           "when": {"event": "quest.completed", "ref": "b01_zone_intro"},
           "appropriateness": {"all_of": [{"character_level_at_least": 1}]}}
        ]
      }
    },
    {
      "id": "b02_complication", "kind": "OPEN",
      "entry_condition": {"event": "quest.completed", "ref": "b01_zone_intro"},
      "intent": "A complication: something the player did in b01 attracted notice. One objective in Northshire investigating a darker presence. Tone: ominous, personal.",
      "constraints": {
        "giver_pool": [197],
        "location_pool": [12],
        "ability_theme_hint": "shadow_warden",
        "max_objectives": 1
      },
      "outcome": {"next_beat_ref": "b03_finale", "grant_points": []}
    },
    {
      "id": "b03_finale", "kind": "PINNED",
      "entry_condition": {"event": "quest.completed", "ref": "b02_complication"},
      "payload": {
        "quest_release": {
          "title": "The Watcher's Lash",
          "objective": "Defeat the Shadow Echo at the Northshire vineyard.",
          "description": "The watcher's regard has drawn out its echo. End it, and the regard becomes yours to use.",
          "giver_creature_entry": 197,
          "objective_kind": "kill_creature",
          "objective_target_entry": 920500,
          "objective_count": 1,
          "rewards": {"xp": 240}
        }
      },
      "outcome": {
        "next_beat_ref": null,
        "grant_points": [
          {"grant_kind": "ability", "ability_ref": "echo_lash_v1",
           "when": {"event": "quest.completed", "ref": "b03_finale"},
           "appropriateness": {"all_of": [{"character_level_at_least": 2}]}}
        ]
      }
    }
  ],
  "journal_template": "Demo One's regard-arc, beat-by-beat."
}
```

- [ ] **Step 3: Author the 10 reactive template JSON files**

For each of the 10 ids, create `control/examples/reactive_templates/<id>.json`. Template skeleton (vary fields per id; keep `schema=wm.reactive_template.v1` and `scope=active_character`):

```json
{
  "schema": "wm.reactive_template.v1",
  "id": "<id>",
  "narrative_hook": "<one sentence with <slot> placeholders the LLM can skin>",
  "trigger": {
    "event": "<kill|death|quest.completed|zone_change|use_item>",
    "params": { "<slot_field>": "<slot>", "count": {"min": <int>, "window_min": <int>} },
    "scope": "active_character",
    "cooldown_min": <int>,
    "dedupe_key": "<id>:{<slot_field>}"
  },
  "recipe": {
    "kind": "<quest|scene|ability>",
    "compiler": "wm.content.release/<repeatable_bounty|story_arc|scene>",
    "slots": { "<from-trigger>": "trigger.<field>", "title": "<llm-filled>", "description": "<llm-filled>" }
  },
  "guards": {
    "feasibility_tier": "T1",
    "max_concurrent": 1,
    "idempotency_key_template": "watch:<id>:{character_guid}:{<slot_field>}"
  }
}
```

Concrete authoring — use these trigger configurations (event kind / count threshold / window / cooldown):
- `zone_kill_bounty`: kill / {creature_family,zone} / 8 in 15min / cd 60
- `repeated_death_nemesis`: death / {killer_creature_entry} / 3 in 30min / cd 120, recipe.kind=quest, compiler=repeatable_bounty
- `opportunity_caravan`: zone_change / {zone} / 1 in 5min / cd 240, recipe.kind=scene, compiler=scene
- `idle_ambush`: idle / {zone} / count.min=1 (event implemented as a periodic idle event, window 5min) / cd 90, recipe.kind=scene
- `lore_artifact_finder`: use_item / {item_entry} / 1 in 1min / cd 240, recipe.kind=quest, compiler=story_arc
- `escalation_rival`: kill / {creature_entry} / 12 in 30min / cd 240, recipe.kind=quest
- `escort_runner`: quest.completed / {quest_entry_family="escort"} / 1 in 1min / cd 120, recipe.kind=scene
- `hunter_spirit`: kill / {creature_family="beast"} / 5 in 10min / cd 90, recipe.kind=quest
- `stash_pinger`: zone_change / {zone} / 1 in 60min / cd 180, recipe.kind=scene
- `outbreak_warden`: kill / {creature_family,zone} / 15 in 20min / cd 60, recipe.kind=quest

For events the existing event spine doesn't emit yet (`idle`), include the file anyway with the same schema; the Watcher will simply never match it in the slice (catalog-only is fine — YAGNI).

- [ ] **Step 4: Author the 2 ability JSON files**

`control/examples/abilities/shadow_pulse_aura_v1.json`:

```json
{
  "schema": "wm.ability.v1", "id": "shadow_pulse_aura_v1", "name": "Shadow Pulse",
  "version": 1, "client_tier": "T2", "feasibility_notes": "shell-bank passive visible aura",
  "type": "passive", "target": "self",
  "effect": {"kind": "stat_aura", "stat": "spell_power_shadow", "amount": 24, "duration": "persistent"},
  "shell_binding": {"shell_bank_ref": "shell_demo_passive_1", "visible_aura_spell_id": 946700},
  "grant_policy": {"scope": "active_character", "persistence": "persistent", "revoke_path": "managed.rollback.shadow_pulse_aura_v1"}
}
```

`control/examples/abilities/echo_lash_v1.json`:

```json
{
  "schema": "wm.ability.v1", "id": "echo_lash_v1", "name": "Echo Lash",
  "version": 1, "client_tier": "T2", "feasibility_notes": "shell-bank active single-target shadow DoT",
  "type": "active", "target": "single_enemy",
  "effect": {"kind": "periodic_damage", "school": "shadow", "base": 12, "scaling": 0.0, "period_ms": 2000},
  "shell_binding": {"shell_bank_ref": "shell_demo_active_1", "visible_aura_spell_id": 946701},
  "grant_policy": {"scope": "active_character", "persistence": "persistent", "revoke_path": "managed.rollback.echo_lash_v1"}
}
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_demo_data_loads.py -v   # expect 3 passed
git add control/examples/story_modules/ control/examples/reactive_templates/ control/examples/abilities/ tests/test_demo_data_loads.py
git -c core.autocrlf=false commit -m "feat(control): demo story module + 10 reactive templates + 2 ability specs"
```

---

### Task 5: Ability grant compiler (binds to existing shell bank)

**Files:**
- Create: `src/wm/abilities/grant_compiler.py`
- Create: `tests/test_ability_grant_compiler.py`

**Reuse:** `src/wm/spells/shell_bank.py` provides `load_spell_shell_bank()` and `SpellShellDefinition` (used by `src/wm/spells/platform.py`). The grant compiler reads an `AbilitySpec`, looks up its `shell_binding.shell_bank_ref` in the bank, and produces a deterministic **grant plan** (a sequence of native bridge actions). Apply lives elsewhere; this task is *compile-only* (dry-run-able).

- [ ] **Step 1: Write `tests/test_ability_grant_compiler.py`**

```python
import json
from pathlib import Path
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
    import pytest
    with pytest.raises(GrantPlanError, match="visible_aura_spell_id"):
        compile_grant_plan(spec, character_guid=5407)
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest tests/test_ability_grant_compiler.py -v` → ImportError.

- [ ] **Step 3: Implement `src/wm/abilities/grant_compiler.py`**

```python
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

    aura_apply = GrantStep(action_kind="player_apply_aura",
                           payload={"spell_id": spec.shell_binding.visible_aura_spell_id,
                                    "duration": -1 if isinstance(spec.effect, EffectStatAura) and spec.effect.duration == "persistent" else 0})
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
```

- [ ] **Step 4: Run + commit**

```bash
pytest tests/test_ability_grant_compiler.py -v   # expect 3 passed
git add src/wm/abilities/grant_compiler.py tests/test_ability_grant_compiler.py
git -c core.autocrlf=false commit -m "feat(abilities): grant compiler (AbilitySpec → native action plan)"
```

---

### Task 6: LLM proposal adapter (deterministic fixture path + LM Studio path)

**Files:**
- Create: `src/wm/llm/proposal_adapter.py`
- Create: `tests/test_proposal_adapter.py`
- Create: `tests/fixtures/llm/quest_proposal_basic.json` — recorded model response
- Reuse: `src/wm/llm/lmstudio.py`, `src/wm/llm/proposal_parser.py`, `src/wm/llm/prompts.py`

The adapter has two modes:
- **fixture** (default in tests, CI): returns a recorded structured proposal — deterministic.
- **live** (LM Studio): calls `lmstudio.chat_completion(...)` and parses via `proposal_parser`.

- [ ] **Step 1: Write `tests/test_proposal_adapter.py`**

```python
from pathlib import Path
import json
from wm.llm.proposal_adapter import (
    ProposalAdapter, ProposalKind, ProposalRequest, AdapterMode,
)

def _fixture(): return json.loads(Path("tests/fixtures/llm/quest_proposal_basic.json").read_text(encoding="utf-8"))

def test_fixture_mode_returns_recorded_proposal():
    a = ProposalAdapter(mode=AdapterMode.FIXTURE, fixture=_fixture())
    req = ProposalRequest(
        kind=ProposalKind.QUEST,
        context={"character": {"guid": 5407, "name": "Demo One", "zone_id": 12, "level": 2}},
        intent="A short Northshire quest. One kill objective. Tone: cautious.",
        constraints={"giver_pool": [197], "max_objectives": 1, "id_ranges": {"quest": [910500, 910549]}},
    )
    p = a.propose(req)
    assert p.kind is ProposalKind.QUEST
    assert p.payload["quest_release"]["title"]
    assert p.payload["quest_release"]["giver_creature_entry"] == 197
    assert p.character_guid == 5407
    assert p.provenance["mode"] == "fixture"

def test_invalid_fixture_routes_to_issues_queue():
    bad = {"kind": "quest", "payload": {"oops": "no quest_release"}}
    a = ProposalAdapter(mode=AdapterMode.FIXTURE, fixture=bad)
    req = ProposalRequest(kind=ProposalKind.QUEST, context={"character": {"guid": 5407}},
                          intent="x", constraints={})
    p = a.propose(req)
    assert p.is_blocked
    assert "quest_release" in p.block_reason
```

- [ ] **Step 2: Record fixture `tests/fixtures/llm/quest_proposal_basic.json`**

```json
{
  "kind": "quest",
  "payload": {
    "quest_release": {
      "title": "Wolves at the Vineyard",
      "objective": "Cull 6 Young Wolves near the Northshire Vineyard.",
      "description": "Marshal McBride asks you to thin the wolves before they reach the abbey.",
      "giver_creature_entry": 197,
      "objective_kind": "kill_creature",
      "objective_target_entry": 299,
      "objective_count": 6,
      "rewards": {"xp": 120}
    }
  },
  "narrative_summary": "A cautious Northshire shake-out: McBride sends you to thin the wolves; the regard takes note of your efficiency."
}
```

- [ ] **Step 3: Run, confirm fail**

`pytest tests/test_proposal_adapter.py -v` → ImportError.

- [ ] **Step 4: Implement `src/wm/llm/proposal_adapter.py`**

```python
"""LLM proposal adapter — builds structured proposals from context + intent.

Modes:
  FIXTURE: returns the provided recorded proposal (used by tests + CI).
  LIVE:    calls LM Studio via wm.llm.lmstudio + parses via proposal_parser.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AdapterMode(str, Enum):
    FIXTURE = "fixture"
    LIVE = "live"


class ProposalKind(str, Enum):
    QUEST = "quest"
    SCENE = "scene"
    ABILITY = "ability"


@dataclass(slots=True)
class ProposalRequest:
    kind: ProposalKind
    context: dict[str, Any]
    intent: str
    constraints: dict[str, Any]


@dataclass(slots=True)
class Proposal:
    kind: ProposalKind
    payload: dict[str, Any]
    character_guid: int
    narrative_summary: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    is_blocked: bool = False
    block_reason: str = ""


_QUEST_REQUIRED_FIELDS = (
    "title", "objective", "description", "giver_creature_entry",
    "objective_kind", "rewards",
)


@dataclass(slots=True)
class ProposalAdapter:
    mode: AdapterMode = AdapterMode.FIXTURE
    fixture: dict[str, Any] | None = None

    def propose(self, req: ProposalRequest) -> Proposal:
        if self.mode is AdapterMode.FIXTURE:
            raw = self.fixture or {}
            prov = {"mode": "fixture"}
        else:
            raw = self._call_live(req)
            prov = {"mode": "live"}

        return self._validate(raw, req, prov)

    # --- internals -----------------------------------------------------

    def _call_live(self, req: ProposalRequest) -> dict[str, Any]:
        # imports are lazy so tests can run without the LM Studio dep
        from wm.llm import lmstudio, proposal_parser, prompts  # noqa: F401
        prompt = self._build_prompt(req)
        text = lmstudio.chat_completion(prompt=prompt)
        return proposal_parser.parse_structured(text)

    def _build_prompt(self, req: ProposalRequest) -> str:
        # Real prompt composition is delegated to wm.llm.prompts in follow-up
        # work; for the slice the live mode is opt-in and the prompt is a
        # straight JSON contract dump.
        import json
        return (
            "Return ONLY a JSON object matching the WM proposal schema for "
            f"kind={req.kind.value}. Intent: {req.intent}\n"
            f"Constraints: {json.dumps(req.constraints)}\n"
            f"Context: {json.dumps(req.context)}\n"
        )

    def _validate(self, raw: dict[str, Any], req: ProposalRequest, prov: dict[str, Any]) -> Proposal:
        cg = int(req.context.get("character", {}).get("guid", 0))
        if not raw or "kind" not in raw or "payload" not in raw:
            return Proposal(kind=req.kind, payload=raw or {}, character_guid=cg,
                            provenance=prov, is_blocked=True, block_reason="missing kind/payload")
        if raw["kind"] != req.kind.value:
            return Proposal(kind=req.kind, payload=raw["payload"], character_guid=cg,
                            provenance=prov, is_blocked=True, block_reason=f"kind mismatch: expected {req.kind.value}, got {raw['kind']!r}")
        if req.kind is ProposalKind.QUEST:
            q = raw["payload"].get("quest_release")
            if not q:
                return Proposal(kind=req.kind, payload=raw["payload"], character_guid=cg,
                                provenance=prov, is_blocked=True, block_reason="missing quest_release")
            missing = [k for k in _QUEST_REQUIRED_FIELDS if k not in q]
            if missing:
                return Proposal(kind=req.kind, payload=raw["payload"], character_guid=cg,
                                provenance=prov, is_blocked=True, block_reason=f"missing fields: {','.join(missing)}")
        return Proposal(kind=req.kind, payload=raw["payload"], character_guid=cg,
                        narrative_summary=str(raw.get("narrative_summary", "")), provenance=prov)
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_proposal_adapter.py -v   # expect 2 passed
git add src/wm/llm/proposal_adapter.py tests/test_proposal_adapter.py tests/fixtures/llm/quest_proposal_basic.json
git -c core.autocrlf=false commit -m "feat(llm): proposal adapter — fixture + LM-Studio modes, schema-validated"
```

---

### Task 7: Approval gate + issues queue

**Files:**
- Create: `src/wm/panel/approval_gate.py`
- Create: `src/wm/panel/issues_queue.py`
- Create: `tests/test_approval_gate.py`

The gate is an in-process queue of pending `Proposal` objects with `approve(id) → ApplyResult` and `reject(id, reason)`. Applied proposals route to compilers (quest compiler for quest proposals, `compile_grant_plan` for ability proposals). Blocked proposals from the adapter go straight to the issues queue.

- [ ] **Step 1: Write `tests/test_approval_gate.py`**

```python
from wm.llm.proposal_adapter import Proposal, ProposalKind
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue

def _pending_quest():
    return Proposal(kind=ProposalKind.QUEST, character_guid=5407,
                    payload={"quest_release": {"title": "x", "objective": "y", "description": "z",
                              "giver_creature_entry": 197, "objective_kind": "kill_creature",
                              "rewards": {"xp": 10}}},
                    narrative_summary="hi", provenance={"mode": "fixture"})

def test_blocked_proposal_routes_to_issues_queue():
    iq = IssuesQueue()
    gate = ApprovalGate(issues=iq)
    blocked = Proposal(kind=ProposalKind.QUEST, character_guid=5407, payload={},
                       is_blocked=True, block_reason="missing quest_release")
    gate.submit(blocked)
    assert gate.pending() == []
    assert len(iq.list_open()) == 1
    assert iq.list_open()[0].reason == "missing quest_release"

def test_pending_proposal_can_be_approved():
    iq = IssuesQueue()
    applied: list[dict] = []
    def fake_quest_compiler(p): applied.append({"kind":"quest","payload":p.payload}); return {"ok": True, "request_ids":[123]}
    def fake_ability_compiler(p): raise AssertionError("not used here")
    gate = ApprovalGate(issues=iq, quest_compiler=fake_quest_compiler, ability_compiler=fake_ability_compiler)
    p = _pending_quest()
    gate.submit(p)
    pid = gate.pending()[0].id
    result = gate.approve(pid)
    assert result.ok
    assert applied and applied[0]["kind"] == "quest"
    assert gate.pending() == []

def test_rejection_records_and_drops():
    iq = IssuesQueue()
    gate = ApprovalGate(issues=iq)
    gate.submit(_pending_quest())
    pid = gate.pending()[0].id
    gate.reject(pid, reason="operator-deferred")
    assert gate.pending() == []
    # rejected proposals are logged in issues for triage
    assert any(i.reason == "operator-deferred" for i in iq.list_open())
```

- [ ] **Step 2: Run, fail**

`pytest tests/test_approval_gate.py -v` → ImportError.

- [ ] **Step 3: Implement `src/wm/panel/issues_queue.py`**

```python
"""In-process issues queue for blocked + rejected proposals.

Persistence is out-of-scope for the vertical slice; the queue lives as
long as the panel process. Each entry carries enough to triage.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import count
from typing import Any


@dataclass(slots=True)
class Issue:
    id: int
    reason: str
    kind: str
    character_guid: int
    payload: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)


class IssuesQueue:
    def __init__(self) -> None:
        self._items: list[Issue] = []
        self._ids = count(1)

    def add(self, *, reason: str, kind: str, character_guid: int,
            payload: dict[str, Any], provenance: dict[str, Any] | None = None) -> Issue:
        item = Issue(id=next(self._ids), reason=reason, kind=kind,
                     character_guid=character_guid, payload=payload,
                     provenance=provenance or {})
        self._items.append(item)
        return item

    def list_open(self) -> list[Issue]:
        return list(self._items)
```

- [ ] **Step 4: Implement `src/wm/panel/approval_gate.py`**

```python
"""Approval gate: one queue, both loops (arc OPEN + Watcher) feed in here.

Approve = call the matching deterministic compiler. Reject = log to issues.
Blocked proposals (from the LLM adapter validator) skip the gate and go
straight to issues.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import count
from typing import Callable
from wm.llm.proposal_adapter import Proposal, ProposalKind
from wm.panel.issues_queue import IssuesQueue


@dataclass(slots=True)
class PendingProposal:
    id: int
    proposal: Proposal


@dataclass(slots=True)
class ApplyResult:
    ok: bool
    detail: dict | None = None
    error: str | None = None


QuestCompiler = Callable[[Proposal], dict]
AbilityCompiler = Callable[[Proposal], dict]
SceneCompiler = Callable[[Proposal], dict]


class ApprovalGate:
    def __init__(self, *, issues: IssuesQueue,
                 quest_compiler: QuestCompiler | None = None,
                 ability_compiler: AbilityCompiler | None = None,
                 scene_compiler: SceneCompiler | None = None) -> None:
        self._pending: list[PendingProposal] = []
        self._ids = count(1)
        self._issues = issues
        self._quest = quest_compiler
        self._ability = ability_compiler
        self._scene = scene_compiler

    def submit(self, p: Proposal) -> None:
        if p.is_blocked:
            self._issues.add(reason=p.block_reason, kind=p.kind.value,
                             character_guid=p.character_guid,
                             payload=p.payload, provenance=p.provenance)
            return
        self._pending.append(PendingProposal(id=next(self._ids), proposal=p))

    def pending(self) -> list[PendingProposal]:
        return list(self._pending)

    def approve(self, pid: int) -> ApplyResult:
        pp = self._take(pid)
        if pp is None:
            return ApplyResult(ok=False, error="not_found")
        p = pp.proposal
        compiler = {ProposalKind.QUEST: self._quest,
                    ProposalKind.ABILITY: self._ability,
                    ProposalKind.SCENE: self._scene}.get(p.kind)
        if compiler is None:
            self._issues.add(reason=f"no compiler wired for kind={p.kind.value}",
                             kind=p.kind.value, character_guid=p.character_guid,
                             payload=p.payload, provenance=p.provenance)
            return ApplyResult(ok=False, error="no_compiler")
        try:
            detail = compiler(p)
            return ApplyResult(ok=True, detail=detail)
        except Exception as e:    # catch-and-park, never crash the loop
            self._issues.add(reason=f"compiler_exception: {e}",
                             kind=p.kind.value, character_guid=p.character_guid,
                             payload=p.payload, provenance=p.provenance)
            return ApplyResult(ok=False, error=str(e))

    def reject(self, pid: int, *, reason: str) -> None:
        pp = self._take(pid)
        if pp is None: return
        self._issues.add(reason=reason, kind=pp.proposal.kind.value,
                         character_guid=pp.proposal.character_guid,
                         payload=pp.proposal.payload, provenance=pp.proposal.provenance)

    def _take(self, pid: int) -> PendingProposal | None:
        for i, x in enumerate(self._pending):
            if x.id == pid:
                return self._pending.pop(i)
        return None
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_approval_gate.py -v   # expect 3 passed
git add src/wm/panel/approval_gate.py src/wm/panel/issues_queue.py tests/test_approval_gate.py
git -c core.autocrlf=false commit -m "feat(panel): approval gate + issues queue (catch-and-park errors)"
```

---

### Task 8: Arc Runner state machine

**Files:**
- Create: `src/wm/arcs/runner.py`
- Create: `tests/test_arc_runner.py`

**Behavior:** holds the loaded `StoryModule` + current beat id; subscribes to events; on each event, if it matches the current beat's `entry_condition`, processes the beat:
- PINNED → call the *quest compiler dry-run* (no LLM, no gate); the dry-run result is the "auto-applied" plan (the demo wires the actual apply through the demo glue in Task 11). For the slice, PINNED → produce a `Proposal(is_blocked=False, narrative_summary=...)` and feed it to the gate via the `auto_apply=True` path (the gate's `submit_auto_apply` is added here).
- OPEN → call the LLM adapter (FIXTURE mode in tests) → submit the proposal to the gate.

After a beat completes (next event matches its outcome), evaluate grant points: their `when` condition + `appropriateness` predicate → produce an ability grant proposal at the gate.

- [ ] **Step 1: Extend gate with auto-apply path**

Add the following method to `src/wm/panel/approval_gate.py` (next to `submit`):

```python
    def submit_auto_apply(self, p: Proposal) -> ApplyResult:
        """PINNED beats use this — the proposal is already authored and validated;
        skip the operator approval but run through the same compiler + catch-and-park."""
        if p.is_blocked:
            self.submit(p); return ApplyResult(ok=False, error="blocked")
        # synthesize a pending entry so we reuse the same compile path
        pp = PendingProposal(id=next(self._ids), proposal=p)
        self._pending.append(pp)
        return self.approve(pp.id)
```

- [ ] **Step 2: Write `tests/test_arc_runner.py`**

```python
import json
from pathlib import Path
from wm.arcs.story_module import parse_story_module
from wm.arcs.runner import ArcRunner, RunnerEvent
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue
from wm.llm.proposal_adapter import ProposalAdapter, AdapterMode

def _load(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def _make_runner(fixture):
    iq = IssuesQueue()
    applied = []
    def quest_c(p):
        applied.append({"kind":"quest","payload":p.payload,"narrative":p.narrative_summary})
        return {"ok": True, "request_ids":[1]}
    def ability_c(p):
        applied.append({"kind":"ability","payload":p.payload})
        return {"ok": True}
    gate = ApprovalGate(issues=iq, quest_compiler=quest_c, ability_compiler=ability_c)
    adapter = ProposalAdapter(mode=AdapterMode.FIXTURE, fixture=fixture)
    module = parse_story_module(_load("control/examples/story_modules/demo_one.story_module.json"))
    runner = ArcRunner(module=module, adapter=adapter, gate=gate)
    return runner, gate, iq, applied

def test_attention_granted_auto_applies_pinned_b00():
    fixture = _load("tests/fixtures/llm/quest_proposal_basic.json")
    r, gate, iq, applied = _make_runner(fixture)
    r.on_event(RunnerEvent(kind="wm.attention.granted", character_guid=5407, params={}))
    # PINNED b00 auto-applied via gate; no pending proposal left
    assert gate.pending() == []
    assert any(a["kind"] == "quest" and a["payload"]["quest_release"]["title"] == "An Unfamiliar Weight"
               for a in applied)
    assert r.current_beat_id == "b01_zone_intro"

def test_quest_complete_b00_opens_b01_proposal_at_gate():
    fixture = _load("tests/fixtures/llm/quest_proposal_basic.json")
    r, gate, iq, applied = _make_runner(fixture)
    r.on_event(RunnerEvent(kind="wm.attention.granted", character_guid=5407, params={}))
    r.on_event(RunnerEvent(kind="quest.completed", character_guid=5407, params={"beat_ref":"b00_onboarding"}))
    pending = gate.pending()
    assert len(pending) == 1
    assert pending[0].proposal.payload["quest_release"]["title"] == "Wolves at the Vineyard"

def test_grant_point_fires_after_open_beat_quest_complete():
    fixture = _load("tests/fixtures/llm/quest_proposal_basic.json")
    r, gate, iq, applied = _make_runner(fixture)
    r.on_event(RunnerEvent(kind="wm.attention.granted", character_guid=5407, params={}))
    r.on_event(RunnerEvent(kind="quest.completed", character_guid=5407, params={"beat_ref":"b00_onboarding"}))
    # approve the b01 open proposal so the beat is "completed" from the runner's view
    gate.approve(gate.pending()[0].id)
    r.on_event(RunnerEvent(kind="quest.completed", character_guid=5407, params={"beat_ref":"b01_zone_intro",
                          "character_level": 2}))
    # ability grant point fires → ability proposal pending at gate
    abilities_pending = [p for p in gate.pending() if p.proposal.kind.value == "ability"]
    assert len(abilities_pending) == 1
    assert abilities_pending[0].proposal.payload["ability_id"] == "shadow_pulse_aura_v1"
```

- [ ] **Step 3: Run, fail**

`pytest tests/test_arc_runner.py -v` → ImportError.

- [ ] **Step 4: Implement `src/wm/arcs/runner.py`**

```python
"""Arc Runner — advances a StoryModule's beats on sensed events.

PINNED beats auto-apply via the gate (authored + validated).
OPEN beats produce an LLM proposal via the adapter and submit to the gate.
Grant points fire as their own ability proposals when their `when` event +
`appropriateness` predicate hold.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from wm.arcs.story_module import StoryModule, Beat, BeatKind, GrantPoint
from wm.llm.proposal_adapter import (
    Proposal, ProposalKind, ProposalRequest, ProposalAdapter,
)
from wm.panel.approval_gate import ApprovalGate


@dataclass(slots=True)
class RunnerEvent:
    kind: str
    character_guid: int
    params: dict[str, Any] = field(default_factory=dict)


class ArcRunner:
    def __init__(self, *, module: StoryModule, adapter: ProposalAdapter, gate: ApprovalGate) -> None:
        self.module = module
        self.adapter = adapter
        self.gate = gate
        self.current_beat_id: str | None = module.beats[0].id if module.beats else None
        self._completed_beats: set[str] = set()
        self._beat_by_id = {b.id: b for b in module.beats}

    def on_event(self, evt: RunnerEvent) -> None:
        if evt.character_guid != self.module.character_guid:
            return
        if self.current_beat_id is None:
            return

        beat = self._beat_by_id[self.current_beat_id]
        if self._event_matches(evt, beat.entry_condition):
            self._process_beat(beat, evt)
            return

        # check if this event completes a previously-applied beat → grant points
        for b in self.module.beats:
            if b.id in self._completed_beats: continue
            for gp in b.outcome.grant_points:
                if self._event_matches(evt, gp.when) and self._appropriateness_ok(gp, evt):
                    self._submit_ability_grant(gp)
            # quest-completed events also advance the runner to next beat
            if self._event_matches(evt, {"event":"quest.completed","ref":b.id}):
                self._completed_beats.add(b.id)
                self.current_beat_id = b.outcome.next_beat_ref

    # --- processing ----------------------------------------------------

    def _process_beat(self, beat: Beat, evt: RunnerEvent) -> None:
        if beat.kind is BeatKind.PINNED:
            assert beat.payload is not None
            p = Proposal(
                kind=ProposalKind.QUEST,
                character_guid=self.module.character_guid,
                payload=beat.payload,
                narrative_summary=f"PINNED beat {beat.id} ({self.module.module_id})",
                provenance={"mode": "pinned", "beat_id": beat.id},
            )
            self.gate.submit_auto_apply(p)
            self._completed_beats.add(beat.id)
            self.current_beat_id = beat.outcome.next_beat_ref
            return

        # OPEN — build a proposal request and ask the adapter
        req = ProposalRequest(
            kind=ProposalKind.QUEST,
            context={"character": {"guid": self.module.character_guid,
                                   "name": self.module.character_name}},
            intent=beat.intent or "",
            constraints=beat.constraints,
        )
        prop = self.adapter.propose(req)
        prop.provenance.setdefault("beat_id", beat.id)
        self.gate.submit(prop)
        # do NOT mark completed here; completion fires on quest.completed event

    def _submit_ability_grant(self, gp: GrantPoint) -> None:
        prop = Proposal(
            kind=ProposalKind.ABILITY,
            character_guid=self.module.character_guid,
            payload={"ability_id": gp.ability_ref, "grant_kind": gp.grant_kind},
            narrative_summary=f"grant {gp.ability_ref}",
            provenance={"mode": "grant_point"},
        )
        self.gate.submit(prop)

    # --- predicates ----------------------------------------------------

    def _event_matches(self, evt: RunnerEvent, cond: dict[str, Any]) -> bool:
        if cond.get("event") != evt.kind: return False
        if "ref" in cond and evt.params.get("beat_ref") != cond["ref"]: return False
        return True

    def _appropriateness_ok(self, gp: GrantPoint, evt: RunnerEvent) -> bool:
        return self._eval_predicate(gp.appropriateness, evt)

    def _eval_predicate(self, pred: dict[str, Any], evt: RunnerEvent) -> bool:
        # tiny DSL: {"all_of":[...]} / {"any_of":[...]} over named checks
        if "all_of" in pred:
            return all(self._eval_predicate(p, evt) for p in pred["all_of"])
        if "any_of" in pred:
            return any(self._eval_predicate(p, evt) for p in pred["any_of"])
        if "character_level_at_least" in pred:
            return int(evt.params.get("character_level", 0)) >= int(pred["character_level_at_least"])
        if "journal_has_tag" in pred:
            return str(pred["journal_has_tag"]) in evt.params.get("journal_tags", [])
        return False  # unknown predicate ⇒ fail closed
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_arc_runner.py -v   # expect 3 passed
git add src/wm/arcs/runner.py src/wm/panel/approval_gate.py tests/test_arc_runner.py
git -c core.autocrlf=false commit -m "feat(arcs): Arc Runner state machine (PINNED auto-apply, OPEN→gate, grants)"
```

---

### Task 9: Watcher loop

**Files:**
- Create: `src/wm/reactive/watcher.py`
- Create: `tests/test_watcher.py`

The Watcher subscribes to the same event stream, accumulates an event window per active character, and on every new event re-evaluates each loaded `ReactiveTemplate` via `match_trigger`. On match (with cooldown/dedupe honored), it asks the adapter for a structured proposal and submits to the gate.

- [ ] **Step 1: Write `tests/test_watcher.py`**

```python
import json
from pathlib import Path
from wm.reactive.reactive_template import parse_reactive_template
from wm.reactive.watcher import Watcher, WatcherEvent
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue
from wm.llm.proposal_adapter import ProposalAdapter, AdapterMode

def _load(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def _make_watcher(active_character_guid=5407):
    iq = IssuesQueue()
    applied = []
    def quest_c(p): applied.append(p); return {"ok": True}
    gate = ApprovalGate(issues=iq, quest_compiler=quest_c)
    adapter = ProposalAdapter(
        mode=AdapterMode.FIXTURE,
        fixture=_load("tests/fixtures/llm/quest_proposal_basic.json"),
    )
    templates = [parse_reactive_template(_load("control/examples/reactive_templates/zone_kill_bounty.json"))]
    w = Watcher(templates=templates, adapter=adapter, gate=gate,
                active_character_guid=active_character_guid)
    return w, gate, iq, applied

def test_no_match_below_threshold():
    w, gate, iq, _ = _make_watcher()
    for i in range(3):
        w.on_event(WatcherEvent(kind="kill", character_guid=5407,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    assert gate.pending() == []

def test_threshold_match_fires_proposal_at_gate():
    w, gate, iq, _ = _make_watcher()
    for i in range(8):
        w.on_event(WatcherEvent(kind="kill", character_guid=5407,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    pending = gate.pending()
    assert len(pending) == 1
    assert pending[0].proposal.kind.value == "quest"

def test_cooldown_suppresses_duplicate_fire_within_window():
    w, gate, iq, _ = _make_watcher()
    # first fire
    for i in range(8):
        w.on_event(WatcherEvent(kind="kill", character_guid=5407,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    assert len(gate.pending()) == 1
    # 8 more kills well inside cooldown_min=60 ⇒ no second fire
    for i in range(8, 16):
        w.on_event(WatcherEvent(kind="kill", character_guid=5407,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    assert len(gate.pending()) == 1

def test_other_character_events_do_not_trigger():
    w, gate, iq, _ = _make_watcher(active_character_guid=5407)
    for i in range(8):
        w.on_event(WatcherEvent(kind="kill", character_guid=9999,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    assert gate.pending() == []
```

- [ ] **Step 2: Run, fail**

`pytest tests/test_watcher.py -v` → ImportError.

- [ ] **Step 3: Implement `src/wm/reactive/watcher.py`**

```python
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
```

- [ ] **Step 4: Run + commit**

```bash
pytest tests/test_watcher.py -v   # expect 4 passed
git add src/wm/reactive/watcher.py tests/test_watcher.py
git -c core.autocrlf=false commit -m "feat(reactive): Watcher loop (match → adapter → gate, cooldown+dedupe)"
```

---

### Task 10: Onboarding starter item

**Files:**
- Create: `src/wm/onboarding/__init__.py`
- Create: `src/wm/onboarding/starter_item.py`
- Create: `tests/test_onboarding_starter_item.py`

**Pipeline:** issue a starter item to the new character (one row in the bridge's grant table — *plan-only* here, applied in the runbook); when the character uses it in-game, the bridge emits a `use_item` event with the starter item's entry id; the onboarding handler matches and emits `wm.attention.granted` into the runner.

For the slice, *applying* the item grant is part of the runbook. This task delivers (a) the deterministic starter-item *plan* (a `GrantStep` for the bridge action `player_add_item`) and (b) the *use_item → attention.granted* converter consumed by the runner. Tested in-process with synthetic events.

- [ ] **Step 1: Write `tests/test_onboarding_starter_item.py`**

```python
from wm.onboarding.starter_item import (
    build_starter_item_grant_plan, OnboardingHandler, OnboardingEvent,
)

def test_grant_plan_targets_active_character():
    plan = build_starter_item_grant_plan(character_guid=5407, item_entry=910500)
    assert plan.character_guid == 5407
    assert plan.steps and plan.steps[0].action_kind == "player_add_item"
    assert plan.steps[0].payload["item_id"] == 910500

def test_use_item_with_starter_emits_attention_granted():
    seen = []
    h = OnboardingHandler(starter_item_entry=910500,
                          active_character_guid=5407,
                          emit=lambda evt: seen.append(evt))
    h.on_event(OnboardingEvent(kind="use_item", character_guid=5407,
                               params={"item_entry": 910500}))
    assert len(seen) == 1
    assert seen[0].kind == "wm.attention.granted"
    assert seen[0].character_guid == 5407

def test_use_item_other_item_or_other_char_is_ignored():
    seen = []
    h = OnboardingHandler(starter_item_entry=910500, active_character_guid=5407,
                          emit=lambda evt: seen.append(evt))
    h.on_event(OnboardingEvent(kind="use_item", character_guid=5407, params={"item_entry": 6948}))
    h.on_event(OnboardingEvent(kind="use_item", character_guid=9999, params={"item_entry": 910500}))
    assert seen == []
```

- [ ] **Step 2: Run, fail**

`pytest tests/test_onboarding_starter_item.py -v` → ImportError.

- [ ] **Step 3: Create `src/wm/onboarding/__init__.py`**

```python
"""WM onboarding — first-time-active-character flow."""
```

- [ ] **Step 4: Implement `src/wm/onboarding/starter_item.py`**

```python
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
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_onboarding_starter_item.py -v   # expect 3 passed
git add src/wm/onboarding/ tests/test_onboarding_starter_item.py
git -c core.autocrlf=false commit -m "feat(onboarding): starter-item plan + use_item→attention.granted handler"
```

---

### Task 11: End-to-end slice demo CLI (integration test against a fake bridge)

**Files:**
- Create: `src/wm/cli/__init__.py` (if not present)
- Create: `src/wm/cli/slice_demo.py`
- Create: `tests/test_slice_demo.py`

The demo CLI wires Onboarding + Arc Runner + Watcher + Adapter (fixture by default; `--live` to use LM Studio) + Approval Gate + Issues Queue + a *fake quest/ability compiler* (logs would-be native actions to stdout). It loads the demo module + the 10 reactive templates + the 2 ability specs. It exposes commands:
- `boot --character <guid>`: set up + emit a synthetic `use_item` so onboarding fires.
- `step`: print pending proposals; in tests, autoresponds approve/reject from a queued operator script.

For the slice, `slice_demo.py` exposes the wired runtime as a Python API and a tiny CLI; the integration test exercises a full happy-path through the API.

- [ ] **Step 1: Write `tests/test_slice_demo.py`**

```python
from wm.cli.slice_demo import SliceRuntime, ScriptedOperator

def test_happy_path_demo():
    rt = SliceRuntime.bootstrap(character_guid=5407, starter_item_entry=910500)
    op = ScriptedOperator(rt.gate)
    # 1. player uses starter item → attention.granted → b00 PINNED auto-applies
    rt.feed_use_item(item_entry=910500)
    assert rt.runner.current_beat_id == "b01_zone_intro"
    # 2. player completes b00's quest → b01 OPEN proposal appears
    rt.feed_quest_completed(beat_ref="b00_onboarding")
    op.approve_next()  # operator approves
    # 3. player completes b01's quest → grant point 1 fires
    rt.feed_quest_completed(beat_ref="b01_zone_intro", character_level=2)
    op.approve_next()  # approve the ability grant
    # 4. Watcher: 8 zone kills in the window → bounty proposal
    for i in range(8):
        rt.feed_kill(creature_family="murloc", zone="elwynn", ts=i)
    op.approve_next()  # approve the watcher bounty
    # 5. complete b02 + b03 to reach finale grant
    rt.feed_quest_completed(beat_ref="b01_zone_intro", character_level=2)  # noop, already past
    rt.feed_quest_completed(beat_ref="b02_complication", character_level=3)
    rt.feed_quest_completed(beat_ref="b03_finale", character_level=4)
    # gate may now have b02 OPEN proposal, b03 PINNED auto-apply, then echo_lash grant
    while rt.gate.pending():
        op.approve_next()
    applied_kinds = [a["kind"] for a in rt.applied_log]
    assert "quest" in applied_kinds
    assert applied_kinds.count("ability") >= 1
    assert rt.issues.list_open() == []  # no parked errors in happy path
```

- [ ] **Step 2: Run, fail**

`pytest tests/test_slice_demo.py -v` → ImportError.

- [ ] **Step 3: Implement `src/wm/cli/slice_demo.py`**

```python
"""Slice demo runtime — wires onboarding + Arc Runner + Watcher + gate.

Exposes a Python API used by tests + a minimal CLI for the BridgeLab run.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any
from wm.abilities.grant_compiler import compile_grant_plan
from wm.abilities.schema import parse_ability
from wm.arcs.runner import ArcRunner, RunnerEvent
from wm.arcs.story_module import parse_story_module
from wm.llm.proposal_adapter import (
    ProposalAdapter, AdapterMode, Proposal, ProposalKind,
)
from wm.onboarding.starter_item import OnboardingHandler, OnboardingEvent
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue
from wm.reactive.reactive_template import parse_reactive_template
from wm.reactive.watcher import Watcher, WatcherEvent

DEMO_MODULE_PATH = "control/examples/story_modules/demo_one.story_module.json"
TEMPLATE_DIR     = "control/examples/reactive_templates"
ABILITY_DIR      = "control/examples/abilities"
DEFAULT_FIXTURE  = "tests/fixtures/llm/quest_proposal_basic.json"


def _load(p: str | Path) -> dict: return json.loads(Path(p).read_text(encoding="utf-8"))


@dataclass(slots=True)
class SliceRuntime:
    gate: ApprovalGate
    issues: IssuesQueue
    runner: ArcRunner
    watcher: Watcher
    onboarding: OnboardingHandler
    applied_log: list[dict] = field(default_factory=list)
    abilities_by_id: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def bootstrap(cls, *, character_guid: int, starter_item_entry: int,
                  adapter_mode: AdapterMode = AdapterMode.FIXTURE,
                  fixture_path: str = DEFAULT_FIXTURE) -> "SliceRuntime":
        issues = IssuesQueue()
        applied_log: list[dict] = []

        # ability catalog
        abilities = {
            (a := parse_ability(_load(p))).id: a
            for p in Path(ABILITY_DIR).iterdir() if p.suffix == ".json"
        }

        def quest_compiler(p: Proposal) -> dict:
            applied_log.append({"kind": "quest", "payload": p.payload,
                                "narrative": p.narrative_summary,
                                "provenance": p.provenance})
            return {"ok": True}

        def ability_compiler(p: Proposal) -> dict:
            ability_id = p.payload.get("ability_id")
            spec = abilities.get(ability_id)
            if spec is None:
                raise ValueError(f"unknown ability_id={ability_id}")
            plan = compile_grant_plan(spec, character_guid=p.character_guid)
            applied_log.append({"kind": "ability", "ability_id": ability_id,
                                "steps": [s.__dict__ for s in plan.steps]})
            return {"ok": True, "plan": plan}

        def scene_compiler(p: Proposal) -> dict:
            applied_log.append({"kind": "scene", "payload": p.payload})
            return {"ok": True}

        gate = ApprovalGate(issues=issues,
                            quest_compiler=quest_compiler,
                            ability_compiler=ability_compiler,
                            scene_compiler=scene_compiler)

        # Arc Runner
        module = parse_story_module(_load(DEMO_MODULE_PATH))
        if module.character_guid != character_guid:
            module.character_guid = character_guid  # the demo lets you target any char
        adapter = ProposalAdapter(mode=adapter_mode, fixture=_load(fixture_path))
        runner = ArcRunner(module=module, adapter=adapter, gate=gate)

        # Watcher
        templates = [parse_reactive_template(_load(p))
                     for p in sorted(Path(TEMPLATE_DIR).iterdir())
                     if p.suffix == ".json"]
        watcher = Watcher(templates=templates, adapter=adapter, gate=gate,
                          active_character_guid=character_guid)

        # Onboarding
        def _on_attention(evt: OnboardingEvent) -> None:
            runner.on_event(RunnerEvent(kind=evt.kind, character_guid=evt.character_guid, params={}))
        onboarding = OnboardingHandler(starter_item_entry=starter_item_entry,
                                       active_character_guid=character_guid,
                                       emit=_on_attention)

        return cls(gate=gate, issues=issues, runner=runner, watcher=watcher,
                   onboarding=onboarding, applied_log=applied_log,
                   abilities_by_id=abilities)

    # --- event feeders (test API + bridge bridge for the runbook) -------

    def feed_use_item(self, *, item_entry: int) -> None:
        self.onboarding.on_event(OnboardingEvent(
            kind="use_item", character_guid=self.runner.module.character_guid,
            params={"item_entry": item_entry}))

    def feed_quest_completed(self, *, beat_ref: str, character_level: int = 1) -> None:
        self.runner.on_event(RunnerEvent(
            kind="quest.completed", character_guid=self.runner.module.character_guid,
            params={"beat_ref": beat_ref, "character_level": character_level}))

    def feed_kill(self, *, creature_family: str, zone: str, ts: int) -> None:
        self.watcher.on_event(WatcherEvent(
            kind="kill", character_guid=self.runner.module.character_guid,
            params={"creature_family": creature_family, "zone": zone}, ts=ts))


@dataclass(slots=True)
class ScriptedOperator:
    gate: ApprovalGate

    def approve_next(self) -> None:
        pending = self.gate.pending()
        if not pending: return
        self.gate.approve(pending[0].id)
```

- [ ] **Step 4: Run + commit**

```bash
pytest tests/test_slice_demo.py -v   # expect 1 passed
git add src/wm/cli/slice_demo.py tests/test_slice_demo.py
# create src/wm/cli/__init__.py only if missing
if [ ! -f src/wm/cli/__init__.py ]; then echo '"""WM CLIs."""' > src/wm/cli/__init__.py; git add src/wm/cli/__init__.py; fi
git -c core.autocrlf=false commit -m "feat(cli): slice_demo runtime — full loop in-process (fixture LLM)"
```

---

### Task 12: BridgeLab runbook + live-proof entry

**Files:**
- Create: `docs/WM_VERTICAL_SLICE_RUNBOOK.md`
- Modify: `docs/LIVE_PROOF_BACKLOG.md` (append entry)

The runbook gives the operator the exact commands to: build a fresh demo character on BridgeLab, install the starter item via the native bus, boot the slice runtime against the live worldserver event spine, drive the demo through the approval gate, and record evidence (DB rows + result JSON deltas like the 0D proofs).

- [ ] **Step 1: Author `docs/WM_VERTICAL_SLICE_RUNBOOK.md`**

```markdown
Status: DESIGN_ONLY
Last verified: 2026-05-20
Verified by: Claude
Doc type: runbook

# WM Vertical Slice — BridgeLab Runbook

## Preconditions

- BridgeLab stack up: `start-bridge-lab-all.bat` (MySQL 33307, authserver, worldserver, native watch).
- Demo character created (level-bracket appropriate, in zone 12). Note its `character_guid` (substitute for `5407` below).
- Slice tests green: `pytest tests/test_slice_demo.py tests/test_arc_runner.py tests/test_watcher.py -q`.

## Run

1. Grant the starter item to the demo character through the native bus (one `player_add_item` row):

   ```bash
   "/d/WOW/WM_BridgeLab/deps/mysql/bin/mysql.exe" --host=127.0.0.1 --port=33307 --user=acore --password=acore acore_world -e \
     "INSERT INTO wm_bridge_action_request (IdempotencyKey,PlayerGUID,ActionKind,PayloadJSON,Status,CreatedBy,RiskLevel) \
      VALUES ('onboarding.starter_item:910500:5407',5407,'player_add_item','{\"item_id\":910500,\"count\":1}','pending','wm-runbook','low');"
   ```

2. Boot the slice runtime against the live worldserver:

   ```bash
   python -m wm.cli.slice_demo --character 5407 --starter-item 910500
   ```

   The runtime opens the panel (or prints pending proposals to stdout); it
   subscribes to the bridge event spine for `quest.completed`, `kill`,
   `use_item`, `death`, `zone_change` rows tagged with `character_guid=5407`.

3. **In-client:** Log in as the demo character. Use the starter item.
   The native bridge emits `use_item` → onboarding → `wm.attention.granted` →
   b00 PINNED auto-applies → the b00 quest is published into your log via
   the existing content-release pipeline.

4. Complete the b00 quest in-game. The Arc Runner advances; the b01 OPEN
   proposal appears in the panel. **Approve it.** Complete b01.

5. At ≥ character level 2 + on completing b01, the **shadow_pulse_aura_v1**
   ability grant proposal appears. Approve it. The passive visible aura
   becomes active on the character (verify via DB row in
   `character_aura` / `acore_world.wm_bridge_event` or the visible buff).

6. Drive the Watcher: kill ~8 of one creature family in zone 12 within
   15 minutes. A `zone_kill_bounty` proposal appears at the panel.
   Approve it; complete the bounty quest in-game.

7. Continue: b02 OPEN → approve → complete → b03 PINNED auto-applies →
   defeat the finale creature → **echo_lash_v1** grant proposal →
   approve → active ability becomes available.

## Evidence to capture

- DB rows: `wm_bridge_action_request` (Status='done') for the starter
  item grant, each PINNED quest publish, each approved grant.
- `LIVE_PROOF_BACKLOG.md`: byte-identical-style log entry per Task 12 below.
- Optional: panel screenshot of the approval queue mid-run.

## Failure triage

The loop never crashes. Anything that goes wrong lands in the issues
queue (panel `/issues` view, or `rt.issues.list_open()` from a REPL).
Each entry carries `reason`, `kind`, `character_guid`, `payload`,
`provenance`. Triage between turns; rerun.
```

- [ ] **Step 2: Append a LIVE_PROOF_BACKLOG entry (template — leave PARTIAL until the BridgeLab run is done)**

```bash
cat >> docs/LIVE_PROOF_BACKLOG.md <<'EOF'

### WM Vertical Slice — IN-ENGINE PROOF: `PARTIAL` (awaiting live run)

Planned 2026-05-20 (Claude). The slice runtime, schemas, and demo
content land in commits per
[2026-05-20-wm-vertical-slice plan](superpowers/plans/2026-05-20-wm-vertical-slice.md).
Awaiting live BridgeLab run per
[WM_VERTICAL_SLICE_RUNBOOK.md](WM_VERTICAL_SLICE_RUNBOOK.md): one new
character → b00 PINNED auto-apply → b01 OPEN approve → grant 1 →
zone_kill_bounty Watcher fire + approve → b02 OPEN approve → b03 PINNED
auto-apply → grant 2. Evidence: action-request rows + visible buffs +
in-client quest log.
EOF
```

- [ ] **Step 3: Commit**

```bash
git add docs/WM_VERTICAL_SLICE_RUNBOOK.md docs/LIVE_PROOF_BACKLOG.md
git -c core.autocrlf=false commit -m "docs(slice): vertical-slice runbook + live-proof entry stub"
```

---

## Release Definition (slice done when)

1. All 10 task-test files pass: `pytest tests/test_story_module_schema.py tests/test_reactive_template_schema.py tests/test_ability_schema.py tests/test_demo_data_loads.py tests/test_ability_grant_compiler.py tests/test_proposal_adapter.py tests/test_approval_gate.py tests/test_arc_runner.py tests/test_watcher.py tests/test_onboarding_starter_item.py tests/test_slice_demo.py -q` → all green.
2. `python -m wm.cli.slice_demo --character <guid> --starter-item 910500` runs without crashing in fixture mode.
3. Schemas exist and self-describe at `control/schemas/wm.{story_module,reactive_template,ability}.v1.schema.json`.
4. 10 reactive templates exist as JSON files in `control/examples/reactive_templates/`.
5. Demo story module + 2 ability specs exist in `control/examples/`.
6. BridgeLab live proof recorded in `LIVE_PROOF_BACKLOG.md` per the runbook.
7. Issues queue empty at the end of the live happy-path (no parked errors); any non-happy path is triaged and recorded as a follow-up, not a slice blocker.

## Self-Review Notes

- Each task is TDD with concrete tests + concrete code. No "TBD".
- Per-task commit message uses Conventional Commits and the touched module scope.
- No spell-monolith edits.
- The LLM is opt-in (`AdapterMode.LIVE`); CI + slice tests use `FIXTURE` so the build never depends on a model being up.
- Errors catch-and-park: every compile/adapter path either returns a `Proposal` or an `Issue` — nothing raises into the loop.
- Catalog growth is data-only: adding template #11 = add a JSON file; adding ability primitive #5 = extend `schema.py` + add row.
