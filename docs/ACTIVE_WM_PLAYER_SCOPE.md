Status: DESIGN_TARGET
Last verified: 2026-04-14
Verified by: ChatGPT
Doc type: reference

# Active WM Player Scope

This file describes the intended active-player control contract for live WM operation.

## Purpose

WM live perception and action should be bound to one explicitly claimed player character at a time.

The active player should not be selected only by asking who is online.

`characters.online` is useful as a sanity check, but the authoritative selector should be explicit WM control state.

## Claim model

The intended flow is:

1. apply a dedicated WM claim spell / aura to the intended player
2. native bridge emits the spell cast / aura applied fact
3. WM extracts `PlayerGUID` from that event
4. WM persists that GUID in a WM-owned active scope table
5. WM updates bridge/player scope to the same GUID
6. watcher supervisor restarts or retargets to that GUID

## Why this is better than online-only selection

It is:

- explicit
- deterministic
- per-character
- compatible with separate journaling/logging per character
- easy to expose in-world through a visible aura or marker

## Intended table shape

A minimal direction:

- `ScopeKey`
- `PlayerGUID`
- `ClaimSpellID`
- `ClaimSource`
- `ClaimedAt`
- `ReleasedAt`
- `IsActive`

One row such as `wm_primary` is enough for the current single-player live model.

## Scope rules

- only one active WM scope row should be active for the main live watcher
- applying the claim effect to another player rewrites the active GUID
- the watcher follows the persisted GUID, not transient client heuristics
- online state should be checked before/while running, but should not replace explicit scope state

## Aura semantics

The claim aura is the trigger for setting scope.

The aura itself should not be the only enduring source of truth, because a visible/control aura may fall off due to reloads, death, dispels, or testing mistakes.

Recommended rule:

- aura application claims scope
- explicit replacement or explicit release changes scope
- aura removal can mark scope stale if needed, but should not silently select a different player

## Relationship to bridge player scope

`wm_bridge_player_scope` or equivalent bridge-side allowlist state should be kept aligned with the active WM player GUID.

That keeps:

- native perception
- native action queue scope
- Python watcher scope

all pinned to the same character.

## Relationship to journals

All WM journals, counters, cooldowns, and event history should remain keyed by character GUID.

The active-player scope controls who is watched live.

It does not replace the per-character storage model.

## Relationship to managed content

Managed content may still target the active player by default, but the artifact families remain separate:

- quests
- items
- spells

The scope model only answers who the current live WM subject is.

## Operational sanity checks

A watcher supervisor should validate:

- active scope row exists
- claimed GUID is online if live watching is expected
- bridge/player scope matches persisted WM scope
- watcher process target GUID matches persisted WM scope

If any of these drift, the supervisor should either:

- restart/retarget cleanly, or
- idle with a clear diagnostic state
