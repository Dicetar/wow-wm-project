Status: PARTIAL
Last verified: 2026-04-13
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
- content workbench for WM-owned items, spells, and shell metadata
- repo-owned bootstrap and bridge-lab workflows

### Live sensing and execution

- `addon_log` is the currently proven live perception path
- `native_bridge` exists and can emit canonical WM events
- native action queue exists with DB-backed policy and player scoping
- native spell learn and unlearn actions exist

### Native spell platform

- shell-bank contract exists
- client patch workspace exists
- `mod-wm-spells` exists as the stable native spell-behavior runtime
- lab debug invoke exists for shell-bound behavior testing without a visible client shell

## What is partial

- `native_bridge` is not yet the fully proven primary live path for all current WM gameplay loops
- broad native action vocabulary exists, but many verbs are still disabled or `not_implemented`
- visible shell-bank spells are not yet proven end-to-end in the client because the local patch artifact is not finalized and installed from repo instructions
- summon/twin behavior work exists in pieces, but only the debug/native lane is currently supported for iteration

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
