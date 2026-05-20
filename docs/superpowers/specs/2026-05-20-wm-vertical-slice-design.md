Status: DESIGN_ONLY
Last verified: 2026-05-20
Verified by: Claude
Doc type: design

# WM Vertical Slice — Design

## North Star (one paragraph)

A presentable end-to-end demo of the WM (World Master) loop for one new
character: the player gains WM attention, a Python **Arc Runner** drives
a per-character authored **story module** (mixed authored + LLM-filled
beats), in parallel a **Watcher** senses live events and proposes
dynamic content from a small catalog of universal reactive templates,
all proposals go through one **LLM-propose → operator-approve →
deterministic-compile → native-bus** gate, and the player perceives the
results in-game (quests, NPCs, abilities). Reuses the existing
infrastructure (context packs, content-release pipeline, native action
bus, shell bank, journal, LM Studio adapter); no spell-monolith
refactor; failures park in an issues queue, the loop never crashes.

## Why this shape (vs. alternatives we ruled out)

- **LLM-first ("messy on-the-fly"):** rejected — narrative coherence
  is brittle, demo-flakey.
- **Fully-authored ("LLM = flavor only"):** rejected — defeats the
  point of an LLM-driven WM.
- **Hybrid pinned/open beats + reactive Watcher (chosen):** authored
  spine guarantees coherence and a reliable demo path; OPEN beats and
  reactive templates are where the LLM actually generates content; the
  operator-approval gate makes the whole thing safe to demo.

Aligned with [ROADMAP.md](../../ROADMAP.md) Track 1 (Personal Journey
Spine), Track 2 (Arc + Reward Factory), Track 3 (Wild Powers),
Track 4 (Live Scene Director), Track 5 (LLM on Locked Contracts).
Explicitly outside roadmap "Not Roadmap": no addon/log transport, no
parallel runner, no freeform SQL/GM/shell lane, no broad coordinator
splitting before behaviour is locked.

## Architecture

Strict reuse of the locked architecture (Python decides/validates/
publishes/audits; native modules sense + run typed actions + shell
behaviour; `control/` is the schema/contract lane; LLM proposes only,
never mutates).

```
                 native bridge event spine (existing)
                            │
        ┌───────────────────┼────────────────────┐
        ▼                                        ▼
   Arc Runner                                Watcher
   (per-character                            (reactive templates,
    story module                              event-pattern match,
    state machine,                            cooldown + dedupe,
    PINNED auto-apply,                        scope=active_character)
    OPEN → LLM)
        │                                        │
        └──────────────► LLM adapter ◄───────────┘
                         (LM Studio,
                          context pack +
                          intent/template →
                          structured proposal
                          in existing schemas)
                                │
                                ▼
                       Approval Gate (panel)
                       one-click approve/reject
                       idempotency + stale-event
                                │
                                ▼
                  Deterministic compilers (existing)
                  quest publish · scene · ability grant
                                │
                                ▼
              Native action bus / managed publish (existing)
                                │
                                ▼
                              In-game
                                │
                                ▼
                  Journal (existing layer, read back
                  into future context packs)
```

## Components (reuse vs. new)

| Component | Status | Role |
|---|---|---|
| Native action bus + event spine | reuse (post-0D) | WM hands + raw senses |
| Context packs (`context/`) | reuse | Deterministic snapshot fed to LLM |
| Content-release pipeline, shell bank, journal | reuse | Compilers; narrative record |
| Control panel + LM Studio (`panel/`, `llm/`) | reuse + extend | WM eyes/hands UI; approval gate view |
| Story Module (`wm.story_module.v1`) | **new** | Per-character authored spine |
| Arc Runner (extend `arcs/`) | **new** | State machine advancing beats on sensed events |
| Watcher (extend `reactive/`, `events/`) | **new** | Reactive content loop |
| Reactive Template (`wm.reactive_template.v1`) + ~10 authored templates | **new** | Universal event-pattern → content recipe |
| Approval Gate + LLM adapter | **new** | Single propose-validate-approve path |
| Ability schema (`wm.ability.v1`) + grant compiler | **new** | Small real schema; expandable catalog |
| Onboarding (starter item → attention aura) | new (thin) | First-time WM-active character |

## Schemas (new)

All under `control/schemas/` with example instances in
`control/examples/`; validated by the same `wm.content.release`-style
validator pattern.

### `wm.story_module.v1` — per-character authored spine

```jsonc
{ "schema": "wm.story_module.v1",
  "module_id": "<stable-id>",
  "character_guid": 5407,
  "character_name": "<new-demo-char>",
  "premise": "<prose, 1-3 sentences>",
  "tone": "<short tone tag>",
  "constraints": {
    "zone_whitelist": [<zone ids>],
    "level_band": [<min>, <max>],
    "id_ranges": { "quest": [<start>,<end>], "creature": [...], "item": [...], "shell_spell": [...] },
    "ability_themes": ["<theme-id>", ...]
  },
  "beats": [
    {
      "id": "b00_onboarding",
      "kind": "PINNED",
      "entry_condition": { "event": "wm.attention.granted" },
      "payload": { /* fully-authored quest_release / scene spec, ready for compiler */ },
      "outcome": { "next_beat_ref": "b01_zone_intro",
                   "grant_points": [] }
    },
    {
      "id": "b01_zone_intro",
      "kind": "OPEN",
      "entry_condition": { "event": "quest.completed", "ref": "b00_onboarding" },
      "intent": "<prose paragraph for the LLM: arc beat purpose + tone>",
      "constraints": {
        "giver_pool": [<npc ids>],
        "location_pool": [<zone/area ids>],
        "ability_theme_hint": "<theme>",
        "max_objectives": 2
      },
      "outcome": {
        "next_beat_ref": "b02_<...>",
        "grant_points": [
          { "grant_kind": "ability",
            "ability_ref": "shadow_pulse_aura_v1",
            "when": { "event": "quest.completed", "ref": "b01_zone_intro" },
            "appropriateness": { "all_of": [ {"journal_has_tag": "shadow_engagement"},
                                             {"character_level_at_least": 65} ] } }
        ]
      }
    }
    /* … 3-4 more beats; final is PINNED finale … */
  ],
  "journal_template": "<optional narrator voice>"
}
```

### `wm.reactive_template.v1` — universal Watcher template

```jsonc
{ "schema": "wm.reactive_template.v1",
  "id": "zone_kill_bounty",
  "narrative_hook": "WM notices you've been thinning the <creature_family> in <zone>.",
  "trigger": {
    "event": "kill",
    "params": { "creature_family": "<slot>", "zone": "<slot>",
                "count": { "min": 8, "window_min": 15 } },
    "scope": "active_character",
    "cooldown_min": 60,
    "dedupe_key": "zone_kill:{zone}:{creature_family}"
  },
  "recipe": {
    "kind": "quest",
    "compiler": "wm.content.release/repeatable_bounty",
    "slots": {
      "creature_family": "trigger.creature_family",
      "zone": "trigger.zone",
      "reward_theme": "<llm-filled>",
      "title": "<llm-filled>",
      "description": "<llm-filled>"
    }
  },
  "guards": {
    "feasibility_tier": "T1",
    "max_concurrent": 1,
    "idempotency_key_template": "watch:zone_kill_bounty:{character_guid}:{zone}:{creature_family}"
  }
}
```

**Starter catalog (~10 templates, authored as data):**
`zone_kill_bounty`, `repeated_death_nemesis`, `opportunity_caravan`,
`idle_ambush`, `lore_artifact_finder`, `escalation_rival`,
`escort_runner`, `hunter_spirit`, `stash_pinger`, `outbreak_warden`.
Each is a JSON file in `control/examples/reactive_templates/`. Adding
template #11 = add a JSON file; no code change.

### `wm.ability.v1` — small real schema

```jsonc
{ "schema": "wm.ability.v1",
  "id": "shadow_pulse_aura_v1",
  "name": "Shadow Pulse",
  "version": 1,
  "client_tier": "T2",
  "feasibility_notes": "<short>",
  "type": "passive",         // passive | active | stance
  "target": "self",          // self | self_aoe | single_friend | single_enemy
  "effect": {                // EXACTLY ONE primitive
    "kind": "stat_aura",     // stat_aura | periodic_damage | on_hit_proc | spawn_actor
    "stat": "spell_power_shadow", "amount": 24, "duration": "persistent"
  },
  "shell_binding": {
    "shell_bank_ref": "<shell-id>",
    "visible_aura_spell_id": <id>
  },
  "grant_policy": {
    "scope": "active_character",
    "persistence": "persistent",
    "revoke_path": "<existing managed-rollback record>"
  }
}
```

Four primitives (`stat_aura`, `periodic_damage`, `on_hit_proc`,
`spawn_actor`) chosen to be deliberately differentiated; cover Wild
Powers' opening surface; catalog grows by adding rows. The
**appropriateness** rule on a grant point is a small declarative
predicate (`all_of` / `any_of` over named checks like
`journal_has_tag`, `character_level_at_least`, `quest_completed`) —
deliberately tiny, evaluated deterministically by the runner; the
implementation plan pins the exact predicate grammar.

## Data flow (per turn)

1. Native bridge writes an event row (kill / quest_completed /
   use_item / death / zone_change).
2. Event spine fans out to Arc Runner *and* Watcher (no second
   runner — both subscribe to the same spine).
3. **Arc Runner** — event matches current beat's `entry_condition`?
   - **PINNED**: payload → deterministic compiler →
     bus/managed-publish. **Auto-applies** (already authored +
     validated). Logged + journaled, not gated.
   - **OPEN**: build context pack + beat intent → LLM adapter →
     structured proposal in the existing release/quest/scene schemas
     → schema-validate → approval gate.
4. **Watcher** — each reactive template scans the event spine for
   trigger matches (with cooldown + dedupe + `scope=active_character`,
   reusing the existing player-isolation pattern so triggers from
   other characters cannot influence the active WM character). On
   match: build context pack + template + slot intents → LLM adapter →
   structured proposal → approval gate.
5. **Approval Gate** (panel "WM hands & eyes" view) — pending
   proposals (arc OPEN + Watcher) show with full diff/preview;
   operator clicks approve or reject. Direct-apply disabled by
   default; idempotency + stale-event gates apply.
6. On approve → existing deterministic compiler → native action bus /
   managed publish → in-game.
7. **Grant points** fire as their own proposal at the gate when the
   "appropriate" condition is met (typically `quest.completed` for
   the relevant beat) — same path as arc/watcher.
8. **Journal** — every PINNED auto-apply *and* every approved
   proposal writes a journal entry. The journal is read back into
   future context packs, closing the narrative loop.

## Demo scenario (locked defaults)

- **Character:** a fresh char (not Jecia 5406, who's mid-arc); name
  decided at module-authoring time. Level-bracket-appropriate.
- **Onboarding trigger:** *use a WM starter item* (a consumable issued
  to the character). On use → existing native bridge action grants
  the WM attention aura → emits `wm.attention.granted` → Arc Runner
  instantiates the module.
- **Module shape (~5 beats):**
  - `b00_onboarding` — **PINNED**: starter-item lore quest in the
    starting zone; pinned giver/text/objective. Auto-applies.
  - `b01_zone_intro` — **OPEN**: LLM generates a 1-objective quest
    from the beat intent + context pack; operator approves.
  - **Grant point 1** (after b01): passive `stat_aura` ability via
    schema, grant proposal at the gate.
  - `b02_complication` — **OPEN**: second LLM-generated quest, may
    branch on player history in the journal.
  - `b03_finale` — **PINNED** finale quest with managed-item reward.
  - **Grant point 2** (after b03): active `periodic_damage` *or*
    `on_hit_proc` ability via schema.
- **Watcher during the run:** the 10-template catalog is active.
  At minimum, the `zone_kill_bounty` template should fire once during
  the demo (parameters tuned so the demo path triggers it); the
  operator approves it inline. Other templates remain armed; firing
  any of them during the demo is bonus, not required.

## Error handling

- **Catch-and-park, never crash.** Every stage wraps failures into a
  structured "blocked proposal" row (reason + payload + source event
  + character) surfaced in a panel **issues queue**. Operator triages
  between turns. No exhaustive edge-case hardening.
- **Atomic apply.** Compilers validate-then-apply per proposal; on
  partial failure, the existing managed-publish rollback record
  reverts and the proposal lands in the issues queue.
- **Idempotency keys** on every proposal; **stale-event checks** skip
  proposals derived from events older than the threshold or already
  consumed. Both are existing bus conventions, inherited.
- **Schema-invalid LLM output** is rejected with zero side effects
  (Track 5 exit criterion). Issues queue records the raw response
  for triage.
- **Operator rejects** = zero side effects, journal not written for
  that proposal.

## Testing (minimum, presentable)

- **Schema validators** for the three new schemas — cheap,
  deterministic, run in CI.
- **One happy-path live-proof on BridgeLab** (pattern:
  [FULL_LOOP_PROOF_RUNBOOK.md](../../FULL_LOOP_PROOF_RUNBOOK.md)):
  attention → b00 PINNED auto-applies → quest published → completed
  → b01 OPEN proposal → approve → quest published → completed →
  grant-point 1 → approve → ability persistent and visible → at
  least one `zone_kill_bounty` Watcher proposal → approve → bounty
  published → completed → b02/b03 → grant-point 2 → finale. Recorded
  in `LIVE_PROOF_BACKLOG.md`.
- **Unit tests only where cheap:** schema validators, Watcher
  `trigger.match()`, the appropriateness-condition evaluator. No
  deep coverage of compilers/native (already proven by 0D + existing
  live proofs).

## Scope boundaries (YAGNI)

In:
- 1 story module, ~5 beats, 1 new character.
- ~10 reactive templates as JSON catalog data.
- Ability schema with 4 primitives; demo grants 2 abilities (1 passive
  `stat_aura`, 1 active `periodic_damage` or `on_hit_proc`).
- LLM via existing LM Studio panel path.
- One happy-path live proof.

Out (explicit):
- No spell-monolith refactor. `wm_spell_runtime.cpp` stays as-is; new
  abilities use the existing shell-bank publish + native binding seams.
- No new addon/log transport, no parallel runner.
- No freeform SQL/GM/shell/config-edit lane from LLM proposals.
- No exhaustive ability taxonomy now — primitives 5..N are catalog
  additions in follow-up specs.
- No multi-character concurrency in the slice (one active WM
  character at a time).
- No client patch work beyond what existing shell bank already
  delivers (T1/T2 only in the demo abilities).

## Reuse map (what hooks to what)

| Existing piece | Slice uses it as |
|---|---|
| `src/wm/context/` | Build context packs for OPEN beats + reactive proposals |
| `src/wm/content/` + `src/wm/content/preflight.py` | Validate proposals before compile |
| `src/wm/spells/shell_bank.py`, `publish.py` | Publish ability shells from `wm.ability.v1` |
| `src/wm/journal/` | Journal entries for every applied event |
| `src/wm/panel/` + `src/wm/llm/` + `CONTROL_PANEL_LM_STUDIO_V1.md` | Approval gate UI + LM Studio adapter |
| `src/wm/reactive/`, `src/wm/events/` | Watcher's home (extend, not replace) |
| `src/wm/arcs/` | Arc Runner's home (extend) |
| `wm_bridge_action_request` / event spine (post-0D) | Apply target + sensing source |
| `wm.content.release` pipeline | Quest/scene compiler reused for arc + Watcher recipes |
| `LIVE_PROOF_BACKLOG.md`, `FULL_LOOP_PROOF_RUNBOOK.md` | Where the slice's live-proof lands |

## Post-slice follow-ups (out of this spec)

- Expand ability primitives beyond 4 (the full taxonomy you asked
  for: stances, autocast, more targeting modes, push/pull/swap/
  reaction-flip effects) — additive, schema-versioned, catalog-only.
- Expand reactive templates beyond ~10 (still data-only).
- Multi-character / handoff between active WM characters.
- LLM-decides-without-approval (only after deterministic compilers
  are "boring" per Roadmap step 8).
- Spell-monolith decomposition — revisit only when behaviour
  changes require it (the 0E analysis is preserved in
  `SPELL_RUNTIME_SPLIT_MAP.md`).
