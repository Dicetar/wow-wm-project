Status: WORKING
Last verified: 2026-04-17
Verified by: Codex
Doc type: reference

# Quest Draft Pipeline V1

## Why this slice exists

The repo can already do three useful things:

- resolve targets
- load WM-owned memory
- shortlist quest, item, and spell candidates

What it still could not do was turn that context into a **validated quest draft** that is safe to inspect before any publish step.

This slice adds that missing bridge.

## What is included

- `src/wm/quests/models.py`
- `src/wm/quests/bounty.py`
- `src/wm/quests/validator.py`
- `src/wm/quests/compiler.py`
- `src/wm/quests/demo.py`
- `tests/test_quest_drafts.py`

## Current scope

V1 is intentionally narrow:

- bounty-style quests only
- one kill objective
- one quest giver / one quest ender
- level-scaled default money reward with optional explicit override
- default stock supply-box item reward (`6827`, `Box of Supplies`) with optional explicit single-item override
- optional XP difficulty reward, defaulting to the current bounty policy tier when the quest schema supports it
- bounty drafts force repeatable quest semantics with `SpecialFlags |= 1`, preserving existing special flags while preventing prior rewarded state from blocking later bounty turn-ins
- SQL **plan preview**, not automatic publish

That is on purpose.

The project still needs a stronger publish/rollback layer before it should execute generated SQL against the live world DB.

## Why this is the right next step

It closes the largest gap in the current repo:

- before: the WM could understand the world, but not draft content safely
- after: the WM can build a structured quest draft, validate it, and compile a reviewable SQL plan

That gives you something concrete to test and critique before touching the live publish path.

## Local command

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.quests.demo
```

## Expected output

The demo prints JSON with three sections:

- `draft`
- `validation`
- `sql_plan`

A healthy result should show:

- `validation.ok = true`
- a staged quest ID in the WM range such as `910001`
- SQL statements for:
  - `quest_template`
  - `creature_queststarter`
  - `creature_questender`

## Important limitation

The compiler assumes a standard AzerothCore-style `quest_template` layout for the listed columns.

That makes this a **review and staging tool first**, not a blind publish tool.

Before auto-publish exists, the next safe step should be:

- schema-aware DB verification against your real `quest_template`
- rollback snapshot capture
- manual publish wrapper
- then automated publish once the dry run matches reality

## Next target after this

The most useful follow-up is:

**Quest Publish Plan V1**

That should add:

- schema verification
- preflight checks against reserved quest IDs
- rollback snapshot generation
- dry-run vs apply modes
- publish audit log rows in WM-owned tables
