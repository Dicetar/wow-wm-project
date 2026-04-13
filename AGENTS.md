# WM Agent Rules

Read these in order before making non-trivial changes:

1. [Documentation Index](docs/README_OPERATIONS_INDEX.md)
2. [WM Platform Handoff](docs/WM_PLATFORM_HANDOFF.md)
3. [Codex Working Rules](docs/CODEX_WORKING_RULES.md)

Non-negotiable rules:

- Read the existing systems before proposing new architecture. Check `src/wm/`, `control/`, `native_modules/mod-wm-bridge/`, and `native_modules/mod-wm-spells/` first.
- Separate client truth from server truth before spell, item, UI, or shell work.
- Classify outcomes as `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`.
- Never reuse stock spell IDs as permanent WM carriers.
- Clean the lab before summon or pet testing.
- After three failed attempts on the same approach, stop and write the structural reason before changing code again.
- If docs conflict, trust current-state docs and postmortems over design notes.

Summon-specific entry points:

- [Summon and Spell Platform Status](docs/SUMMON_SPELL_PLATFORM_STATUS.md)
- [Summon Failure Postmortem](docs/SUMMON_FAILURE_POSTMORTEM.md)
