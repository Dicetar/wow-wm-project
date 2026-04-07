# Roadmap (current)

This file reflects the **current implementation state** of the repository.

The original bootstrap-era roadmap has been preserved at:

- `docs/archive/ROADMAP.bootstrap.md`

## Project principles

Use a **retrieval-first external service** with a **translation layer** in front of any LLM work.

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

### Quest platform prototype

Implemented:
- live DB bounty quest generation
- schema-aware quest validator and SQL compiler
- quest publish preflight against the live schema
- rollback snapshots and publish logs
- live publish with SOAP runtime reload commands
- live quest edit for title / reward changes
- quest inspection / comparison tools
- rollback command restoring from latest snapshot
- reserved-slot seeding and managed-slot enforcement
- duplicate-title guard for the same questgiver

This means the repo is already beyond "bootstrap only" status.

---

## Phase 1 — Quest platform hardening

### Goal
Turn the working quest prototype into a reliable operator-grade WM content pipeline.

### Deliverables
- mandatory managed reserved slots for quest publishing
- duplicate-title and active-slot safety checks
- rollback v1 with runtime sync
- updated docs matching the real codebase
- more explicit publish / rollback state reporting

### Exit criteria
- a quest can be seeded into a staged slot
- a generated quest can be published live
- the same quest can be edited live without going through a full republish
- the quest can be rolled back from the latest snapshot
- publishing the same effective quest twice to the same questgiver is blocked by default

---

## Phase 2 — Contextual quest generation

### Goal
Make quest generation context-aware instead of merely syntactically valid.

### Deliverables
- generation that consumes target resolver output directly
- journal-aware generation inputs
- reward scaling and kill-count heuristics
- duplicate / repetition controls using recent history
- more quest archetypes beyond bounty:
  - delivery
  - investigate
  - report
  - collection

### Exit criteria
- generated quests use world facts instead of raw IDs
- repeated generation for the same area / questgiver becomes meaningfully different without becoming random garbage
- recent quest history affects new generation choices

---

## Phase 3 — Registry and lifecycle governance

### Goal
Manage WM-created artifacts as first-class objects with provenance and lifecycle.

### Deliverables
- stronger artifact registry conventions
- staged → active → retired / archived lifecycle discipline
- cache-risk and reused-ID tracking
- provenance in publish logs:
  - source prompt / generator kind
  - target context
  - operator action

### Exit criteria
- every generated quest can be traced to its source and lifecycle state
- slot reuse is intentional and visible
- rollback and retirement semantics are explicit instead of implied

---

## Phase 4 — Evented WM lite

### Goal
Let the WM react to the world without requiring a custom C++ bridge yet.

### Deliverables
- simple event ingestion adapters:
  - DB polling
  - quest completion checks
  - kill milestone checks
  - manual / chat-triggered WM commands
- session memory and anti-spam logic
- lightweight world reactions:
  - rotating board refreshes
  - follow-up quest offers
  - simple generated announcements

### Exit criteria
- a player action can trigger a WM reaction using resolver + journal context
- eventing works without baking WM logic into the core server

---

## Phase 5 — Item slot pipeline v1

### Goal
Begin item work safely, using the same discipline learned from quests.

### Deliverables
- reserved item slot strategy
- item validator with hard caps
- publish / rollback flow for managed item slots
- quest reward integration for managed items

### Exit criteria
- one managed custom item can be produced, rewarded, and retired without unsafe freeform mutation

---

## Phase 6 — Thin bridge exploration

### Goal
Improve live-awareness only after the external platform is strong enough to deserve a bridge.

### Deliverables
- investigate a minimal AzerothCore-side bridge only if a compile-capable source path is available
- structured event emission to the external WM service
- no migration of WM decision-making into the core itself

### Exit criteria
- transient world events can be emitted cleanly to the external WM without changing the core project philosophy

---

## What is intentionally not first

Not first:
- Eluna dependency
- combat overhaul
- deep item generation without slot governance
- direct freeform LLM-to-SQL content mutation
- giant UI/admin surface area

Those are all real possibilities later, but they are not the shortest path to a stable World Master platform.
