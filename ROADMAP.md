Status: DESIGN_TARGET
Last verified: 2026-04-14
Verified by: ChatGPT
Doc type: program roadmap

# WM Program Roadmap

This file is the **program-level roadmap** for WM.

It complements, but does not replace:

- `docs/ROADMAP.md` for the current native/control execution path
- `docs/WM_PLATFORM_HANDOFF.md` for current status
- `docs/WORK_SUMMARY.md` for recent completed work
- `docs/JOURNAL_LAYER_V1.md` for the journal slice
- `docs/CONTENT_WORKBENCH_V1.md` for the operator-first content lane
- `docs/QUEST_DRAFT_PIPELINE_V1.md` for structured quest drafting

Use this file when deciding **what WM should become**, **what tech to keep**, and **what order to build the remaining platform in**.

---

## 1. Executive summary

WM is already beyond the old “bounty board prototype” stage.

Today the repo already has a real platform spine:

- Python package and CLI-first control plane
- WM-owned schema and bootstrap flow
- deterministic event spine with inspect / preview / run / watch
- native AzerothCore live perception path through `mod-wm-bridge`
- native action queue contracts with player scoping and policy gates
- content workbench flows for managed items, spells, and shell-bank behavior
- journal groundwork and quest draft groundwork
- tests around control, apply, journal, quests, and native bridge work

That means the project should **not** reset back to a thin prototype.

The correct direction is:

1. keep the current external-first Python control plane
2. continue pushing native bridge + typed actions as the long-term runtime substrate
3. finish the world-model / target-recognition / journal layers so WM can understand subjects and history cleanly
4. make content generation deterministic and reviewable first
5. place LLM assistance on top of locked contracts, not underneath them

---

## 2. Recommended tech decisions

### 2.1 Core stack to keep

**Keep Python as the main WM language.**

Reason:

- the repo is already materially invested in Python
- the current control / CLI / content / journal / quests slices fit Python very well
- fast iteration matters more than web-stack aesthetics
- Python is the best place to keep planners, validators, summarizers, and DB-integrated tooling together

### 2.2 Runtime architecture to keep

**Keep AzerothCore as the runtime body and WM as the external brain.**

Reason:

- this is already the working architectural truth of the repo
- the native bridge now gives a realistic growth path without throwing away the external-first model
- it preserves operator control, replayability, and auditability

### 2.3 Native layer decision

**Keep C++ native work thin and typed.**

The native layer should do only these jobs:

- sense canonical in-game facts
- expose structured context snapshots when asked
- execute registered typed actions
- return explicit result / error JSON

It should **not** become a second brain.

### 2.4 Database decision

Use the current world DB plus WM-owned tables, but keep the ownership boundary strict.

Recommended ownership rule:

- AzerothCore tables remain the source of mechanical truth
- WM-owned tables store memory, policy, provenance, staging, rollback, and generated artifact metadata
- direct mutation of non-WM-owned content stays limited, typed, and auditable

### 2.5 API / UI decision

**Do not front-load a big web UI.**

Recommended order:

- CLI first
- optional FastAPI service second
- thin operator UI third

Reason:

The hard part of this project is not rendering forms. It is reliable sensing, deterministic planning, safe publish/apply, and meaningful world memory.

### 2.6 LLM decision

**LLM stays advisory and schema-bound.**

LLM can help with:

- proposal drafting
- text generation
- quest flavor and narrative variants
- candidate ranking
- summarization

LLM must not get:

- arbitrary SQL power
- arbitrary shell or file power
- arbitrary GM command power
- direct unreviewed world mutation

### 2.7 Memory / retrieval decision

**Use WM’s own journal and codex as the main retrieval layer.**

Do not build the system around live lookups to public WoW websites.

Use:

- AzerothCore DB truth
- WM subject definitions and enrichments
- WM player-subject journal
- WM event log
- curated lore dictionaries if needed

This is faster, more reliable, and more controllable.

---

## 3. Target end-state

WM should become a **world-intelligence platform** with six stable layers:

1. **Perception**  
   ingest canonical player/world events and request deterministic snapshots

2. **Recognition**  
   resolve targets into meaningful subject identities such as:
   - specific NPC
   - specific spawn
   - creature family / type cluster
   - settlement role
   - faction role
   - zone / subzone / scene context

3. **Memory**  
   maintain append-only raw history plus prompt-ready summary views

4. **Planning**  
   inspect → propose → validate → dry-run → apply → verify

5. **Content**  
   manage quests, rewards, scenes, item shells, spell shells, rumors, contracts, mentors, and nemeses

6. **Direction**  
   let operators and later LLMs choose among registered recipes and policies

When these layers are stable, WM stops feeling like a quest utility and starts feeling like a real world director.

---

## 4. Program principles

### 4.1 Deterministic first, generative second

If a feature cannot be inspected, replayed, dry-run, and explained, it is not ready.

### 4.2 Native facts, external planning

C++ senses and executes. Python normalizes, remembers, evaluates, and decides.

### 4.3 Memory is built from events, not vibes

WM should infer meaning from recorded actions and derived counters, not from LLM guesswork.

### 4.4 Subjects matter more than raw rows

WM should think in terms of:

- Bethor Iceshard, mage trainer in Undercity
- Grey Wolf, shabby local beast near Goldshire
- Stormwind guards in Elwynn/Westfall
- murloc groups on this shoreline

not only raw `creature_template` fields.

### 4.5 Generated content is lifecycle-managed

Everything generated by WM should move through states such as:

- draft
- staged
- active
- retired
- archived

### 4.6 The operator lane stays first-class

Manual and operator-driven flows remain the source of truth for how the platform should behave.

---

## 5. Capability map

WM development should be organized into these capability tracks.

### Track A. Platform substrate

- bootstrap/build/runtime helpers
- env/config validation
- MySQL / SOAP / native bridge connectors
- schema ownership
- migrations
- logging and diagnostics
- replayable tests

### Track B. Perception and recognition

- event normalization
- subject resolver
- type/family/faction/npcflag decode
- zone / settlement / role recognition
- nearby context snapshots

### Track C. Memory and journal

- append-only event storage
- per-player / per-subject counters
- special events
- summary generation
- zone mood / local legend summaries

### Track D. Control and policy

- inspect / validate / dry-run / apply / audit
- control contract registry
- action policy and capability selection
- provenance and rollback

### Track E. Content platform

- quest drafts and publishing
- item/shell/spell management
- scene composition
- rumors, contracts, mentor arcs
- nemesis and patron systems later

### Track F. LLM assistance

- context packing
- recipe selection assistance
- constrained proposal generation
- narrative text variants
- critique / revise loop

---

## 6. Roadmap by phase

## Phase 0 — Hardening the current platform baseline

### Goal

Turn the current repo into a boringly reliable base for future world-intelligence work.

### Why this phase matters

The project already has a lot of moving parts. Before adding more ambition, the platform needs clearer boundaries and stronger day-to-day reliability.

### Deliverables

- verify and document the current supported runtime matrix:
  - native bridge
  - combat-log fallback/debug path
  - SOAP fallback paths
  - lab build path
  - legacy addon path only as historical reference
- tighten environment/bootstrap docs so a fresh machine can reach a known-good state
- standardize WM-owned table bootstrap, verification, and drift checks
- improve operator diagnostics for:
  - DB connectivity
  - SOAP readiness
  - native bridge readiness
  - policy gate readiness
- add a “system health” command that prints one summary view
- make test categories explicit:
  - unit
  - DB-integration
  - bridge-contract
  - content-plan
- document which features are production-ready, lab-ready, or design-only

### Exit criteria

- a fresh checkout can reach a known-good local build from repo docs
- WM can report live readiness in one command
- the repo clearly separates current truth from aspirational docs
- failures in DB/SOAP/native setup are diagnosable without source diving

---

## Phase 1 — Subject recognition and codex foundation

### Goal

Teach WM to recognize what a target **is**, not only what raw IDs say.

### Why this phase matters

This is the missing foundation for meaningful world reactions.

Without it, WM can generate content only around raw entries and thin metadata.

With it, WM can reason about:

- a trainer vs a guard vs a villager
- a wolf as a wolf, and also as a local beast in a specific area
- “King Mrglmrgl” as both a named subject and part of the murloc class of beings

### Deliverables

- `subject resolver` layer that maps raw world references to WM subject cards
- subject-card schema covering:
  - canonical id
  - kind
  - display name
  - title/subname
  - role tags
  - creature type/family/faction meaning
  - area / settlement / zone context
  - WM notes / enrichments
- decoders for common AzerothCore fields:
  - faction
  - npcflag
  - creature type
  - creature family
  - rank
  - unit class
- subject-cluster support:
  - exact subject
  - subject archetype
  - family/group cluster
  - local population cluster
- enrichment tables and loaders for WM-owned annotations
- operator command to inspect resolved subject context

### Exit criteria

- given a player + target, WM can build a readable subject card
- given a kill event, WM can resolve both the exact subject and a useful group bucket
- operators can inspect why a subject was classified the way it was

---

## Phase 2 — Journal Layer V2 and memory pipeline

### Goal

Turn the current journal prototype into a real DB-backed memory layer.

### Why this phase matters

WM’s long-term value depends on memory.

The journal is how the platform stops being a stateless trigger bot.

### Deliverables

- DB-backed load/save helpers for journal tables
- subject definition and enrichment loading
- raw event ingestion into journal-facing WM tables
- per-player / per-subject counters:
  - kills
  - skins
  - feeds
  - quests started/completed/rewarded
  - training interactions
  - item hand-ins
  - notable conversation / contract milestones later
- special-event rows for narrative milestones
- prompt-ready summarizer fed from real DB rows
- zone and settlement summary rollups
- initial local-legend and local-mood views

### Suggested schema direction

Keep the current architectural idea:

- append-only raw events
- derived counters
- summary view/materialization

Do **not** collapse memory into one mutable text blob.

### Exit criteria

- the Stieve / Grey Wolf examples can be produced from real DB-backed rows
- WM can answer “what does this player mean to this subject or group?”
- operators can inspect both raw event history and compact memory summaries

---

## Phase 3 — Deterministic context packs

### Goal

Build a reusable context assembly pipeline for operators first and LLMs later.

### Why this phase matters

Recognition and journal data need to become consumable packets.

### Deliverables

- context-pack builder for one player / one event / one target
- pack sections such as:
  - source event
  - player card
  - subject card
  - recent related events
  - journal summary
  - quest/runtime state
  - nearby context snapshot
  - zone / local mood
  - eligible recipes
  - policy gates
- versioned pack schema
- text and JSON renderers
- snapshot request integration with native bridge when available

### Exit criteria

- one command can produce a stable context pack for a live event
- the same pack can feed operator review or future LLM proposal generation
- pack generation is deterministic and testable

---

## Phase 4 — Quest publish pipeline completion

### Goal

Finish the path from quest draft to safe publish.

### Why this phase matters

The repo already has a quest draft slice. The missing part is safe publication and rollback at platform quality.

### Deliverables

- schema verification against the live `quest_template` shape
- reserved quest-id checks
- rollback snapshot capture for quest-linked rows
- dry-run and apply modes
- publish audit logging
- verify-after-apply step
- operator helpers for staged quest review and promotion
- reusable bounty templates upgraded into a generalized quest publish path

### Exit criteria

- WM can take a validated quest draft and produce a reviewable publish plan
- apply mode captures rollback state and emits audit/provenance rows
- one operator can publish and, if needed, rollback a WM quest cleanly

---

## Phase 5 — Managed content platform expansion

### Goal

Broaden managed content beyond the current shell/item/spell workbench into a coherent artifact system.

### Deliverables

- unified artifact metadata for:
  - quests
  - items
  - spell shells
  - summon shells
  - scene packages
  - rumor bundles
- artifact lifecycle model with provenance links
- slot/state governance for managed items and shells
- better direct operator tooling for grant/ungrant/test flows
- low-risk content package types:
  - rumors
  - letters
  - mentor tasks
  - patrol bounties
  - local warnings

### Exit criteria

- WM-managed artifacts look like one family of objects instead of isolated feature silos
- operators can inspect lifecycle, provenance, and rollback for managed content

---

## Phase 6 — Event spine convergence and native-first truth

### Goal

Move more of WM’s live truth onto native bridge facts while keeping fallbacks available.

### Why this phase matters

Native bridge should become the durable substrate for live WM facts.

### Deliverables

- native parity for the most valuable event categories:
  - kill
  - quest granted
  - quest completed
  - quest rewarded
  - optional interaction hooks as they become safe
- event normalization layer with consistent canonical WM event shapes
- event replay tooling
- suppression/cooldown behavior unified across adapters
- reconciliation rules between native truth, combat-log fallback, legacy addon-derived history, and runtime queries where needed

### Exit criteria

- the same high-level WM logic can run on native_bridge with clear fallback behavior
- native bridge becomes the preferred fact source for supported events
- fallback adapters remain usable without polluting the domain layer

---

## Phase 7 — Operator-grade world direction features

### Goal

Build the first truly “WM” features that feel like a world director rather than a utility set.

### Deliverables

- mentor relationship flows
- local reputation / local legend titles
- zone mood state
- dynamic bounty families
- subject-specific follow-up tasks
- small scene composition:
  - temporary spawn
  - say/emote
  - short gossip override
  - escort/follow moments later
- low-risk narrative reward types:
  - rumor
  - note/letter
  - temporary title/tag
  - factional favor counters

### Exit criteria

- a player’s repeated behavior changes what the world offers them
- at least one settlement or zone can reflect accumulated WM memory in a visible way
- content feels reactive, not merely randomized

---

## Phase 8 — Controlled LLM assistance

### Goal

Add LLM help on top of locked recipes, context packs, and policy gates.

### Deliverables

- recipe-aware prompt builders
- constrained proposal generation to existing control contracts
- narrative-text generation lanes for:
  - quest text
  - rumors
  - NPC reactions
  - letters
- optional critique/revise loop for content drafts
- confidence / repair / retry logic
- full provenance on LLM-assisted proposals

### Non-negotiable rules

- no direct SQL output to live DB
- no direct shell/file command lane
- no freeform GM command lane
- no action outside registered contracts
- direct apply remains gated off by default

### Exit criteria

- LLM output improves text quality and choice quality without weakening safety
- manual/operator proposals remain the control reference lane

---

## Phase 9 — Advanced world systems

### Goal

Start building the bigger fantasy systems that make WM feel unique.

### Candidate systems

- patron / favor systems
- local ecology / retaliation systems
- nemesis generator
- contract/oath systems
- regional rumor propagation
- population memory clusters
- scene chains and micro-story arcs

### Constraint

Only build these after recognition, journal, context packs, and deterministic planning are already stable.

### Exit criteria

- at least one advanced world system reuses the same substrate instead of adding a one-off stack
- new systems mostly compose existing WM primitives instead of bypassing them

---

## Phase 10 — UX, API, and release engineering

### Goal

Make WM easier to operate and safer to evolve.

### Deliverables

- optional FastAPI operator API
- minimal operator dashboard
- saved inspections and proposals
- import/export for drafts and context packs
- CI split by test category
- fixture datasets for journal and control tests
- golden tests for pack rendering and proposal generation
- lab → working promotion checklists
- release notes and migration notes

### Exit criteria

- one operator can inspect, draft, dry-run, apply, and verify without living in raw source files
- the repo is safe to evolve without constant regression fear

---

## 7. What to build first inside each phase

### Highest-priority missing pieces

These are the next best investments by value:

1. **Subject resolver**
2. **DB-backed Journal Layer V2**
3. **Deterministic context-pack builder**
4. **Quest publish/rollback completion**
5. **Artifact/provenance unification**
6. **Native parity for core event facts**
7. **Local legend / mentor / zone-mood features**
8. **LLM constrained proposal layer**

If a sprint can only do one thing, pick from this list.

---

## 8. Suggested repository structure direction

Current structure is already usable. The main improvement should be conceptual clarity.

Recommended stable module grouping:

- `wm/control/`
  - contracts, validation, apply, policy, audit
- `wm/events/`
  - adapters, normalization, replay, watch
- `wm/subjects/`
  - resolvers, codex, enrichment, decoders
- `wm/journal/`
  - event store helpers, counters, summarizers, rollups
- `wm/context/`
  - context pack builders and renderers
- `wm/quests/`
  - drafts, validation, compile, publish, rollback
- `wm/content/`
  - managed artifacts, workbench, shells, scenes
- `wm/runtime/`
  - SOAP/native runtime bridges and capability probing
- `wm/llm/`
  - prompt/context assembly, adapters, repair loops

This is not a mandatory refactor now. It is the direction to converge toward as the codebase grows.

---

## 9. Risks and mitigation

### Risk: native bridge scope explosion

Mitigation:
- keep actions typed and narrow
- prove in bridge lab first
- never add a generic GM-command action

### Risk: world-model hand-waving

Mitigation:
- subject cards come from deterministic resolution and WM enrichments
- journal summaries come from recorded facts and counters

### Risk: content mutation becoming untraceable

Mitigation:
- provenance for every managed artifact
- rollback snapshots before apply
- draft/staged/active/retired lifecycle

### Risk: LLM pressure arriving too early

Mitigation:
- finish context packs, policies, and deterministic planning first
- keep manual lane first-class

### Risk: too many parallel feature spikes

Mitigation:
- require every new feature to declare which existing WM substrate it reuses
- prefer composition over new one-off pipelines

---

## 10. Definition of success

WM is successful when all of these are true:

- it can recognize a player, subject, and local context in human-meaningful terms
- it can remember repeated interactions as both raw history and compact summaries
- it can produce reviewable content and action proposals deterministically
- it can apply and verify live changes safely through typed channels
- it can create reactive content that feels tied to player behavior rather than random generation
- LLMs improve the system’s expression and option quality without becoming trusted executors

That is the real destination.

Not “AI inside WoW.”

A **reliable world-intelligence platform** for AzerothCore.

---

## 11. Immediate next-sprint recommendation

If only one concrete sequence is chosen next, do this:

1. implement the subject resolver slice
2. complete Journal Layer V2 against real DB rows
3. add a context-pack builder command
4. finish quest publish plan + rollback path
5. then use those four pieces to build the first truly reactive mentor/local-legend feature

That path unlocks the largest amount of future WM work with the least wasted effort.
