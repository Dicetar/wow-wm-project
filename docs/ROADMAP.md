Status: DESIGN_ONLY
Last verified: 2026-04-14
Verified by: ChatGPT
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
- current fallback/debug path: `combat_log`
- legacy/retired live path: `addon_log`

## Working principles

- C++ senses facts and executes registered typed actions
- WM Python normalizes, plans, validates, dry-runs, audits, and applies
- the LLM does not get freeform mutation powers
- manual control remains the first-class reference lane
- all risky native work is proven in `D:\WOW\WM_BridgeLab` before any promotion
- live perception and action should stay pinned to one explicitly claimed WM player at a time

## Phase 0: Stabilize the native-first baseline

### Goal

Turn the current lab/native path into the boring default substrate for WM.

### Deliverables

- docs updated to reflect `native_bridge` as the target live source
- retire `addon_log` from current-state docs
- keep `combat_log` only as fallback/debug
- verify native event coverage for kill, quest lifecycle, gossip, area enter, spell cast, item use, aura changes, and weather changes
- keep lab runtime config helper and bridge-lab workflow healthy

### Exit criteria

- the repo clearly names `native_bridge` as the live direction
- `addon_log` is no longer presented as the current primary path
- operators can bring up the bridge lab and native watcher from repo docs alone

## Phase 1: Active WM player scope

### Goal

Make one explicitly claimed player the live WM target for perception, journaling, and action.

### Deliverables

- dedicated WM claim spell / aura
- WM-owned active-player scope table
- bridge scope update flow driven by the claim event
- watcher supervisor that retargets/restarts when the claimed GUID changes
- online-state sanity checks using `characters.online`

### Exit criteria

- applying the WM claim effect rewrites the active player GUID
- the watcher follows only that GUID
- switching the claim effect to another character cleanly rewrites scope and restarts perception

## Phase 2: Journal Layer V2 and rollups

### Goal

Move from per-subject counters only to richer per-character memory.

### Deliverables

- daily kill rollups by player and subject
- optional zone/faction/family rollups
- richer pressure-style views such as yesterday/this week hot subjects
- keep append-only raw events plus derived counters and summaries

### Exit criteria

- WM can answer what this player killed a lot yesterday / this week
- subject, family, and zone pressure views are inspectable

## Phase 3: Template convergence

### Goal

Unify the publish side around top-level artifact families while keeping the richer operator-facing workbench split.

### Top-level managed artifact families

1. quests
2. items
3. spells

### Operator-facing content workbench subtypes

The current workbench should continue to expose richer categories where that helps operators:

- managed items
- passive spell-slot drafts
- visible spell-slot drafts
- item-trigger spell-slot drafts
- WM shell-bank drafts

### Deliverables

- top-level docs use the three-family platform model
- content workbench docs keep the richer subtype breakdown
- quest, item, and spell templates converge on shared provenance/lifecycle rules

## Phase 4: Spawn pressure and event-state control

### Goal

Let WM overcharge encounters and local events without treating permanent world DB edits as the first tool.

### Deliverables

- temporary summon-wave events first
- WM-owned spawn pressure overlay second
- pool switching / respawn-multiplier work later where justified
- avoid raw permanent world edits as the default event engine

### Exit criteria

- WM can create a local overcharge event safely and reversibly
- event-state spawns use explicit WM-owned provenance

## Phase 5: Rich world-direction features

### Goal

Use native facts + memory + templates to create more interesting world behavior.

### Deliverables

- mentor / familiar NPC followups
- local legend / local reputation summaries
- zone mood / pressure systems
- richer quest/item/spell reward patterns
- small event-state scenes built from typed native actions

## What is intentionally not first

Not first:

- more addon transport sophistication
- more combat-log work
- Eluna or ALE as the main WM runtime
- freeform LLM-to-game mutation
- broad autonomous story logic before native perception, active-player scope, and memory are stable

Those may still matter later, but they are not the shortest path to a stable World Master platform.
