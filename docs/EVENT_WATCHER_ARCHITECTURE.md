Status: DESIGN_TARGET
Last verified: 2026-04-14
Verified by: ChatGPT
Doc type: design

# Event Watcher Architecture

This file describes the intended watcher architecture after the native-first doc actualization pass.

## Design summary

WM should not treat log scraping as the durable substrate.

The durable watcher model is:

1. native AzerothCore code senses canonical gameplay facts
2. `mod-wm-bridge` writes append-only rows into `wm_bridge_event`
3. WM Python normalizes those rows into canonical WM events
4. WM binds live perception to one explicitly claimed active player GUID
5. WM journals, evaluates, and reacts per character
6. WM publishes or executes typed artifacts/actions through deterministic pipelines

## Source policy

Primary live source:
- `native_bridge`

Fallback/debug source:
- `combat_log`

Legacy path:
- `addon_log`

`addon_log` can remain in-tree as historical code, but it should not be described as the primary live path in current-state docs.

## Event families

The intended high-value watcher families are:

- combat
  - kill
- quest lifecycle
  - accepted
  - granted
  - completed
  - rewarded
- interaction
  - gossip opened
  - gossip selected
- exploration
  - area entered
- inventory / spell
  - loot item
  - item used
  - spell cast
  - aura applied
  - aura removed
- environment
  - weather changed

These are enough to support the current bounty/control/content lane and future richer world-state logic.

## Why native first

Native bridge is the right long-term substrate because it gives:

- authoritative server facts
- cleaner player scoping
- less ambiguity than client/log-derived paths
- better alignment between mutation and perception
- a stable typed contract between AzerothCore and Python WM

## Watcher stages

### 1. Raw sensing

AzerothCore native code should emit append-only bridge rows with at least:

- bridge event id
- occurred at
- player guid
- event family
- event type
- subject/object refs
- map / zone / area
- payload JSON

### 2. Canonical normalization

WM Python should convert bridge rows into canonical WM events with one stable schema.

The canonical event layer is the only layer that the journal, rules, planner, and control workbench should consume.

### 3. Active-player filter

Live watching should bind to one explicitly claimed active WM player.

The watcher should not infer ownership purely from who is online.

### 4. Journal and rollups

WM should keep:

- append-only raw events
- per-character subject counters
- richer daily/zone/faction/family rollups over time

### 5. Deterministic rule evaluation

Rules should match on canonical events and on journal state, not on raw bridge rows.

Example rule shape:

- trigger event type
- subject matcher
- optional area/zone scope
- time window
- threshold
- cooldown
- template or recipe key

### 6. Typed reaction paths

When a rule matches, WM should emit a typed publish/action plan rather than inventing raw SQL or freeform mutation.

## Live player control model

The intended ownership path is:

- dedicated WM claim spell / aura
- native bridge observes claim event
- WM persists active player scope
- bridge/player scope updates to that GUID
- watcher follows only that GUID

See [Active WM Player Scope](ACTIVE_WM_PLAYER_SCOPE.md).

## Artifact families

WM should reason in three top-level managed artifact families:

1. quests
2. items
3. spells

The operator-facing workbench can still expose richer subtypes under the spell/content lane.

## Spawn pressure and overcharge direction

The intended order is:

1. temporary summon-wave events first
2. WM-owned spawn-pressure overlays second
3. respawn multiplier or pool-switching work later where justified

Permanent raw world edits should not be the default event engine.

## Non-goals for the watcher

The watcher should not:

- become a second brain inside C++
- plan story logic in native code
- depend on Lua as the primary runtime
- depend on addon log as the long-term source of truth
- apply freeform world mutations directly
