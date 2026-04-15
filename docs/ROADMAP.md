Status: DESIGN_ONLY
Last verified: 2026-04-15
Verified by: Codex
Doc type: design

# WM Roadmap

This file is the intended direction, not the current truth source.

Read these first if you need current state:

- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)
- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)

WM is now a platform project, not a bootstrap experiment.

The direction is native-first:

- WM stays the external brain
- AzerothCore stays the runtime body
- `native_bridge + control` becomes the main substrate
- workaround perception paths stay available only as fallback until native parity is proven

Current fallback policy:

- primary target architecture: `native_bridge`
- current proven live fallback: `addon_log`
- debug-only fallback: `combat_log`

## Working principles

- C++ senses facts and executes registered typed actions
- WM Python normalizes, plans, validates, dry-runs, audits, and applies
- the LLM does not get freeform mutation powers
- manual control remains the first-class reference lane
- all risky native work is proven in `D:\WOW\WM_BridgeLab` before any promotion

## Phase 0: Stabilize the current bridge-lab delta

### Goal

Turn the current lab spike into a clean checkpoint we can safely build on.

### Deliverables

- lab launcher plus auth realmlist sync helper
- graceful-first lab worldserver restart path
- native `quest_add` implementation
- native `quest/granted` emission after successful `quest_add`
- Questie compat addon for WM custom quest ids
- docs updated to reflect the actual lab workflow
- lab runtime config helper keeps `WeatherVibe.Debug = 0`

### Exit criteria

- the lab boots from repo helpers
- `quest_add` places the quest directly into Jecia's journal and the quest is turn-in capable
- successful `quest_add` also yields a native quest event visible to WM
- WeatherVibe debug spam is off in the lab
- Questie no longer spams tracker errors for WM custom quest ids
- the repo is push-ready again

## Phase 1: Native parity for the current bounty loop

### Goal

Make the existing reactive bounty loop work fully through native perception and native-preferred action execution.

### Current checkpoint (2026-04-13)

- `PARTIAL`
- repo automated coverage now proves:
  - burst threshold crossing
  - native-preferred `quest_grant`
  - SOAP fallback when native is unavailable
  - post-reward cooldown reopening
  - one spine-level native bridge flow with runtime reconciliation
- historical bridge-lab evidence from April 11, 2026 shows `Bounty: Kobold Vermin` emitting native `quest_granted`, native `quest_completed`, native `quest_rewarded`, and a WM cooldown row for player `5406`
- the April 13, 2026 bridge-lab rerun did not complete the live kill/turn-in cycle because validation player `5406` was offline, so the Phase 1 exit criteria remain open
- April 14, 2026 comparison work kept richer reward support as a product capability and moved it into the shared bounty draft / publish path instead of a parallel template publisher; dry-run slot preview now stays non-mutating without false preflight failure; dynamic per-trigger watcher binding remains a `REWORK` item
- April 15, 2026 cleanup separated operator templates from implicit auto-bounties: bundled examples now use `reactive_bounty:template:*`, `WM_REACTIVE_AUTO_BOUNTY_ENABLED` defaults off, and live validation should install one explicit template before arming the watcher

### Deliverables

- native `kill`
- native `quest_granted`
- native `quest_completed`
- native `quest_rewarded`
- cooldown and suppression remain in WM
- `quest_grant` prefers native `quest_add` and falls back to SOAP only when native is unavailable
- runtime quest-state polling remains as reconciliation, not primary truth

### Exit criteria

- 4 `Kobold Vermin` kills in 120 seconds grant quest `910000` through native action
- turning in to `Marshal McBride` emits usable native reward-state facts
- immediate retrigger is suppressed while the quest is active or complete-but-not-rewarded
- post-reward cooldown works
- after cooldown, the same burst grants again
- `addon_log` still works if native is disabled

## Phase 2: Control-native convergence

### Goal

Make manual control the normal operator lane for native actions and keep it identical to future LLM contracts.

### Deliverables

- event inspect
- proposal build
- validate
- dry-run
- apply
- audit
- capability-aware action selection:
  - native when implemented and policy-allowed
  - fallback only where native is not yet proven
- `control/` remains the single place for:
  - event contracts
  - action contracts
  - recipe registry
  - runtime safety checks
  - policy defaults
  - manual examples

### Exit criteria

- a human can reproduce the bounty grant and small native tests entirely through the control workbench
- proposal audit links source event -> proposal -> native request -> result
- policy, idempotency, stale-event, and wrong-player rejections are visible and explainable

## Phase 3: Context and perception packs

### Goal

Expose nearby context as snapshots and package deterministic world state for operators and later LLM use.

### Current checkpoint (2026-04-15)

- `PARTIAL`
- initial subject resolver and DB-backed journal reader slices exist
- journal reads now merge WM subject definitions, enrichments, player-subject counters, raw journal events, and optional resolver-built subject cards
- DB-unavailable journal probes degrade to resolver-backed `PARTIAL` output instead of crashing
- deterministic lab seed `sql/dev/seed_journal_context_5406_world.sql` exists for player `5406`, creature entry `46`, and one event-backed context smoke row
- bridge-lab DB proof on 2026-04-14 against `127.0.0.1:33307` is `WORKING` for `wm.journal.inspect` and `wm.context.builder --event-id` with native snapshot disabled
- `wm.context_pack.v1` assembly exists for source event, character state, target profile, subject card, journal summary, recent events, related subject events, reactive quest runtime, eligible recipes, policy metadata, and latest native context snapshot rows when present
- `python -m wm.context.snapshot` and the bridge-lab wrapper can request one bounded native snapshot proof
- fresh live context snapshot consumption is `WORKING` for one-shot operator proof: on 2026-04-15, action request `31` reached `done`, `wm_bridge_context_snapshot` row `1` was written, and the event-backed context pack consumed it with `native_snapshot: true`
- zone mood, non-reactive quest runtime, and full proposal-gate preview sections are still open

### Deliverables

- `context_snapshot_request`
- `wm_bridge_context_snapshot`
- WM perception packs built from:
  - recent canonical events
  - quest runtime state
  - player refs and location
  - nearby entities and objects
  - current area and weather
- snapshot requests start as operator/manual tools first

### Exit criteria

- WM can request a scoped nearby snapshot for one player and consume it deterministically
- control inspect can show recent events plus nearby context together
- no continuous nearby-entity spam lane is introduced

## Phase 4: Broaden native action primitives

### Goal

Front-load reusable typed verbs so later WM features do not require constant full rebuild churn.

### Native action order

1. `world_announce_to_player`
2. quest verbs:
   - `quest_add`
   - `quest_complete`
   - objective and counter helpers
3. low-risk player verbs:
   - `player_apply_aura`
   - `player_remove_aura`
   - `player_restore_health_power`
4. reward verbs:
   - `player_add_item`
   - `player_add_money`
   - `player_add_reputation`
5. interaction verbs:
   - `gossip_override_set`
   - `gossip_override_clear`
   - `player_show_menu`
6. WM-owned scene verbs:
   - `creature_spawn`
   - `creature_despawn`
   - `creature_say`
   - `creature_emote`
   - `creature_follow_player`
7. environment verbs:
   - `zone_set_weather`
   - `zone_clear_weather_override`

### Rules

- no generic GM-command action
- no arbitrary SQL action
- no mutation of non-WM-owned creatures or gameobjects except explicit admin-only lab tools
- every verb needs:
  - policy default
  - payload schema
  - manual proposal example
  - lab proof
  - clear result and error JSON

## Phase 5: Artifact governance and scene composition

### Goal

Treat WM-created artifacts and WM-owned spawned objects as first-class lifecycle-managed objects.

### Deliverables

- staged -> active -> retired -> archived lifecycle model
- provenance links from:
  - source event
  - control proposal
  - native action request
  - publish log / rollback state
- WM-owned scene composition:
  - temporary NPCs
  - temporary gameobjects
  - companion flows
  - injected gossip and menu interactions

### Exit criteria

- WM can compose small multi-part scenes without losing provenance or rollback clarity
- slot ownership and WM-owned object ownership are explicit

## Phase 6: LLM layer on top of locked contracts

### Goal

Let the LLM choose and fill registered controls only after the native/manual foundation is boringly reliable.

### Deliverables

- LLM input includes:
  - perception pack
  - eligible recipes
  - allowed action contracts
  - current policy gates
- manual stays the reference lane
- direct live apply stays off by default

### Exit criteria

- LLM proposals use the same schema as manual proposals
- no freeform config edits, shell commands, SQL, or file mutations are exposed
- direct apply remains gated and explainable

## What is intentionally not first

Not first:

- more addon transport sophistication
- more combat-log work
- Eluna or ALE as the main WM runtime
- freeform LLM-to-game mutation
- broad autonomous story logic before native perception and action are stable

Those may still matter later, but they are not the shortest path to a stable World Master platform.
