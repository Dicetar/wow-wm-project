Status: WORKING
Last verified: 2026-04-13
Verified by: Codex
Doc type: adr

# ADR 0001: Do Not Reuse Stock Live Spell IDs as WM Carriers

## Context

Several WM summon experiments reused stock spell IDs such as `697`, `8853`, `57913`, `49126`, and `7302`.

That created stock behavior collisions, unstable summon behavior, and at least one hostile incorrect summon.

## Decision

Production WM abilities do not use stock live spell IDs as their permanent execution carriers.

Rules:

- player-facing WM abilities use WM-owned shell IDs
- WM shell rows are dummy or script-style shells
- actual behavior is executed by WM-owned runtime code such as `mod-wm-spells`
- stock IDs may be used only for tightly scoped, temporary lab experiments and must be labeled as testing-only

## Consequences

- visible new WM spells require the shell-bank/client patch path
- debug and native invocation lanes remain valid for behavior tuning before the client shell exists
- stock-carrier summon work is treated as retired, not as an acceptable fallback
