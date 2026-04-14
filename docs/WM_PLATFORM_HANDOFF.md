Status: PARTIAL
Last verified: 2026-04-14
Verified by: ChatGPT
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
- the target live perception substrate is `native_bridge`
- the intended live player model is one explicitly claimed active WM player at a time

## What is working now

### Platform foundations

- canonical WM event spine
- manual control contract system
- content workbench for WM-owned items, spells, and shell metadata
- repo-owned bootstrap and bridge-lab workflows

### Live sensing and execution

- `native_bridge` exists and can emit canonical WM events for kills, quest lifecycle, gossip, area enter, spell cast, item use, aura changes, and weather changes
- native action queue exists with DB-backed policy and player scoping
- native spell learn and unlearn actions exist
- `combat_log` remains available as fallback/debug only

### Native spell platform

- shell-bank contract exists
- client patch workspace exists
- `mod-wm-spells` exists as the stable native spell-behavior runtime
- lab debug invoke exists for shell-bound behavior testing without a visible client shell

## What is partial

- `native_bridge` is the target primary live path, but not every intended gameplay loop has been proven end-to-end yet
- broad native action vocabulary exists, but many verbs are still disabled or `not_implemented`
- active WM player selection through a dedicated claim aura / persisted scope is the intended control model, but should still be treated as an architecture target until fully wired end-to-end
- visible shell-bank spells are not yet proven end-to-end in the client because the local patch artifact is not finalized and installed from repo instructions
- summon/twin behavior work exists in pieces, but only the debug/native lane is currently supported for iteration
- richer journal rollups and world-pressure logic are still ahead of the current subject-journal baseline

## What is broken or retired

- `addon_log` is no longer the canonical or preferred live source; it should be treated as a legacy path only
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
- future-facing active-player scope metadata belongs in WM-owned scope tables, not in watcher-local state only

## Event and content model

### Top-level managed artifact families

WM should think in three top-level managed artifact families:

1. quests
2. items
3. spells

This is the platform-level model.

### Operator-facing content subtypes

The existing content workbench is intentionally richer than the top-level model. In practice the current spell/content side already splits into:

- managed items
- managed passive spell-slot drafts
- managed visible spell-slot drafts
- managed item-trigger spell-slot drafts
- WM shell-bank drafts for summon/behavior work

So the repo now uses:

- a simple three-family platform model
- a richer operator-facing subtype model where the workbench needs it

### Event watcher direction

The intended watcher model is:

1. native bridge senses canonical facts
2. WM normalizes them into canonical WM events
3. WM binds live perception to one explicitly claimed active player GUID
4. WM journals raw and derived memory per character
5. WM evaluates rules/templates and emits typed publish or action plans

## Architecture boundary for ambitious features

Use this model when proposing or implementing wild abilities:

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

### If you are working on event watching, player scope, or journaling

1. [Event Watcher Architecture](EVENT_WATCHER_ARCHITECTURE.md)
2. [Active WM Player Scope](ACTIVE_WM_PLAYER_SCOPE.md)
3. [Native Bridge Action Bus](native-bridge-action-bus.md)
4. [Roadmap](ROADMAP.md)

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
- A player being online is not enough to make them the WM player; live scope should come from explicit WM claim/control state.
