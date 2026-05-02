Status: WORKING
Last verified: 2026-04-28
Verified by: Codex
Doc type: reference

# Documentation Index

This is the canonical map for WM documentation.

If you are a new engineer or LLM, read these first:

1. [../AGENTS.md](../AGENTS.md)
2. [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)
3. [Codex Working Rules](CODEX_WORKING_RULES.md)
4. [Roadmap](ROADMAP.md)

The repo uses a Diataxis-style split:

- **handoff / status**: what is true now
- **howto**: exact operational steps
- **reference**: contracts, tables, layouts, interfaces
- **design / adr**: intended architecture and durable decisions
- **postmortem**: failed paths and retirement decisions

## Current State / Handoff

- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md) - best first-read for current WM platform state
- [Next Chat Handoff](NEXT_CHAT_HANDOFF.md) - compact continuation brief for a fresh chat
- [Work Summary](WORK_SUMMARY.md) - compact summary of what the repo has built
- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md) - current summon/spell truth source
- [Roadmap](ROADMAP.md) - canonical intended product direction: per-character arcs, exclusive rewards, wild powers, companion behavior, live scenes, conversation steering, and locked-contract LLM use. Current-state docs remain the truth for what is proven now

## How-To / Operations

- [Development Workflow](DEVELOPMENT_WORKFLOW.md) - default repo workflow
- [How-To Conventions](HOWTO_CONVENTIONS.md) - format rules for future operational guides
- [Cleanup Playbook](CLEANUP_PLAYBOOK.md) - cleanup and reset discipline
- [Deployment Windows](DEPLOYMENT_WINDOWS.md) - Windows-oriented setup/runtime notes

## Architecture / Decisions

- [ADR 0001: No stock live spell carriers](adr/0001-no-stock-live-spell-carriers.md)
- [ADR 0002: Extend the existing action bus](adr/0002-extend-existing-action-bus.md)
- [ADR 0003: Client shell bank for visible WM spells](adr/0003-client-shell-bank-for-visible-wm-spells.md)
- [Native Bridge Action Bus](native-bridge-action-bus.md)
- [Spell Shell Bank V1](SPELL_SHELL_BANK_V1.md)
- [Broug Guard Pipeline V1](BROUG_GUARD_PIPELINE_V1.md) - Broug-scoped parry-anything, moving-ranged, Deflect, and Riposte progression lane
- [Broug Lightness Assassin V1](BROUG_LIGHTNESS_ASSASSIN_V1.md) - Broug's murim-style qinggong movement, marked-meridian followups, and Silent Meridian quest lane
- [Broug Empty Court V2](BROUG_EMPTY_COURT_V2.md) - Broug's First Peak continuation: room pressure, Qi Reversal cleanse, Predator sustain, and Vitality Drain
- [Working Strategies V1](WORKING_STRATEGIES_V1.md) - reusable quest, ability, item, scene, marker, and proof patterns that survived live feature work

## Postmortems / Retired Paths

- [Summon Failure Postmortem](SUMMON_FAILURE_POSTMORTEM.md)
- [Windows Detached Watch Launch Postmortem](WINDOWS_DETACHED_WATCH_LAUNCH_POSTMORTEM.md)
- [mod-wm-prototypes README](../native_modules/mod-wm-prototypes/README.md)

## Reference / Contracts

- [Custom ID Ledger](CUSTOM_ID_LEDGER.md)
- [Working Strategies V1](WORKING_STRATEGIES_V1.md)
- [Personal Journey Spine V1](CHARACTER_EXCLUSIVITY_V1.md) - per-character arcs, unlocks, reward instances, steering notes, and prompt queue
- [Arc + Reward Factory V1](ARC_REWARD_FACTORY_V1.md) - first product-facing personal arc publisher using fresh quest slots and visible managed rewards
- [Content Release Pipeline V1](CONTENT_RELEASE_PIPELINE_V1.md) - strict base schemas and release gates for quests, abilities, items, scenes, spawns, and environment effects
- [Content Required Fields](CONTENT_REQUIRED_FIELDS.md) - mandatory quest, item, ability, DBC, and WM aura-isolation fields before player-facing deploy
- [Content Workbench V1](CONTENT_WORKBENCH_V1.md)
- [Journal Layer V1 / V2](JOURNAL_LAYER_V1.md) - current subject-memory reader and inspect status
- [Prompt Package V1](PROMPT_PACKAGE_V1.md) - historical prompt-package reference; check status header before trusting
- [Context Pack V1](CONTEXT_PACK_V1.md) - current deterministic context-pack reference
- [Item Slot Pipeline V1](ITEM_SLOT_PIPELINE_V1.md)
- [Quest Draft Pipeline V1](QUEST_DRAFT_PIPELINE_V1.md)
- [Spell Slot Pipeline V1](SPELL_SLOT_PIPELINE_V1.md)

## Superseded Planning Notes

These files are useful history, but they are not the current roadmap:

- [Phase 2 Contextual Quest Generation](PHASE2_CONTEXTUAL_QUEST_GENERATION.md)
- [Quest Publish Plan V1](QUEST_PUBLISH_PLAN_V1.md)
- [Content Candidates V1](CONTENT_CANDIDATES_V1.md)
- [Content Candidates V2](CONTENT_CANDIDATES_V2.md)
- [Content Candidates V4](CONTENT_CANDIDATES_V4.md)

Use [Roadmap](ROADMAP.md), [WM Platform Handoff](WM_PLATFORM_HANDOFF.md), and [Work Summary](WORK_SUMMARY.md) for active direction. `part1_transcript.md` is historical transcript material even though it is not under `docs/archive/`.

## Templates

- [status template](templates/status.md)
- [handoff template](templates/handoff.md)
- [postmortem template](templates/postmortem.md)
- [ADR template](templates/adr.md)
- [how-to template](templates/howto.md)
