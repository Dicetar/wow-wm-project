# Transcript Archive

This directory preserves transcript snapshots that shaped the current WM project design and implementation.

## What belongs here

These files are historical design / build transcripts that are useful for:
- recovering project intent
- tracing why certain architecture choices were made
- matching repo milestones to the conversations that produced them

They are **archive material**, not the live source of truth.

## Current source of truth

For the current implementation state and active plan, use:

- `README.md`
- `docs/ROADMAP.md`
- `docs/CLEANUP_PLAYBOOK.md`
- `docs/PHASE2_CONTEXTUAL_QUEST_GENERATION.md`

The roadmap inside older transcripts may describe interim plans or partially completed steps.
When transcript guidance conflicts with the current repo docs, prefer the current repo docs.

## Archive files

### `2026-03-28_wow-content-creation.md`
Foundational design-history transcript.

Main value:
- establishes the external-first WM direction
- captures why Eluna is not the first implementation track for this repack
- captures the dummy-slot / managed-ID thinking for quests, items, and spells
- captures the mini-journal / player-specific memory direction
- captures the early reasoning about live generation limits on WoW 3.3.5

### `2026-04-06_project-analysis-and-roadmap_part2.md`
Intermediate repo-analysis transcript.

Main value:
- evaluates the first repo baseline
- introduces the early quest draft / publish roadmap
- captures compatibility, preflight, publish, and rollback work in progress

### `2026-04-07_project-analysis-and-roadmap_part3.md`
Latest continuation transcript in this archive set.

Main value:
- captures the cleaner live quest workflow
- includes rollback / cleanup / republish / edit-live guidance
- is the most useful transcript to read when understanding how the repo moved from prototype quest drafting into live quest operations

## Practical reading order

If you only want the essentials:

1. `2026-03-28_wow-content-creation.md`
2. `2026-04-07_project-analysis-and-roadmap_part3.md`

Read part2 only if you want the intermediate implementation trail between those two.

## How this maps to the current roadmap

The repo is already beyond bootstrap and has a working live quest vertical slice.
The next active direction is:

1. finish hardening the quest platform where needed
2. move into contextual quest generation using resolver + journal data
3. then improve registry / lifecycle governance
4. only after that broaden into evented WM-lite and item-slot workflows

That progression should be read from `docs/ROADMAP.md`, not reconstructed manually from the archive transcripts.
