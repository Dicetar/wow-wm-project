Status: PARTIAL
Last reviewed: 2026-09-30
Evidence: source inspection and primary-source research; no runtime tests
Doc type: design / research

# WM Harness: Decision And Reading Guide

## Decision In Plain English

WM is a game-specific agent harness, not merely a chatbot, a quest generator, or a control panel. It connects an imperfect model to a persistent multiplayer world. Its job is to make creative decisions possible without requiring the model to understand AzerothCore internals or remember every safety rule.

**Recommendation: evolve this repository. Rebuild the director's execution contract, not the entire game integration.** Keep Python, Pydantic, the native C++ bridge/spell modules, managed publishers, shell bank, and the operator panel. Consolidate durable state and enforce the same release contract for operator and autonomous requests. Evaluate Pydantic AI behind the model adapter; do not make a framework migration the first milestone.

A clean-sheet implementation would still use Python/Pydantic and a narrow native C++ adapter. It would start with a transactional ledger, an explicit state machine, typed compiler interfaces, FastAPI, and a replaceable structured-output model adapter. It would not start with a society of agents, unrestricted MCP tools, or an LLM writing live SQL. See [architecture](ARCHITECTURE.md).

**Low-capability local models are a first-class constraint.** A model should choose between a few understandable outcomes, use supplied world references, and write the creative part. The harness handles database rows, IDs, legality, retries, reloads, client compatibility, and evidence. No prompt can make an arbitrarily weak model reliable; qualification determines which tasks a particular model may perform.

## Read Only What You Need

| Reader / task | Read |
|---|---|
| Local coding agent assigned one ticket | [Local-agent contract](LOCAL_AGENT_CONTRACT.md), then that ticket in [delivery plan](DELIVERY_PLAN.md) |
| Owner deciding direction | This page and [technology decisions](TECHNOLOGY_REVIEW.md) |
| Engineer implementing persistence/execution | [Current evidence](CURRENT_SYSTEM.md) and [architecture](ARCHITECTURE.md) |
| Content compiler implementer | Architecture's release section and existing [required fields](../../CONTENT_REQUIRED_FIELDS.md) |
| Model qualification / gameplay proof | [Evaluation and operations](EVALUATION_AND_OPERATIONS.md) |
| Checking external claims | [Sources](SOURCES.md) |

Do not feed this entire folder into each model call. Runtime WM receives a short evidence packet and one output schema, not architecture documents. Coding agents receive one task packet and selected files.

## Scope And Honesty

This pack is a researched recommendation, not a deployed redesign. It adds no live mutation, dependency, database migration, or service. Current source was inspected at HEAD `5a0ee41eb1fd9d9bd32db1fa7e0b780adf707122` with substantial local changes; HEAD alone does not identify that working tree. No suite, benchmark, build, or live proof ran for this research.

The locally emptied `src/wm/control/coordinator.py` was restored from its tracked implementation after its diff and callers were inspected. Its source now matches HEAD, but a runnable baseline remains unverified because no tests were run.

This extends the [September 23 rebuild plan](../wm-redesign-2026-09-23/REBUILD_PLAN.md), not a competing roadmap. Preserve its R1-R12 requirements and [ADR 0008](../../adr/0008-durable-player-experience-director.md). The new contribution is a technology comparison, explicit weak-model interface, native retry analysis, and an actionable delivery sequence. Implementation decisions must be recorded when adopted; this document does not silently supersede an ADR.

## What Changes First

1. Verify a trustworthy baseline and identify which local changes belong together.
2. Classify native action retry safety and remove blind retry for effects with uncertain outcomes.
3. Give the director one durable request/obligation lifecycle and immutable release artifacts.
4. Give the model one small decision contract and automatically create development requests for missing mechanics.
5. Prove a complete universal content loop, including restart recovery and client-visible results.
6. Improve editorial quality, latency, and model costs using measured failures.

The first playable loop is not another named-character arc. It is: selected player request -> grounded plan -> supported quest/scene/power -> visible result -> remembered obligation -> resolution or coherent replacement. Unsupported mechanics produce a tracked task, not a fake reward or endless retries.

## Product Requirements That Must Survive

- WM observes the environment continuously but need not interrupt on every event.
- On Demand, Moderate (default), and Active change initiative, not mutation authority.
- Existing obligations, recovery, and cleanup continue when initiative is paused.
- World and Character Author's Notes stay separate from inferred memory. Explicit notes outrank inferred preferences; incompatible firm constraints require clarification.
- World change is allowed with cause, affected-player/quest handling, and a defined lifecycle. Preserve coherent continuity, not an artificially frozen world.
- Supported capabilities can run automatically under granted policy. New code, native behavior, client patches, and restarts remain staged development/release work.
- New quests, items, spells, and encounters must function, not just have convincing names and text.
- The operator panel explains what WM observed, decided, applied, verified, and still owes the player.

## Completion Definition

The harness is usable when a qualified local model can complete supported scenarios through the small interface, cannot bypass deterministic gates even when instructed to, survives interruption without duplicating rewards or losing obligations, and reports success only at the proof level actually reached. The delivery plan defines that scope; this research does not claim it has been met.
