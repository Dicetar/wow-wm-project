Status: WORKING
Last verified: 2026-04-13
Verified by: Codex
Doc type: adr

# ADR 0003: Player-Facing WM Spells Require a Client Shell Bank

## Context

WM needs true custom abilities that can appear in the spellbook, on the action bar, and with owned icons and tooltips.

The stock 3.3.5a client does not safely support arbitrary unknown spell IDs as real visible abilities.

## Decision

Player-facing WM spells use a pre-seeded shell bank plus client patch.

Rules:

- shell IDs are reserved in `control/runtime/spell_shell_bank.json`
- the repo stores the shell-bank workspace and instructions
- built patch artifacts are generated locally and are not committed
- until the patch is installed, behavior iteration stays on the debug/native lane

## Consequences

- server-only spell hacks are testing-only, not production-safe player-facing solutions
- the shell bank should be sized broadly enough to avoid per-spell repatching for normal iteration
- visible custom WM abilities become a stable contract instead of an ad hoc carrier experiment
