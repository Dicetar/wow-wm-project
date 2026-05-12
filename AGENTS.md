# WM Agent Rules

This file is the short router. Keep durable task knowledge in repo skills and current-state docs, not here.

## Read Order

Before non-trivial changes, read:

1. [Documentation Index](docs/README_OPERATIONS_INDEX.md)
2. [WM Platform Handoff](docs/WM_PLATFORM_HANDOFF.md)
3. [Codex Working Rules](docs/CODEX_WORKING_RULES.md)

Use current-state docs and postmortems over roadmap/design notes when they conflict.

## Project Skills

Use these repo-local skills when the task matches:

- `$wm-workflow` from `.agents/skills/wm-workflow/SKILL.md` for repo cleanup, docs, tests, workflow, handoff, and general code changes.
- `$wm-live-bridge-lab` from `.agents/skills/wm-live-bridge-lab/SKILL.md` for BridgeLab, native watcher, live proof, player scope, and summon/pet lab work.
- `$wm-content-release` from `.agents/skills/wm-content-release/SKILL.md` for quests, items, spells, shell abilities, arcs, scenes, context packs, candidate packs, and LLM proposal surfaces.

Skill requirements: each skill must have a `SKILL.md` with YAML frontmatter containing only `name` and `description`, then concise Markdown instructions. Optional `agents/openai.yaml` may hold UI metadata. Do not add README/changelog-style clutter inside skills.

## Non-Negotiables

- Read existing systems before proposing new architecture. Check `src/wm/`, `control/`, `native_modules/mod-wm-bridge/`, and `native_modules/mod-wm-spells/` first.
- Separate client truth from server truth before spell, item, UI, or shell work.
- Classify outcomes as `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`.
- Never reuse stock spell IDs as permanent WM carriers.
- Clean the lab before summon or pet testing.
- After three failed attempts on the same approach, stop and write the structural reason before changing code again.
- Do not add freeform SQL, GM-command, shell-command, config-edit, or direct LLM mutation lanes.

## Watcher Default

Use repo-owned watcher launchers instead of ad hoc detached PowerShell:

- `start-bridge-lab-all.bat` for normal BridgeLab startup with watcher.
- `start-bridge-lab-watch.bat` for watcher-only startup.
- `status-bridge-lab-watch.bat` and `stop-bridge-lab-watch.bat` for watcher operations.

The Windows detached watcher rule lives in [Codex Working Rules](docs/CODEX_WORKING_RULES.md) and [Development Workflow](docs/DEVELOPMENT_WORKFLOW.md).

## Summon Entry Points

- [Summon and Spell Platform Status](docs/SUMMON_SPELL_PLATFORM_STATUS.md)
- [Summon Failure Postmortem](docs/SUMMON_FAILURE_POSTMORTEM.md)
