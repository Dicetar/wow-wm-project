# WM Native Adventure Vision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (or subagent-driven-development) to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the fully personalized adventure system — a character
becomes "watched" by the WM on login, the WM senses what they do natively,
fills journals, decides arcs via LLM, and authors differentiated content
(quests, NPCs, mobs, objects, items, abilities) the player steers through
chat.

**Architecture:** Per ADR-0007. In-process bookkeeping (counters,
thresholds, effect gates, character lifecycle) is native C++ invoked from
game hooks. LLM, journal context, arc decisions, and content authoring stay
Python, routed back through the existing `wm_bridge_action_request` bus.
DB tables are directional: command tables (Python→C++) vs audit tables
(C++→Python, Python read-only).

**Tech Stack:** AzerothCore 3.3.5a C++ modules (`mod-wm-bridge`,
`mod-wm-spells`) built in BridgeLab (MSVC); Python 3 (`src/wm/`) with
pytest; MySQL (acore_world / acore_characters / wm audit DB).

**Non-negotiables (every task):**
- No freeform SQL / GM-command / shell / config-edit / direct-LLM mutation lane.
- `WM_LLM_DIRECT_APPLY=0` default — LLM-authored live apply stays blocked.
- Never reuse dirty/retired visible IDs (quest/item/spell/creature). Fresh ID + retire old.
- No native poll loop / second action runner (ADR-0002, ADR-0007).
- No WORKING claim without proof: DB row, native ping response, or in-game observation.
- BridgeLab is the build/test env. Player 5406 / Jecia. MySQL 127.0.0.1:33307.
- TDD: failing test → minimal impl → green → commit. Native pieces: build in
  BridgeLab + live proof before promotion to wm-project.

---

## Phase Map & Dependency Order

| Phase | Track | Unblocks | Status |
|-------|-------|----------|--------|
| 1 | Native Bookkeeping Migration | everything (real-time state) | reference impl landed (effect registry) |
| 2 | Active Character Lifecycle | the entry point — "watched" character | not started |
| 3 | Ability Taxonomy & Schema | differentiated abilities | not started |
| 4 | World Authoring Runtime | interactive generated content | not started |
| 5 | Decision Engine & Steering | ties the loop together | not started |

Phases are sequential by data dependency. Within a phase, tasks are
independent unless noted.

---

## Phase 1 — Native Bookkeeping Migration

Completes ADR-0007 action items 2–4. Makes counters/thresholds real-time so
later phases read fresh state instead of polled lag.

**Files:**
- Modify: `native_modules/mod-wm-bridge/src/wm_bridge_player_script.cpp`
- Create: `native_modules/mod-wm-bridge/src/wm_journal_counter.{h,cpp}`
- Create: `native_modules/mod-wm-bridge/src/wm_threshold_eval.{h,cpp}`
- Modify: `native_modules/mod-wm-bridge/src/wm_bridge_worldscript.cpp`
- Mirror all into `D:/WOW/WM_BridgeLab/src/modules/mod-wm-bridge/src/`
- Add to `D:/WOW/WM_BridgeLab/build/modules/modules.vcxproj` + `.filters`
- SQL: `data/sql/updates/pending_*/` (new `wm_journal_counter` audit table)
- Tests: `tests/test_journal_counter_read.py` (Python read-side contract)

### Task 1.1: wm_journal_counter audit table

- [ ] **Step 1: Write the migration SQL**

Create `data/sql/updates/pending_db_wm/<random>_wm_journal_counter.sql`:

```sql
CREATE TABLE IF NOT EXISTS wm_journal_counter (
    character_guid  INT UNSIGNED NOT NULL,
    counter_key     VARCHAR(120) NOT NULL,
    counter_value   BIGINT UNSIGNED NOT NULL DEFAULT 0,
    last_updated    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (character_guid, counter_key),
    INDEX idx_key (counter_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: Apply to BridgeLab DB and verify**

Run: `mysql -h127.0.0.1 -P33307 ... < <file>` then `DESCRIBE wm_journal_counter;`
Expected: 4 columns, composite PK.

- [ ] **Step 3: Commit** — `feat(DB): wm_journal_counter audit table`

### Task 1.2: Native counter increment on kill

- [ ] **Step 1: Write the read-side failing test**

`tests/test_journal_counter_read.py`:

```python
def test_counter_read_returns_zero_when_absent(mem_db):
    from wm.journal.counters import read_counter
    assert read_counter(mem_db, character_guid=5406, key="kill.beast") == 0

def test_counter_read_returns_value(mem_db):
    from wm.journal.counters import read_counter
    mem_db.execute("INSERT INTO wm_journal_counter VALUES (5406,'kill.beast',7,NOW())")
    assert read_counter(mem_db, character_guid=5406, key="kill.beast") == 7
```

- [ ] **Step 2: Run — expect FAIL** (`wm.journal.counters` missing)

- [ ] **Step 3: Implement `src/wm/journal/counters.py`** with `read_counter`
      (SELECT-only; Python never writes this table — ADR-0007).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Implement native writer** in `wm_journal_counter.cpp`:
      `WMJournalCounter::Increment(uint32 charGuid, std::string key, int delta)`
      → `WorldDatabase.Execute(INSERT ... ON DUPLICATE KEY UPDATE
      counter_value = counter_value + {delta})`.

- [ ] **Step 6: Wire into `wm_bridge_player_script.cpp`** `OnPlayerKilledCreature`
      → derive key (e.g. `kill.<creatureType>`), call `Increment`. Gate on
      `WmBridge::IsPlayerAllowed(player)`.

- [ ] **Step 7: BridgeLab build** — add files to vcxproj/.filters,
      build `modules.vcxproj`. Expected: 0 errors.

- [ ] **Step 8: Live proof** — kill a creature as Jecia, query
      `wm_journal_counter` row incremented. Record evidence.

- [ ] **Step 9: Commit** — `feat(Core/Bridge): native journal counters`

### Task 1.3: Native threshold evaluator

- [ ] **Step 1: Define threshold config** read from existing bridge config
      (`wm_threshold_eval.h`): `{counterKey, threshold, eventType}` list.

- [ ] **Step 2: Implement `WMThresholdEval::OnCounter(charGuid, key, newValue)`**
      — if `newValue` crosses a configured threshold (and not already
      fired this character/key), emit a bridge **event**
      (`MakePlayerScopedEvent(... "wm" "threshold_crossed")`) — NOT an action.

- [ ] **Step 3: Call from `WMJournalCounter::Increment`** after the DB write.

- [ ] **Step 4: BridgeLab build + live proof** — cross a threshold, observe
      one `threshold_crossed` event row, no duplicate on next kill.

- [ ] **Step 5: Python side** — confirm existing event consumer routes
      `threshold_crossed` to the arc-decision path (Phase 5 consumes it).

- [ ] **Step 6: Commit** — `feat(Core/Bridge): native threshold evaluator`

### Task 1.4: Sync + handoff doc

- [ ] Sync BridgeLab → `native_modules/`, `diff -rq` clean.
- [ ] Update `docs/WM_PLATFORM_HANDOFF.md`: directional table contract
      (command tables vs audit tables; `wm_journal_counter` is audit).
- [ ] Commit — `docs: native bookkeeping contract`

---

## Phase 2 — Active Character Lifecycle

The entry point. A character becomes "watched": login applies a WM
attention aura, logout strips it. The aura is the gate for all WM activity
on that character (consistent with the no-aura-no-effect principle).

**Files:**
- SQL: `pending_db_wm/` → `wm_active_character` (command table, Python→C++)
- Create: `native_modules/mod-wm-bridge/src/wm_active_character.{h,cpp}`
- Modify: `wm_bridge_player_script.cpp` (OnLogin / OnLogout hooks)
- Create: `src/wm/lifecycle/activation.py` (Python: mark character active)
- Tests: `tests/test_character_activation.py`

### Tasks
- [ ] **2.1** `wm_active_character` table: `character_guid PK, activated_by,
      attention_spell_id, state ENUM('active','inactive'), activated_at`.
      Command table — Python writes intent, C++ reads on login.
- [ ] **2.2** Python `activate_character(guid)` / `deactivate_character(guid)`
      — TDD with mem-db stub; writes/updates `wm_active_character`.
- [ ] **2.3** Native `WMActiveCharacter::OnLogin(Player*)` — if row state
      `active`, `player->AddAura(attentionSpellId)` + register in
      `WMEffectRegistry` (permanent until logout).
- [ ] **2.4** Native `OnLogout` — strip attention aura, `Unregister`.
- [ ] **2.5** Gate Phase 1 counters on attention aura present — extend
      `IsPlayerAllowed` or add `HasAttentionAura(player)` check so the WM
      only counts/evaluates for watched characters.
- [ ] **2.6** BridgeLab build + live proof: activate Jecia via Python,
      relog, confirm attention aura applied; deactivate, relog, aura gone.
- [ ] **2.7** Commit — `feat(Core/Bridge): active character lifecycle`

---

## Phase 3 — Ability Taxonomy & Schema

The differentiated-ability layer the vision emphasizes. A formal ability
record + validator so the LLM can propose abilities that bind to the
shell-bank and execute through existing native runtime behaviors.

**Taxonomy axes (the ability record schema):**
- `activation_mode`: passive | active | stance | autocast | triggered
- `target_geometry`: self | single | self_aoe | target_aoe | cone | chain
- `allegiance_filter`: friendly | hostile | any | self_only
- `effect_domain`: combat | movement | stats | reaction | summon | sense |
  economy | narrative | environment | transformation
- `delivery`: instant | projectile | aura | ground | leap
- `persistence`: instant | duration | permanent | until_dispelled
- `aura_binding`: shell-bank spell id (required for any duration/permanent)

**Files:**
- Create: `src/wm/abilities/schema.py` (AbilitySpec dataclass + axes enums)
- Create: `src/wm/abilities/validator.py` (LLM proposal → AbilitySpec | reject)
- Modify: `src/wm/abilities/models.py` (link AbilitySpec → EffectApplyRequest)
- Reference: `native_modules/mod-wm-spells/src/wm_spell_runtime.h`
  (existing Maintain/Tick/Forget behaviors are the executable vocabulary)
- Tests: `tests/test_ability_schema.py`, `tests/test_ability_validator.py`

### Tasks
- [ ] **3.1** `AbilitySpec` dataclass with all six axes + `aura_binding`;
      enums for each axis. TDD: construct/validate/serialize round-trip.
- [ ] **3.2** Validator rules (TDD, one test per rule):
      - duration/permanent persistence ⇒ `aura_binding` required (reject if absent)
      - `effect_domain` must map to an existing native runtime behavior
        (enumerate the `wm_spell_runtime.h` behavior catalog as allowed set)
      - shell-bank id must be in the 946xxx WM-owned range
      - reject any spec whose effect would tick without an aura
- [ ] **3.3** `AbilitySpec → EffectApplyRequest` adapter — a validated
      ability produces the exact `EffectApplyRequest` the existing
      `ActiveEffectTracker` + `WMEffectRegistry` already enforce.
- [ ] **3.4** LLM proposal entrypoint: prompt template +
      `propose_ability(context) → AbilitySpec` going through the validator;
      `WM_LLM_DIRECT_APPLY=0` keeps it audit-only (no live apply).
- [ ] **3.5** Full pytest green; commit — `feat(abilities): taxonomy schema + validator`

> No native build in this phase — the executable vocabulary already exists
> in `wm_spell_runtime.h`. This phase makes the LLM author *within* it.

---

## Phase 4 — World Authoring Runtime

Makes WM-generated objects/NPCs interactive. GameObject spawn and
gossip/NPC override are the missing native action kinds
(`gameobject_spawn/despawn/set_state`, `gossip_override_set` — currently
`implemented=False` in `action_kinds.py`).

**Files:**
- Modify: `native_modules/mod-wm-bridge/src/wm_bridge_environment_actions.cpp`
  (GO spawn/despawn/state)
- Modify: `native_modules/mod-wm-bridge/src/wm_bridge_gossip_actions.cpp`
  (runtime gossip override)
- Modify: `src/wm/sources/native_bridge/action_kinds.py` (flip `implemented`)
- Tests: `tests/test_action_kinds_gameobject.py` (payload validators)

### Tasks
- [ ] **4.1** GO spawn payload validator (Python TDD): entry, position,
      map, duration, spawn-as-temp vs persistent; rejects malformed.
- [ ] **4.2** Native `ExecuteGameObjectSpawn` — temp summon GO via
      existing action-bus dispatch (extends bus, no new runner — ADR-0002).
- [ ] **4.3** Native `ExecuteGameObjectDespawn` / `SetState`.
- [ ] **4.4** Native runtime gossip override — bind a generated gossip
      menu to a (WM-owned) NPC for the active character only.
- [ ] **4.5** Flip `implemented=True` for the four action kinds; integration
      test that the action round-trips through the bus.
- [ ] **4.6** BridgeLab build + live proof: WM spawns an interactive object
      near Jecia; gossip override responds. Record evidence.
- [ ] **4.7** Commit — `feat(Core/Bridge): GO spawn + gossip override runtime`

---

## Phase 5 — Decision Engine & Steering

Ties the loop: native events (Phase 1 thresholds) → journal context →
LLM arc decision → authored content (Phases 3,4) → player steers via chat.

**Files:**
- Create: `src/wm/decision/engine.py` (event → journal → arc-state machine)
- Create: `src/wm/decision/steering.py` (chat utterance → arc adjustment)
- Modify: existing event consumer to route `threshold_crossed` → engine
- Reference: `docs/JOURNAL_LAYER_V1.md`, `docs/WM_ARC_TOOLING_V1.md`
- Tests: `tests/test_decision_engine.py`, `tests/test_steering.py`

### Tasks
- [ ] **5.1** Arc state machine (TDD): journal score + threshold event →
      arc phase transition (dormant → seeded → escalating → climax → resolved).
      Pure function, no I/O in the core; one test per transition.
- [ ] **5.2** Engine consumes `threshold_crossed` events (Phase 1 output),
      reads `wm_journal_counter` (Phase 1 read-side), pulls journal context,
      calls LLM for the arc beat (audit-only under `WM_LLM_DIRECT_APPLY=0`).
- [ ] **5.3** Arc beat → authored action sequence: quest/NPC/mob/object/item
      via the bus (Phase 4 runtime), abilities via Phase 3 validator.
- [ ] **5.4** Steering pipeline: player chat / NPC talk / item use → bridge
      event → `steering.py` maps intent to an arc-state nudge (bounded —
      cannot skip phases, only bias next beat). TDD the intent→nudge map.
- [ ] **5.5** End-to-end dry run (LLM stub): kill threshold → arc seeds →
      chat steer → next beat authored. Assert action sequence shape.
- [ ] **5.6** BridgeLab live proof: full personalized loop for Jecia —
      activate → play → threshold → arc beat spawns content → steer via
      chat → arc adapts. Record as the vision acceptance proof.
- [ ] **5.7** Commit — `feat(decision): arc engine + chat steering`

---

## Release Definition

The vision is **delivered** when, for an activated character:

1. Login applies the WM attention aura (Phase 2, proven live).
2. Native counters track play in real time, no poll lag (Phase 1, DB rows).
3. A crossed threshold fires an arc beat (Phase 5, observed).
4. The beat authors interactive content — quest + NPC + object + an
   ability bound to a shell-bank aura (Phases 3,4, in-game).
5. The player steers the arc through chat and the next beat adapts
   (Phase 5, observed).
6. Every durable effect has its aura; aura removed ⇒ effect ends
   (`WMEffectRegistry`, already enforced — regression-checked each phase).
7. Logout strips attention; WM goes quiet for that character (Phase 2).

No phase is WORKING without its live proof recorded in
`docs/LIVE_PROOF_BACKLOG.md`.

## Self-Review Notes

- Spec coverage: vision elements map to phases — activation→P2,
  watching/counters→P1, arc decision→P5, generated content→P4,
  differentiated abilities→P3, chat steering→P5, aura-bound effects→
  already landed (regression each phase).
- Type consistency: `AbilitySpec → EffectApplyRequest → WMEffectRegistry`
  is one chain reusing the existing tracker/registry contract — no new
  parallel effect model.
- ADR alignment: P4 explicitly extends the action bus (ADR-0002); P1/P2
  add passive native registries/evaluators only (ADR-0007).
- Scope check: five sequential phases, each independently shippable and
  live-provable; this is the correct decomposition of "full vision."
