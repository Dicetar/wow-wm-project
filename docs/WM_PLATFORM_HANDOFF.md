Status: PARTIAL
Last verified: 2026-04-14
Verified by: Codex
Doc type: handoff

# WM Platform Handoff

This is the current entrypoint for a new engineer or LLM.

Use this with:

- [Documentation Index](README_OPERATIONS_INDEX.md)
- [Codex Working Rules](CODEX_WORKING_RULES.md)
- [Work Summary](WORK_SUMMARY.md)

## What WM is

WM is an external-first World Master platform for AzerothCore 3.3.5a.

Current architecture:

- Python WM is the reasoning and orchestration layer
- native AzerothCore modules are the sensing and atomic execution layer
- contracts, policies, and manual control live in repo-owned schemas and CLIs

## What is working now

### Platform foundations

- canonical WM event spine
- manual control contract system
- initial subject resolver slice maps target profiles into WM subject cards and exposes `python -m wm.subjects.inspect`
- DB-backed journal reader loads WM subject definitions, enrichments, player-subject counters, and raw journal events when those tables exist; prompt demos and inspect paths now fall back to resolver-built subject cards when journal rows or live DB access are missing
- operator journal inspection exists through `python -m wm.journal.inspect`
- deterministic context-pack builder composes source events, character state, target profiles, subject cards, journal summaries, recent events, reactive quest runtime, control recipe/policy metadata, and latest native context snapshots into `wm.context_pack.v1`; unresolved target/event CLI requests return `UNKNOWN`
- deterministic lab seed `sql/dev/seed_journal_context_5406_world.sql` exists for player `5406`, creature entry `46`, and one seeded `wm_event_log` smoke event
- content workbench for WM-owned items, spells, and shell metadata
- repo-owned bootstrap and bridge-lab workflows

### Live sensing and execution

- `addon_log` is the currently proven live perception path
- `native_bridge` exists and can emit canonical WM events
- `wm.events.watch` now survives per-iteration spine failures and flushes summary/error lines for automation logs instead of exiting silently on the first exception
- reactive bounty installs now have a repo-owned fast path through `control/examples/reactive_bounties/` and `scripts/bridge_lab/Install-BridgeLabReactiveBounty.ps1`
- reactive bounty templates now default to fresh `wm_reserved_slot` quest allocation instead of reusing one mutable live quest ID across iterations
- reactive bounty dry-runs can preview the next free reserved quest slot without staging it or producing a false preflight failure
- shared reactive bounty publishing supports richer quest reward fields when the live `quest_template` schema exposes them:
  - money
  - reward item
  - `RewardXPDifficulty`
  - `RewardSpell` / `RewardDisplaySpell`
  - `RewardFactionID*` plus value/override slots
- native action queue exists with DB-backed policy and player scoping
- native spell learn and unlearn actions exist
- `quest_grant` prefers native `quest_add` when bridge config, player scope, and policy are ready, with SOAP fallback otherwise
- the Phase 1 reactive bounty loop has repo-level automated parity coverage and historical native bridge proof for quest `910000`

### Native spell platform

- shell-bank contract exists
- client patch workspace exists
- `mod-wm-spells` exists as the stable native spell-behavior runtime
- lab debug invoke exists for shell-bound behavior testing without a visible client shell

## What is partial

- `native_bridge` is not yet the fully proven primary live path for all current WM gameplay loops
- the April 13, 2026 bridge-lab rerun only reached smoke level:
  - `debug_ping` reached `done`
  - `wm.events.watch --adapter native_bridge --arm-from-end` advanced the live high-water mark
  - the full in-game `Kobold Vermin -> quest 910000 -> reward -> cooldown -> regrant` loop was not rerun because validation player `5406` was offline
- broad native action vocabulary exists, but many verbs are still disabled or `not_implemented`
- `context_snapshot_request` is `PARTIAL`: tracked native code now writes one `wm_bridge_context_snapshot` from the action queue when the scoped player is online, and the bridge-lab `worldserver` target compiles; live proof still needs player `5406` online
- subject recognition is only a first slice:
  - static lookup and live-target resolver wrapping exist
  - DB-backed journal read helpers and resolver-card fallback exist
  - context-pack assembly exists and includes recipe/policy metadata plus latest native snapshot rows when present
  - repo tests are `WORKING` for the resolver, journal reader/inspect, and context-pack assembly
  - bridge-lab DB proof on `127.0.0.1:33307` is `WORKING` for the seeded player `5406` / creature `46` journal and event-backed context pack
  - automatic subject materialization, online-player native snapshot proof, zone mood, and full proposal-gate previews are still `PARTIAL`
- visible shell-bank spells are not yet proven end-to-end in the client because the local patch artifact is not finalized and installed from repo instructions
- summon/twin behavior work exists in pieces, but only the debug/native lane is currently supported for iteration
- experimental `template_watch` / `template_publish` comparison work remains isolated in `.worktrees/template-watch-compare`; its dynamic binding idea is useful, but its standalone watcher path is not the production architecture

## What is broken or retired

- stock spell carrier reuse for WM abilities is retired
- `mod-wm-prototypes` is not the main summon or ability lane
- visible stock-carrier summon testing is retired
- freeform LLM mutation of configs, SQL, shell commands, or arbitrary game state is not allowed

For the summon failure history, read:

- [Summon Failure Postmortem](SUMMON_FAILURE_POSTMORTEM.md)
- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)

## System map

### Key repo areas

- `src/wm/` - Python orchestration, control, content, prompt, and runtime tooling
- `control/` - event/action/recipe/policy contracts
- `native_modules/mod-wm-bridge/` - native sensing and action queue
- `native_modules/mod-wm-spells/` - native shell-bound spell behavior runtime
- `scripts/bridge_lab/` - isolated native build and runtime helpers
- `client_patches/wm_spell_shell_bank/` - shell-bank patch workspace

### Key runtime/data pieces

- `wm_event_log`
- `wm_bridge_event`
- `wm_bridge_action_request`
- `wm_control_proposal`
- `wm_spell_shell`
- `wm_spell_behavior`
- `wm_spell_grant`
- `wm_spell_debug_request`

## Architecture boundary for ambitious features

Use this model when proposing or implementing "wild" abilities:

1. trigger or event
2. Python-side decision and state
3. atomic action sequence or shell-bound native behavior
4. client requirement level

Feature feasibility filter:

- `T1` server only
- `T2` server plus existing client assets
- `T3` client patch required
- `T4` client asset or UI work
- `NOT FEASIBLE` on stock 3.3.5a

If a feature needs a visible spellbook entry, hotbar button, or owned tooltip, treat it as `T3` immediately.

## Read order by task

### If you are working on summon or spell behavior

1. [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)
2. [Summon Failure Postmortem](SUMMON_FAILURE_POSTMORTEM.md)
3. [mod-wm-spells README](../native_modules/mod-wm-spells/README.md)
4. [Spell Shell Bank V1](SPELL_SHELL_BANK_V1.md)

### If you are working on native bridge actions

1. [Native Bridge Action Bus](native-bridge-action-bus.md)
2. [ADR 0002](adr/0002-extend-existing-action-bus.md)
3. [Roadmap](ROADMAP.md)

### If you are working on repo process or agent behavior

1. [../AGENTS.md](../AGENTS.md)
2. [Codex Working Rules](CODEX_WORKING_RULES.md)
3. [Documentation Index](README_OPERATIONS_INDEX.md)

## Known footguns

- Client-visible spell work requires client truth, not just server truth.
- Dirty lab state can poison summon and pet retests.
- Design docs can be useful and still be stale.
- Current-state docs and postmortems outrank aspirational design notes.
- The repo may contain dirty local experiments; only supported paths in status docs should be treated as trusted.
