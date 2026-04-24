Status: WORKING
Last verified: 2026-04-14
Verified by: Codex
Doc type: reference

# Documentation Index

This is the canonical map for WM documentation.

If you are a new engineer or LLM, read these first:

1. [../AGENTS.md](../AGENTS.md)
2. [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)
3. [Codex Working Rules](CODEX_WORKING_RULES.md)

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
- [Roadmap](ROADMAP.md) - intended direction, not current truth

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

## Postmortems / Retired Paths

- [Summon Failure Postmortem](SUMMON_FAILURE_POSTMORTEM.md)
- [Windows Detached Watch Launch Postmortem](WINDOWS_DETACHED_WATCH_LAUNCH_POSTMORTEM.md)
- [mod-wm-prototypes README](../native_modules/mod-wm-prototypes/README.md)

## Reference / Contracts

- [Custom ID Ledger](CUSTOM_ID_LEDGER.md)
- [Content Workbench V1](CONTENT_WORKBENCH_V1.md)
- [Journal Layer V1 / V2](JOURNAL_LAYER_V1.md) - current subject-memory reader and inspect status
- [Prompt Package V1](PROMPT_PACKAGE_V1.md) - historical prompt-package reference; check status header before trusting
- [Context Pack V1](CONTEXT_PACK_V1.md) - current deterministic context-pack reference
- [Item Slot Pipeline V1](ITEM_SLOT_PIPELINE_V1.md)
- [Quest Draft Pipeline V1](QUEST_DRAFT_PIPELINE_V1.md)
- [Spell Slot Pipeline V1](SPELL_SLOT_PIPELINE_V1.md)

## Templates

- [status template](templates/status.md)
- [handoff template](templates/handoff.md)
- [postmortem template](templates/postmortem.md)
- [ADR template](templates/adr.md)
- [how-to template](templates/howto.md)
