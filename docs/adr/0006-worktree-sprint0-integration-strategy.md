# ADR-0006: Sprint 0 Worktree Integration Strategy

**Status:** Accepted  
**Date:** 2026-05-18  
**Deciders:** WM maintainers

## Context

A parallel development branch (`claude/lucid-curran-3c5f91` in `D:\Projects\wow-wm-project`)
produced 15 commits advancing Living World scaffolds, status-as-data, Journal V2,
native payload contracts, and the Wild Feature Catalog. The canonical repo
(`D:\WOW\wm-project`) had diverged — notably with a `panel/` package replacing the
worktree's flat `panel.py` module — making a simple merge risky.

## Decision

Cherry-pick 12 of 15 commits into a dedicated integration branch
(`integrate/worktree-sprint0`) using `git cherry-pick` with explicit collision
handling. Skip 3 commits whose changes conflict irreconcilably with the canonical
package layout.

### Commit disposition

| Commit | Action | Reason |
|--------|--------|--------|
| `e4ba999`–`aa08c48` (4 commits) | Cherry-pick clean | No conflicts |
| `2e74c90`–`f97e6ce` (6 commits) | Cherry-pick + resolve | `cli.py` diagnostics entries, `panel.py` and `webpanel.py` modify/delete |
| `ab9b450`–`94ff125` (2 commits) | Cherry-pick + resolve | `webpanel.py` modify/delete |
| `f06f41d` | **Skip** | `llm/__init__.py` collision — canonical version preserved |
| `2d4ac0b` | **Skip** | `panel.py` flat module — canonical has `panel/` package |
| `2d81022` | **Skip** | `webpanel.py` — depended on the skipped `panel.py` |

### Collision resolutions

**Collision 1 — `panel.py` vs `panel/` package:**  
The worktree introduced a flat `panel.py` with `PanelReport`/`build_panel()`. Canonical
already has a `panel/` package (server, catalog, jobs, schemas, state). Resolution:
keep the `panel/` package; implement the summary surface as `panel/summary.py` exposing
`HealthCheck`, `PanelReport`, and `build_panel()`. Add `wm panel summary` subcommand
to `panel/__main__.py` and `/api/living` endpoint to `panel/server.py`.

**Collision 2 — `llm/__init__.py`:**  
The worktree's `f06f41d` rewrote the LLM client initialisation in a way that
conflicts with canonical routing. Canonical version wins; the llm smoke CLI entry
(`llm.smoke`) is dropped from the diagnostics catalog.

**Collision 3 — `webpanel.py`:**  
Downstream of the skipped `panel.py`. File removed; its functionality (web-based
status surface) is subsumed by the existing `panel/` server and the new `summary`
subcommand.

## Consequences

- All 12 cherry-picked commits land with full test coverage (709 tests passing).
- `wm panel summary` provides the read-only operator dashboard originally in `panel.py`.
- `/api/living` exposes Wild Feature Catalog data to the web panel.
- Three worktree capabilities (llm smoke, raw panel.py, webpanel.py) are intentionally
  not ported; they are superseded or deferred.
- The integration branch is ready for PR review and merge into `main`.
