Status: WORKING
Last verified: 2026-05-13
Verified by: Codex
Doc type: reference

# WM Agent Skills Lifecycle

This adapts the public Agent Skills lifecycle pattern to WM without importing generic skills that would weaken WM release safety.

## Source Pattern

The upstream pattern is:

```text
define -> plan -> build -> verify -> review -> ship
```

WM keeps that lifecycle, but routes the work through repo-local skills and WM gates.

## WM Skill Router

Use the narrowest matching repo skill:

| Work type | Skill | Gate |
| --- | --- | --- |
| Repo cleanup, tests, docs, workflow, general code | `$wm-workflow` | Read order, dirty-worktree discipline, focused tests |
| BridgeLab, watcher, native bridge, live proof, player scope | `$wm-live-bridge-lab` | Repo-owned watcher wrappers, scoped live proof |
| Quests, items, spells, shells, arcs, scenes, context packs, LLM proposals | `$wm-content-release` | Strict schemas, fresh IDs, dry-run, packet, rollback |

When more than one applies, load only the skill bodies needed for the current slice.

## Lifecycle

### Define

State the operator goal, the current supported path, and the known forbidden paths.

For content or LLM work, define the target schema and whether the output is draft, packet, dry-run, or live apply.

### Plan

Break work into one testable slice at a time. Prefer:

```text
schema/contract -> backend validation -> CLI/API path -> UI/control surface -> tests -> docs
```

Do not plan direct SQL, GM-command, shell-command, config-edit, or direct LLM mutation lanes.

### Build

Extend existing WM systems first:

- `src/wm/` for Python state, validation, publishing, rollback, audit, and panel code
- `control/` for recipes, policies, and proposal examples
- `native_modules/mod-wm-bridge/` for typed sensing/actions
- `native_modules/mod-wm-spells/` for shell-bound runtime behavior

Keep every increment independently reversible. New mutating surfaces must default to dry-run or disabled.

### Verify

Run focused tests first. Use `python -m pytest -q` for the full suite when the change touches shared behavior and the host test environment is healthy.

For browser UI, verify the local panel visually when the in-app browser permits it; otherwise record API/HTTP smoke proof and keep the status `PARTIAL`.

For live game behavior, repo tests are not enough. Use BridgeLab proof and label unproven gameplay `PARTIAL`.

### Review

Before finishing, check:

- Did this reuse existing WM pipelines instead of creating a parallel one?
- Are client truth and server truth explicit for visible content?
- Are fresh IDs, rollback, audit, and proof gates preserved?
- Are unrelated changes left alone?
- Are docs updated where workflow or behavior changed?

### Ship

End with:

- files changed
- verification commands and results
- `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`
- remaining proof gaps

Do not call a player-facing content lane `WORKING` until both repo proof and required live proof pass.

## Anti-Rationalization Checks

| Temptation | WM answer |
| --- | --- |
| "The LLM can just apply it." | No. LLM output is draft-only. |
| "This one SQL update is faster." | No. Route through owned publishers, action bus, rollback, or audited CLI. |
| "The UI can be loose; backend will catch it." | No. UI schemas, LLM schemas, and server validation must share a contract. |
| "This stock spell ID works." | Not as a permanent WM carrier. Use WM shell IDs. |
| "Tests passed, so gameplay works." | Repo proof is not live proof. Mark gameplay `PARTIAL` until BridgeLab/in-client proof exists. |
