Status: PLAN
Last verified: 2026-06-01
Verified by: Claude
Doc type: program implementation plan

# Autonomous World Master — Program Implementation Plan

> **For agentic workers:** this is a *program* spanning several sub-projects.
> Each phase below is sized to become its own `superpowers:writing-plans` plan and
> be executed task-by-task. Build in the listed order; later phases depend on
> earlier ones. Every code task is TDD (write the failing test first), commits are
> frequent, and no safeguard is weakened. Native (C++) phases require a worldserver
> rebuild + BridgeLab live-proof and are inherently live-coupled.

**Goal:** turn the current reactive, confirm-gated, operator-supervised WM into a
proactive, policy-bounded, self-directed world master — without weakening the
typed-action / validate / audit / rollback safety model.

**Sequencing rationale:** Phase 6 (Autonomy Loop) is the keystone and is pure
Python on existing primitives, so it ships first and is testable offline. Phase 7
(verbs) gives WM a richer body to act through. Phase 8 wires the dormant living-
world modules into the loop. Phase 9 makes memory drive decisions. Phase 10 hardens.

**Dependency graph:**
```
Phase 6 (Autonomy Loop) ──► Phase 8 (Living systems as candidate sources)
        │                          ▲
        ├──► Phase 9 (Memory/retrieval/outcome) ──┘
        │
Phase 7 (Native verbs) ──► richer actions for 6/8 (parallelizable after 6.4)
Phase 10 (Hardening/split) — after 6 is live-proven
```

---

## Current baseline (what exists, do not rebuild)

- Sense→DB→read spine; presence/perception heartbeats; native event sensors.
- Typed action bus: `wm_bridge_action_request` + `wm_bridge_action_policy`;
  Python `control/` pipeline (validate → policy gate → idempotent apply → audit →
  rollback). **27 of 100 native verbs implemented.**
- Conversational layer (Phases 1–5): `service.py` chat loop, `intent.py`/
  `intent_extract.py`, `ambient.py`, `memory_extract.py`, `scene_compose.py`,
  `spawn_args.py`, `targets/name_resolver.py`.
- Content: `content/release.py`, quest publish/rollback, arcs/reward factory,
  `candidates/release_pack.py`.
- Memory/world (built as modules, NOT wired into the live loop): `character/journey.py`
  (`wm_character_*` tables), `journal/*`, `subjects/*`, `context/pack.py`+`builder.py`,
  `living/{nemesis,patron,mentor,oath,oath_watcher,ecology,rumor,rumor_propagation,
  legend,zone_mood,journal_trigger,catalog}.py`.

---

## PHASE 6 — Autonomy Loop (keystone)

**Goal:** WM wakes on its own cadence, assembles a per-character decision context,
asks the LLM to choose a next move from a *validated candidate set* (or do nothing),
applies it within an autonomy governor (no per-action human confirm, full audit +
rollback), and records the outcome.

**New module dir:** `src/wm/autonomy/`. All pure-Python, offline-testable with fakes.

### Task 6.1 — Autonomy governor
**Files:** create `src/wm/autonomy/governor.py`; test `tests/autonomy/test_governor.py`.
- `@dataclass AutonomyBudget`: `max_actions_per_window`, `window_seconds`,
  `max_risk` (`off|low|medium|high`), `cooldown_seconds`, `per_kind_caps: dict`.
- `@dataclass GovernorDecision`: `allow: bool`, `reason: str`, `requires_review: bool`.
- `class AutonomyGovernor`: `evaluate(*, action_kind, risk, recent_actions, now) ->
  GovernorDecision`. Rules: reject if `risk > max_risk`; if `risk == max_risk` and
  it's mutating → `requires_review=True` (queue, don't auto-apply); enforce window
  rate cap + per-kind caps + cooldown.
- Reads budget from control config (`autonomy_*` keys) so it's operator-tunable.
- **Tests:** under-cap allows; over-cap rejects with reason; risk above max rejects;
  risk at max → requires_review; per-kind cap independent of global; cooldown blocks.
- **Exit:** governor is the single chokepoint every autonomous action passes.

### Task 6.2 — Decision context assembler
**Files:** create `src/wm/autonomy/decision_context.py`; test `tests/autonomy/test_decision_context.py`.
- `build_decision_context(*, settings, player_guid) -> dict` (schema
  `wm.autonomy.decision_context.v1`) composing, from existing builders:
  presence/perception (`world_context`), `build_session_context_pack` (journey/arc/
  unlocks/steering), recent events (`EventStore.list_recent_events`), and a
  `journal` summary (`journal/summarizer.py`). Bounded + compact (token-aware, reuse
  `_voice_world_digest`-style trimming).
- **Tests:** assembles from injected fakes; trims to caps; tolerates missing sections.
- **Exit:** one deterministic, bounded "what's going on with this character" packet.

### Task 6.3 — Candidate set builder
**Files:** create `src/wm/autonomy/candidates.py`; test `tests/autonomy/test_autonomy_candidates.py`.
- `build_candidate_moves(*, decision_context) -> list[CandidateMove]` where a
  `CandidateMove` = `{move_kind, title, summary, payload_template, risk, source}`.
- V1 sources: `say_to_player` (ambient/flavor), `offer_scene` (reuse `scene_compose`
  recipes), `advance_arc` (from `character/journey.py` arc state + `arcs/factory.py`),
  `grant_reward` (from `candidates/release_pack.py`). Each candidate is already
  schema-valid before the LLM sees it.
- **Tests:** candidates only reference implemented verbs/recipes; empty when nothing
  eligible; arc candidate respects current arc stage.
- **Exit:** the LLM never invents actions — it selects from pre-validated candidates.

### Task 6.4 — Decision step + executor
**Files:** create `src/wm/autonomy/decider.py`; test `tests/autonomy/test_decider.py`.
- `decide_next_move(*, client, decision_context, candidates) -> ChosenMove | None`:
  schema-bound `generate_json` (`wm.autonomy.decision.v1`, fields
  `{act, candidate_id, params, reason, confidence}`). Returns None on act=false /
  low confidence / unknown candidate_id. Never raises.
- `execute_move(*, service, settings, player_guid, move, governor) -> dict`:
  governor.evaluate → if `allow & not requires_review`: build `ControlProposal`(s)
  (reuse `_run_scene` / `_apply_compiled` / `journey.apply_plan`) and apply; if
  `requires_review`: park in the panel approval inbox (`store.set_pending_intent`
  with a review tag); else log issue.
- **Tests:** chosen low-risk move auto-applies (fake coordinator); medium-at-max →
  queued for review, not applied; unknown candidate rejected; failed apply recorded.
- **Exit:** closed decide→govern→act path, fully fake-tested.

### Task 6.5 — Outcome recording
**Files:** create `src/wm/autonomy/outcome.py`; test `tests/autonomy/test_outcome.py`.
- After execution, write an outcome record (new table `wm_character_autonomy_log`
  via `data/sql/.../wm_autonomy_log.sql`, or reuse `append_journal("autonomy")`):
  `{at, player_guid, move_kind, candidate_id, applied, result, reason}`.
- Mark arc/journey state advanced where relevant (reuse `journey.apply_plan`).
- **Tests:** outcome persisted; arc state updated on `advance_arc`.
- **Exit:** every autonomous act is auditable and feeds future context (6.2 reads it).

### Task 6.6 — Initiative cadence (tick integration)
**Files:** modify `src/wm/autoplay/service.py` (`tick`/`_drive_*`), add
`AutoplayRuntimeConfig.autonomy_*`; test additions in `tests/test_autoplay.py`.
- New `_drive_autonomy(...)` called from `tick()` after chat/ambient: gated by
  `autonomy_enabled` (default **off** — opt-in), runs only when player idle N seconds
  (no recent `wm_chat`) and not on autonomy cooldown. Assembles context (6.2) →
  candidates (6.3) → decide (6.4) → execute (6.4) → record (6.5).
- Config: `autonomy_enabled`, `autonomy_idle_seconds`, `autonomy_cooldown_seconds`,
  `autonomy_max_risk` (default `low`), `autonomy_per_window` — plumbed through
  `_config_to_dict`/`_merged_control_config` (mirror the ambient/memory flags).
- **Tests:** disabled → no-op; idle+enabled → one decision cycle; cooldown respected;
  never runs while a chat event is fresh.
- **Exit:** WM acts on its own cadence, opt-in, low-risk-only by default.

### Task 6.7 — Operator surfaces + kill switch
**Files:** modify `src/wm/panel/server.py`, `static/app.js`; `wm.autoplay configure`
in `src/wm/autoplay/__main__.py`; tests in `tests/panel/`.
- Panel: autonomy on/off, budget sliders, live autonomy log, the review queue
  (medium-risk moves awaiting approval), one-click **kill switch** (sets
  `autonomy_enabled=false`).
- **Exit:** an operator can watch, throttle, approve/reject, and instantly stop WM.

**Phase 6 exit criteria:** with `autonomy_enabled` on and player idle, WM produces a
low-risk move (e.g. an ambient line or a safe scene) end-to-end through the governor,
logs the outcome, and an operator can kill it instantly. Live-proven on BridgeLab.

---

## PHASE 7 — Native verb expansion (the body)

**Goal:** implement the 73 unbuilt verbs in coherent batches so WM has a real body.
Each batch: C++ executor in `native_modules/mod-wm-bridge/src/` (register in
`wm_bridge_environment_actions.cpp`), payload contract in
`control/actions/native/native_bridge_action.json`, `implemented=True` +
`default_risk` in `action_kinds.py`, disabled-by-default policy seed SQL, Python
payload-contract tests, then rebuild + deploy + BridgeLab live-proof.

**Per-verb-batch task template (repeat per batch):**
1. Write payload-contract test in `tests/test_native_bridge_actions.py` (required/
   required_any/optional) — fails first.
2. Add contract entries to `native_bridge_action.json`; flip `implemented=True` +
   risk in `action_kinds.py`. Test passes.
3. Implement C++ executor(s); register in the action registry. Follow existing
   patterns (`creature_spawn`, `creature_say`).
4. Seed disabled policy rows (`wm_bridge_action_policy`) so they stay off until proven.
5. `Build-BridgeLabIncremental.ps1` → `Deploy-BridgeLabWorldServer.ps1` → submit each
   verb via `actions_cli` and confirm `done` + visible effect.
6. Document live status; commit.

### Batch 7.1 — Companion family (12) — *highest player-facing value*
`companion_spawn, companion_follow, companion_say, companion_whisper, companion_emote,
companion_move_to, companion_wait, companion_set_state, companion_set_gossip,
companion_despawn`. A persistent, owner-scoped, named talking follower with state.
Reuse `wm_bridge_world_object` ownership + the Bonebound/Echo runtime patterns in
`mod-wm-spells`. **Exit:** a companion follows the player, speaks/whispers, takes
move/wait/state commands, and despawns cleanly — owner-scoped, audited.

### Batch 7.2 — Creature AI / movement
`creature_follow_player, creature_move_to, creature_set_waypoints, creature_stop_movement,
creature_attack_target, creature_attack_player, creature_flee, creature_evade,
creature_set_react_state, creature_set_faction, creature_set_health_pct`. Lets scenes
*move and behave*, not just spawn/speak. **Exit:** a scene can spawn → approach → act
→ leave with real motion.

### Batch 7.3 — Player-world verbs
`player_teleport, player_summon_to_location, player_send_mail(_with_items),
player_add_title, player_remove_title, player_add_xp, player_play_sound,
player_play_movie, player_set_speed, player_resurrect, player_equip_item,
player_create_bound_item`. **Exit:** WM can move, mail, title, and reward the player
through typed verbs (mail/title/teleport are the autonomy-relevant ones).

### Batch 7.4 — Native quest closure
`quest_complete, quest_complete_objective, quest_reward, quest_fail, quest_set_explored`.
Closes the quest loop natively (off SOAP). **Exit:** a WM quest can be granted,
progressed, completed, and rewarded entirely through the native bus + audit.

### Batch 7.5 — World dressing + counters
`gossip_override_set/clear, gossip_option_add/remove, npc_text_override_set/clear,
zone_set_weather, zone_clear_weather_override, gameobject_spawn/despawn/set_state,
wm_counter_set/increment/clear, area_trigger_marker_set/clear, player_show_menu,
player_close_gossip`. Visible world flavor + WM-owned counters the living systems use.
**Exit:** WM can dress a scene (gossip lines, weather, props) and keep durable counters.

*(Batches 7.1–7.4 unblock Phases 8–9; 7.5 is flavor and can trail.)*

---

## PHASE 8 — Living-world integration

**Goal:** wire the dormant `living/*` modules into the autonomy loop as candidate
sources + persistent world state. They currently run only via CLI/tests.

### Task 8.1 — Relationship / reputation graph
**Files:** `src/wm/world/relationships.py` + `data/sql/.../wm_relationship.sql`;
tests `tests/test_relationships.py`.
- Tables for player↔subject and subject↔subject standing; typed read/write helpers.
- **Exit:** nemesis/patron/mentor can read and write standing through one substrate.

### Task 8.2 — Living systems as candidate sources
**Files:** adapters in `src/wm/autonomy/candidates.py` pulling from each `living/*`
module (`nemesis.propose`, `patron.propose`, `mentor.propose`, `oath`, `ecology`,
`rumor_propagation`, `legend`, `zone_mood`); tests per source.
- Each returns governor-eligible `CandidateMove`s (e.g. nemesis → spawn a hunter
  scene; mentor → offer a task; rumor → ambient line; zone_mood → scene tone).
- **Exit:** the autonomy loop can select living-world moves, fully validated.

### Task 8.3 — World heartbeat scheduler
**Files:** `src/wm/autonomy/heartbeat.py`; cadence hook in `service.py` (or a
CronCreate-driven tick); tests.
- Time/condition-triggered world ticks so `ecology`/`rumor_propagation`/`zone_mood`
  advance even when the player is silent (governor-bounded).
- **Exit:** the world evolves on a clock, not only on player input.

---

## PHASE 9 — Memory that drives decisions

### Task 9.1 — Journal V2 live ingestion
**Files:** wire `journal/projector.py`+`writer.py` into the event pipeline
(`events/` or a watcher step); tests.
- Real events → per-player/per-subject counters → summaries, continuously.
- **Exit:** journal reflects live play without manual runs.

### Task 9.2 — Retrieval-augmented context
**Files:** `src/wm/autonomy/recall.py` (+ optional embedding/index or keyword recall
over journal); feed into 6.2 + chat `world_context`; tests.
- Pull the few most relevant past beats into decision/chat prompts.
- **Exit:** WM references specific, relevant history ("you spared the Defias captain").

### Task 9.3 — Outcome evaluation loop
**Files:** `src/wm/autonomy/evaluate.py`; reads `wm_character_autonomy_log` + journal;
tests.
- Did the move land (reward used, arc beat completed, scene seen)? Bias future
  candidate ranking accordingly.
- **Exit:** WM adapts; repeated ignored offers are de-prioritized.

---

## PHASE 10 — Hardening for autonomy

- **`service.py` split** (the ENABLER, now unlocked): extract chat / ambient / memory
  / scene / autonomy drivers into `src/wm/autoplay/drivers/` behind stable seams;
  keep tests green throughout. Pure refactor, no behavior change.
- **Observability:** structured autonomy metrics + a soak test (N hours, assert no
  budget breach, no unowned spawns, no high-risk auto-apply).
- **Safety suite:** property tests that the governor can never be bypassed; that
  every autonomous mutation is in `wm_bridge_world_object`/audited; kill switch halts
  within one tick.
- **Exit:** autonomy can run unattended for hours within budget, fully auditable,
  instantly stoppable.

---

## Cross-cutting principles & guardrails
- LLM only ever *selects from* or *fills* pre-validated candidates/schemas — never
  emits raw SQL/GM/shell/verbs. (Unchanged from current model.)
- Autonomy defaults **off**; default `max_risk=low`; medium queues for review; high
  is never auto-applied.
- Every autonomous mutation: typed verb → governor → validate → apply → audit →
  rollback path, recorded in the autonomy log.
- Native batches stay policy-disabled until live-proven on BridgeLab.
- Don't touch the watcher marker 946602.

## Suggested execution order (highest leverage first)
1. **Phase 6** (6.1→6.7) — the autonomy keystone (pure Python, offline-testable).
2. **Batch 7.1 companions** + **7.2 creature AI** — the body autonomy acts through.
3. **Phase 8** — living systems become autonomy candidate sources.
4. **Phase 9** — memory drives and adapts decisions.
5. **Batch 7.3/7.4** — player-world + native quest closure (reward surfaces).
6. **Phase 10** — split + hardening + soak.
7. **Batch 7.5** — world dressing (flavor, trailing).

## Definition of done (program)
WM, opt-in and budget-bounded, observes a character, decides and applies safe moves
on its own cadence (advancing arcs, offering rewards, staging companion/creature
scenes, evolving the zone), remembers and adapts to outcomes, and can be watched,
throttled, and stopped by an operator — with every action typed, validated, audited,
and reversible.
