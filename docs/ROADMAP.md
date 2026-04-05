# Roadmap

## Architecture choice

Use a **retrieval-first external service** with a **translation layer** in front of any LLM work.

The WM should not start by generating prose. It should start by understanding the world deterministically.

## Phase 0 — foundation

### Goal
Make the runtime predictable and the project runnable on your machine.

### Deliverables
- Python project skeleton
- local config via `.env`
- bootstrap SQL for WM-owned tables
- lookup ingestion convention
- Windows deployment guide
- Target Resolver v1 CLI

### Exit criteria
- local environment boots successfully
- tests pass
- a sample creature entry can be resolved into a normalized profile

---

## Phase 1 — Target Resolver v1

### Goal
Turn raw AzerothCore creature data into LLM-safe target profiles.

### Inputs
- `creature_template_full` export
- enum maps (`type`, `family`, `npcflag`, `rank`, `unit_class`)
- optional faction-label map

### Outputs
- normalized target profile JSON with:
  - entry
  - name
  - subname
  - level range
  - faction id + optional label
  - service roles
  - mechanical type
  - family
  - rank
  - unit class

### Exit criteria
- Bethor resolves correctly as a quest giver humanoid with faction 68
- Grey Wolf / Timber Wolf resolve correctly as beasts with wolf family
- service roles are decoded from bitmasks, not guessed from names

---

## Phase 2 — Journal Layer

### Goal
Track what the player has done with subjects.

### Deliverables
- `wm_subject_definition`
- `wm_subject_enrichment`
- `wm_player_subject_journal`
- `wm_player_subject_event`
- journal summarizer that returns compact history per `(player, subject)`

### Exit criteria
- journal can represent examples such as:
  - "Player completed Stieve's quest"
  - "Player learned Mining from Stieve"
  - "Player killed Grey Wolf 18 times"
  - "Player skinned Grey Wolf 10 times"

---

## Phase 3 — Enrichment Layer

### Goal
Add narrative facts without touching core AzerothCore tables.

### Deliverables
- manual enrichment rows keyed by `subject_type + entry_id`
- support fields such as:
  - species
  - profession
  - role_label
  - home_area
  - short_description
  - tags

### Exit criteria
- Bethor can resolve to mechanical facts + enrichment facts
- Murloc-specific named NPCs can be identified via exact entry enrichment instead of model guessing

---

## Phase 4 — Prompt Builder

### Goal
Build model inputs from translated facts, not raw DB rows.

### Deliverables
- prompt context package builder
- compact journal summary formatter
- target profile formatter
- quest/NPC/event prompt templates

### Exit criteria
- prompts no longer contain raw integers like `npcflag=66`
- prompts only expose translated facts such as `service_roles=[QuestGiver, ProfessionTrainer]`

---

## Phase 5 — Quest Pipeline

### Goal
Generate and publish a safe first content type.

### Deliverables
- quest schema
- validator
- SQL compiler
- rollback snapshot table usage
- publish command runner

### Exit criteria
- one generated quest can be staged, published, and rolled back

---

## Phase 6 — Evented WM

### Goal
Connect player activity to world reactions.

### Deliverables
- event ingestion interface
- prototype adapters for logs / DB polling
- later thin-bridge integration if a compile-ready source tree becomes available

### Exit criteria
- a player action can trigger a WM reaction using target + journal context

---

## Value vs effort notes

| Slice | Value | Effort | Why it comes now |
|---|---:|---:|---|
| Target Resolver v1 | High | Low | Everything later depends on clean target facts |
| Journal Layer | High | Medium | Enables contextual memory without AI guessing |
| Enrichment Layer | High | Medium | Gives named NPCs specific identity beyond raw mechanics |
| Prompt Builder | Medium | Medium | Important, but only after facts are trustworthy |
| Quest Pipeline | Very High | Medium | First visible content payoff |
| Evented WM | Very High | High | Best delayed until fundamentals are deterministic |
