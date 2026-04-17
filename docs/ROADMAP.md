Status: DESIGN_ONLY
Last verified: 2026-04-16
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

## Priority order

The revised external notes in `D:\WOW\STUFFv2.md` and `D:\WOW\DS_Roadmap_16-04v2.md` are useful as idea input, but they do not replace current-state docs.

Adopted priority order:

1. Native operator lane plus Primitive Pack 1
   - enable the next high-value native verbs through the existing action bus and `control/`
   - prove small playable scenes through audit, not through a second runtime path
   - example: `field_medic_pulse`, `bonebound_battle_cry`, and `summon_marker`
2. Native parity for the existing reactive bounty loop
   - finish the current watcher/spine/bounty path instead of inventing a parallel watcher
   - example: kill burst -> native-preferred quest grant -> reward facts -> cooldown -> regrant
3. Context, journal, and subject integration
   - make context packs and prompt inputs use real player-subject history and native snapshot data
   - example: generated content references the player's actual history with a target instead of generic bounty text
4. Item and spell artifact pipelines
   - extend the existing reserved-slot and rollback model from quests into items and spell grants
   - example: a generated quest rewards a generated WM-owned item from a reserved item slot
5. Visible shell-bank and summon release quality
   - finalize the client-facing spell shell path and keep Bonebound Alpha as the supported summon lane
   - example: a visible WM spell in the spellbook summons or triggers supported WM behavior without stock spell reuse
6. Dynamic scenes, encounters, chat, and narrative arcs
   - add richer world interventions only after primitives, context, and artifact governance are stable
   - example: a WM-owned scene actor spawns, speaks, buffs, and despawns, or a later arc reacts to journal state

Keep from the revised notes:

- journal prompt integration
- subject enrichment and cached subject cards
- item pipeline V1
- visible spell shell bank
- native action vocabulary expansion
- chat, encounter, and arc ideas as later layers

Rework from the revised notes:

- reactive logic must stay on the existing event spine, not a second watcher engine
- native verbs must ship through the current action bus, policy, and audit contracts
- content expansion must use the existing reserved-slot and rollback lifecycle, not ad-hoc publishes

Do not adopt:

- treating quest hardening as the whole project center
- parallel watcher or publisher architecture
- stock spell carriers for visible WM abilities
- any roadmap language that bypasses `control/`, audit, or native policy gates

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
- April 16, 2026 operator-lane cleanup made bundled templates discoverable by key: `wm.reactive.install_bounty --list-templates --summary` lists available bounties and `--template-key <key>` installs one without copying file paths
- April 17, 2026 watcher hardening fixed two live blockers: player-owned non-pet summons now emit native kill facts through a guarded `UnitScript::OnUnitDeath` path, and reactive streak evaluation now reads the newest bounded event-log slice before replaying it chronologically so long lab history cannot hide fresh kills; consecutive streaks fire on threshold multiples to recover cleanly from a missed pre-arm crossing without firing every later kill

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

### Current checkpoint (2026-04-16)

- `WORKING`
- repo implementation now has explicit audit visibility through `python -m wm.control.audit`
- `wm.control.apply --summary` reports idempotency, validation, dry-run/apply status, and native request ids/statuses when present
- `control/policies/direct_apply.json` now defaults `max_source_event_age_seconds` to `600`, so stale non-admin source events are rejected instead of silently replayed
- repo tests cover audit fetch/list, native request extraction for `quest_grant` / `native_bridge_action`, stale-event rejection, wrong-player rejection, and duplicate idempotency rejection
- BridgeLab proof shows control-driven `debug_ping` reaching native request `36` `done` and visible through `wm.control.audit`
- BridgeLab fresh bounty grant proof is now complete: event `1599` -> proposal `43` -> native `quest_add` request `74` `done`, `wm.control.audit` resolves the native request linkage, `wm.executor` recorded `quest_grant_issued` event `1601`, and native bridge event `26505` recorded `quest/granted` for quest `910020`
- the structural fix was to align native `quest_add` with GM `.quest add` sanity checks instead of `player->CanTakeQuest()`, because WM force grants must match the existing SOAP/GM operator lane rather than normal quest-offer eligibility

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
- prompt/package integration for:
  - journal summaries
  - subject cards
  - latest native snapshot rows
- WM perception packs built from:
  - recent canonical events
  - quest runtime state
  - player refs and location
  - nearby entities and objects
  - current area and weather
- subject definition and enrichment persistence so target context is cached after first proof
- snapshot requests start as operator/manual tools first

### Exit criteria

- WM can request a scoped nearby snapshot for one player and consume it deterministically
- control inspect can show recent events plus nearby context together
- journal-backed prompt inputs can reference a player's real history with the resolved subject
- no continuous nearby-entity spam lane is introduced

## Phase 4: Broaden native action primitives

### Goal

Front-load reusable typed verbs and operator scenes so later WM features do not require constant full rebuild churn or a second execution path.

### Current checkpoint (2026-04-17)

- `PARTIAL`
- Primitive Pack 1 is `WORKING` in BridgeLab for player `5406` behind policy-disabled defaults
- Primitive Pack 2 is repo/build `WORKING` and live `PARTIAL`: `player_cast_spell`, `player_set_display_id`, `creature_cast_spell`, `creature_set_display_id`, and `creature_set_scale` now have typed native bodies, payload contracts, disabled policy seed SQL, repo tests, and a successful BridgeLab native build; live `arcane_marker_demo` apply stopped at request `83` with `player_not_online`
- The next proof step is to log player `5406` into BridgeLab, enable the Pack 2 policies for the scoped player, run `python -m wm.control.scene_play --scene arcane_marker_demo --player-guid 5406 --mode apply --confirm-live-apply --summary`, and audit the resulting native requests

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
   - `player_cast_spell`
   - `player_set_display_id`
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
   - `creature_cast_spell`
   - `creature_set_display_id`
   - `creature_set_scale`
   - `creature_follow_player`
7. environment verbs:
   - `zone_set_weather`
   - `zone_clear_weather_override`

### Deliverables

- Primitive Pack 1 implemented through `native_bridge_action`
- `python -m wm.control.scene_play` as an operator wrapper over existing control proposals
- first playable scenes:
  - `field_medic_pulse`
  - `bonebound_battle_cry`
  - `summon_marker`
  - `arcane_marker_demo`
- audit output that links proposal -> native request -> result for scene steps and direct primitive use

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

Treat WM-created artifacts and WM-owned spawned objects as first-class lifecycle-managed objects, then use them for items, spell grants, and controlled world scenes.

### Current checkpoint (2026-04-17)

- `PARTIAL`
- item pipeline V1 is repo-tested and live-proven for one managed bounty reward at DB/runtime-reload level
- `control/examples/items/night_watchers_lens.json` publishes item `910006` (`Night Watcher's Lens`) from a managed item slot with Intellect, Stamina, spell power, visible wearer aura spell `132`, and a native 10% direct-hit target-mark proc gated by equipped item plus visible aura
- the target mark uses a visible debuff (`770`) with a tracked 10-second duration that refreshes on reapply; melee/ranged attacks against marked targets bypass the avoidance/defense outcomes covered by the current hook, and WM-owned proc hooks such as Bonebound Alpha Echo can opt into doubled proc chance
- generic stock/core proc chance doubling remains `PARTIAL` until a real proc-event hook exists; do not document the lens as globally doubling every stock effect yet
- quest `910024` (`Bounty: Nightbane Dark Runner - Lens`) now rewards item `910006` x1 through the shared quest edit path, so WM can replace coin-only bounty rewards with managed artifacts without bypassing slot governance
- visible reward iteration must allocate a fresh quest slot after an older test ID has been accepted or rewarded; `910021` was retired for this proof because the live client kept showing stale money-only reward data after mutation
- client-visible reward pickup, equip behavior, and passive behavior remain `PARTIAL` until confirmed in-game after quest turn-in
- hidden server mechanics must have visible effect indication; stock auras are acceptable as visible markers only when they fit the mechanic, not as unrelated tooltip hacks

### Deliverables

- staged -> active -> retired -> archived lifecycle model
- item pipeline V1 on top of reserved slots, validation, publish, and rollback
- spell grant and revoke paths that stay inside WM shell ownership and action contracts
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
- later content layers once the artifact base is proven:
  - encounter compiler
  - chat-command entrypoints
  - multi-step story arcs

### Exit criteria

- WM can compose small multi-part scenes without losing provenance or rollback clarity
- slot ownership and WM-owned object ownership are explicit
- a WM quest can reward a WM item or shell-backed spell grant without bypassing lifecycle tracking

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
- broad autonomous story logic before native perception, action, and context are stable
- a parallel watcher or template publisher architecture
- ad-hoc item or spell publishing outside reserved-slot governance
- stock spell carrier reuse for visible WM spells

Those may still matter later, but they are not the shortest path to a stable World Master platform.
