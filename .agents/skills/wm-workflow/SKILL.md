---
name: wm-workflow
description: Use when working in the WM repository on code changes, cleanup, documentation, tests, workflow polish, handoffs, or repo organization. Guides the required read order, dirty-worktree discipline, status labels, validation commands, and project-specific engineering boundaries for D:\WOW\wm-project.
---

# WM Workflow

## Start Here

Before non-trivial work, read the current-state chain:

1. `AGENTS.md`
2. `docs/README_OPERATIONS_INDEX.md`
3. `docs/WM_PLATFORM_HANDOFF.md`
4. `docs/CODEX_WORKING_RULES.md`

Then read task-specific current docs. Trust current-state docs and postmortems over roadmap/design notes when they conflict.

## Working Rules

- Inspect existing systems before proposing architecture: `src/wm/`, `control/`, `native_modules/mod-wm-bridge/`, and `native_modules/mod-wm-spells/`.
- Keep the WM split intact: Python owns decisions, state, validation, publishing, rollback, and audit; native modules own sensing, typed atomic actions, and shell-bound runtime behavior.
- Prefer extending the existing action bus, control registry, shell bank, workbench, or release pipeline over creating parallel middleware.
- Separate client truth from server truth before spell, item, UI, or shell work.
- Never use stock spell IDs as permanent WM carriers.
- Keep live mutation behind strict contracts. Do not add freeform SQL, GM command, shell command, config-edit, or direct LLM mutation lanes.
- Preserve user-owned dirty work. Check `git status --short` before editing, read diffs for files you touch, and avoid reverting unrelated changes.
- Classify outcomes as `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`.

## Default Loop

1. Read the current code and docs for the area.
2. Make the smallest useful change.
3. Run focused tests first.
4. Run broader tests when the change touches shared behavior.
5. Update docs in the same change when behavior or workflow changes.
6. End with exact status labels and remaining proof gaps.

Use `python -m pytest -q` as the full-suite command. Use focused tests while iterating, for example `python -m pytest tests/test_event_watch.py -q`.

On this Windows host, if bare `rg` fails with `Access is denied`, use `.\.wm-bootstrap\tools\ripgrep\rg.exe` or `.\.wm-tools\rg.exe`.

## Cleanup Discipline

- Remove generated scratch artifacts only after identifying what produced them and confirming they are not tracked source.
- Keep disposable local output out of git through `.gitignore`; do not hide real source directories.
- For quest/item/spell lab state, prefer repo rollback or purge tooling instead of hand-editing DB rows.
- Clean summon and pet lab state before summon/pet tests.
- After three failed attempts on the same approach, stop and write the structural reason before changing code again.
