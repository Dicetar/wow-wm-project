Status: WORKING
Last verified: 2026-04-13
Verified by: Codex
Doc type: adr

# ADR 0002: Extend the Existing WM Action Bus

## Context

The WM repo already has:

- Python control/orchestration
- `wm_bridge_action_request`
- native bridge dispatch and policy

There is repeated pressure to add parallel executors, runners, or native sidecar systems when building ambitious features.

## Decision

New native gameplay capability extends the existing action bus instead of introducing a parallel execution system.

Rules:

- new native behavior exposed to WM becomes a new `action_kind` or shell-bound runtime behavior
- Python remains the reasoning and sequencing layer
- C++ remains the sensing, execution, and safety layer

## Consequences

- "wild feature" implementation should be expressed as Python decisions plus atomic action sequences
- future work should not create a second C++ action runner for companion, spell, or scene logic
- design proposals that duplicate the action bus are considered architecture drift
