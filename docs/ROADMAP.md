# Roadmap (current)

This file reflects the current implementation state of the repository.

The original bootstrap-era roadmap has been preserved at:

- `docs/archive/ROADMAP.bootstrap.md`

## Project principles

Use a retrieval-first external service with a translation layer in front of any LLM work.

The WM should not begin by generating prose. It should begin by understanding the world deterministically, then publishing live content through controlled, reversible operations.

Hard rules:

- the LLM never writes directly to the game
- every live publishable artifact must be validated first
- every live publishable artifact must be reversible
- managed ID ranges beat improvised IDs
- runtime sync is a real step, not a footnote
- prototype event ingestion must remain replaceable later

---

## Current implemented baseline

### Lookup and translation

Implemented:
- local config via `.env`
- bootstrap SQL for WM-owned tables
- target resolver and live target profile utilities
- candidate lookup / ranking helpers
- enum/ID translation files and lookup notes

### Quest, item, and spell platform baseline

Implemented:
- live DB bounty quest generation
- schema-aware quest validator and SQL compiler
- quest publish preflight against the live schema
- rollback snapshots and publish logs
- live publish with SOAP runtime reload commands
- live quest edit for title / reward changes
- quest inspection / comparison tools
- rollback command restoring from latest snapshot
- managed item slot publish flow
- managed spell slot publish flow
- quest reward flow that can attach managed items
- reserved-slot seeding and managed-slot enforcement across quest/item/spell ranges
- duplicate-title guard for the same questgiver

### Event spine baseline

Implemented on the event-spine track:
- canonical WM event contract and storage
- DB-first polling adapter against existing WM-owned journal events
- hidden addon-log tail adapter against `WMOps.log`
- client combat-log tail adapter against `WoWCombatLog.txt` as fallback/debug
- projection from canonical observed events into compact journal counters
- deterministic rule evaluation with cooldown guards
- reaction planning and execution through existing quest/item/spell publishers
- read-only inspect and preview commands for operator trust
- reusable reactive bounty rule storage
- direct quest-grant execution through SOAP for reusable reactive quests
- player quest runtime-state snapshots plus observed `quest_granted` / `quest_completed` / `quest_rewarded` transitions
- kill-burst gating for a stable repeatable quest with turn-in-only NPC linkage
- shared player/creature/NPC/quest/item/spell ref models for internal schemas
- native bridge adapter for server-truth kill, quest, loot, gossip, area, spell, item, aura, and weather events
- control contract registry for manual and future LLM action proposals
- Pydantic `ControlProposal` schema shared by humans and LLMs
- manual inspect/new/validate/apply workbench over the same executor gates
- native bridge action queue contract with scoped player DB control, policy gates, request/audit rows, and a broad fixed action vocabulary

This means the repo is already beyond bootstrap-only status and is moving toward an event-driven WM core.

### Rebuilt development baseline

Implemented:
- latest-baseline AzerothCore + module reconstruction tooling for native WM module work
- portable repo-relative `setup-wm.bat` -> `build-wm.bat` bootstrap flow under `.wm-bootstrap\`
- side-by-side build/run workflow instead of in-place repack mutation
- launcher and rebuild helper scripts for the rebuilt tree
- runtime DLL guard for MySQL/OpenSSL dependency mismatch detection
- isolated `D:\WOW\WM_BridgeLab` helper scripts for bridge rebuild/testing before promotion

Current truth:
- the rebuilt baseline is for WM development first
- it is not yet a gameplay-parity replacement for the original repack
- Individual Progression currently has known script/code drift
- some custom NPC/service content still depends on missing older module SQL/code pairings
- WeatherVibe loads but is not yet meaningfully configured in-world

---

## Phase 1 - Event spine hardening

### Goal
Turn the event spine into a reliable operator-grade WM orchestration layer.

### Deliverables
- unify canonical publish paths so event execution has one safe target per artifact type
- harden canonical event storage, cursor handling, and replay safety
- tighten projection/evaluation bookkeeping and anti-spam behavior
- make dry-run/apply reporting clearer across reaction planning and execution
- add a true read-only operator layer so previewing does not mutate WM-owned audit state
- update docs to reflect the event-driven direction

### Exit criteria
- one adapter can ingest world activity into canonical events
- a live hidden addon-channel source can feed the same event contract without server rebuilds
- the same event is never projected twice
- deterministic rules can emit reaction opportunities safely
- reaction execution can call the quest/item/spell publishers through one coherent path
- cooldowns suppress repeated firehose reactions
- reusable reactive quests cannot be accidentally purged or rolled back without explicit override

---

## Phase 2 - Control contracts and safe manual/LLM reactions

### Goal
Make reactions controllable through a narrow registry that both humans and LLMs can use safely.

### Deliverables
- keep `control/` as the one place for event/action/recipe/policy contracts
- make manual proposals the first-class test lane for every future LLM action
- keep direct apply to one registered action per observed event in v1
- persist proposal validation, dry-run, apply, and reject audit state
- only enable LLM-authored apply behind `WM_LLM_DIRECT_APPLY=1`

### Exit criteria
- a human can inspect an event, generate a proposal, validate it, dry-run it, and apply it without an LLM
- future LLM proposals use the exact same JSON schema and coordinator path
- unregistered actions, wrong player scope, stale events, duplicate applies, and high-risk mutations are rejected

---

## Phase 3 - Contextual smart reactions

### Native bridge action bus note
The native action bus has a proven isolated lab path: full build once, then `incremental-bridge-lab.bat` for C++ edits, lab MySQL on port `33307`, and `debug_ping`/`debug_echo`/`debug_fail` queue smoke tests before promotion. Before adding more live gameplay behavior, harden one narrow mutation at a time. The queue and policy schema are broad by design, but most native action kinds stay disabled or `not_implemented` until their C++ body has a dedicated lab test.

### Goal
Make reactions context-aware instead of merely structurally valid.

### Deliverables
- context shaping that consumes resolver output, journal summaries, and control perception packs directly
- event-to-reaction heuristics that use recent player history
- deterministic opportunity detection with optional LLM content shaping layered on top
- richer follow-up quest, reward, passive, and announcement payload generation
- duplicate/repetition controls using recent reaction and proposal history

### Exit criteria
- reactions use world facts instead of raw IDs
- repeated reactions for the same area or subject become meaningfully different without becoming random garbage
- recent history changes what WM chooses to do next

---

## Phase 4 - Registry and lifecycle governance

### Goal
Manage WM-created artifacts as first-class objects with provenance and lifecycle.

### Deliverables
- stronger artifact registry conventions
- staged -> active -> retired/archived lifecycle discipline
- cache-risk and reused-ID tracking
- provenance in publish logs and control proposal audit state

### Exit criteria
- every generated artifact can be traced to its source and lifecycle state
- slot reuse is intentional and visible
- rollback and retirement semantics are explicit instead of implied

---

## Phase 5 - Broader perception and content breadth

### Goal
Expand what WM can sense and create once control contracts are trustworthy.

### Deliverables
- more quest archetypes beyond bounty:
  - delivery
  - investigate
  - report
  - collection
- broader managed item use
- broader managed spell/passive use
- eventual creature/NPC authoring only if a chosen demo requires it
- on-demand nearby context snapshots from the native bridge

### Exit criteria
- WM can compose richer multi-artifact scenarios without breaking slot governance

---

## What is intentionally not first

Not first:
- Eluna dependency
- combat overhaul
- deep item generation without slot governance
- direct freeform LLM-to-SQL content mutation
- giant UI/admin surface area

Those are all real possibilities later, but they are not the shortest path to a stable World Master platform.
