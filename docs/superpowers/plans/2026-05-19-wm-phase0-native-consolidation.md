# WM Phase 0 — Native Layer Consolidation (Refactor)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. This is a **behavior-preserving
> refactor** — every sub-phase ends with a verification gate proving output
> is byte-identical to before. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Pay down the three highest-priority debt items on the vision
plan's critical path so Phases 1–5 build on clean structure: unify the
duplicated JSON layer, make action dispatch table-driven, decompose both
C++ monoliths (`wm_bridge_action_queue.cpp` 2,668 ln; `wm_spell_runtime.cpp`
8,381 ln) into the pre-existing domain/family file structure, and stand up
a native GoogleTest target so the refactor (and all later native work) is
automatically verified.

**Architecture:** Per ADR-0002 (extend the bus, no parallel runner) and
ADR-0007 (native-first in-process). This phase moves *no behavior* — it
relocates code behind unchanged seams (`wm_bridge_common.h`,
`wm_spell_runtime.h`, the action bus). The seams stay; the giant
translation units behind them are split.

**Tech Stack:** C++ modules built in BridgeLab (MSVC,
`build/AzerothCore.sln`); AzerothCore GoogleTest harness
(`src/test/`, already present); Python pytest for the bus-contract parity
tests.

**Non-negotiables (every task):**
- Behavior-preserving. No payload, JSON-shape, or game-effect change. If a
  task is tempted to "fix" behavior, STOP — that is a Phase 1+ change,
  out of scope here. File it, don't do it.
- No native poll loop / second action runner (ADR-0002/0007).
- BridgeLab is the build/test env. Player 5406 / Jecia. MySQL 127.0.0.1:33307.
- No WORKING claim without proof: GoogleTest green + DB row / in-game obs.
- Every sub-phase: build clean (0 errors), tests green, live-proof matrix
  row recorded in `docs/LIVE_PROOF_BACKLOG.md` before the next sub-phase.
- Mirror every file change BridgeLab ↔ `native_modules/`; end each
  sub-phase with `diff -rq` clean between the two trees.
- Commit per task. Conventional Commits, `Core/Bridge` or `Core/Spells` scope.

---

## Why this ordering

Verification scaffold first (0A) so the refactor is provably safe. Then
the cheapest, highest-priority win (0B, JSON dedupe, Priority 32). Then
the dispatch seam (0C) which makes the handler move (0D) mechanical. Then
the spell-runtime split (0E), the largest surface, last — it benefits from
the test harness and the proven refactor playbook from 0B–0D.

| Sub | Debt item | Priority | Risk control |
|-----|-----------|----------|--------------|
| 0A | E — native tests | 18 | enables all the rest |
| 0B | B — JSON dup | 32 | smallest surface, char-tests |
| 0C | C — string dispatch | 24 | table behind same entry point |
| 0D | A — action_queue monolith | 27 | move into existing stub files |
| 0E | D — spell_runtime monolith | 7 | hardest; harness + playbook ready |

---

## Sub-Phase 0A — Native GoogleTest Target

**Files:**
- Create: `native_modules/mod-wm-bridge/test/CMakeLists.txt`
- Create: `native_modules/mod-wm-bridge/test/test_wm_effect_registry.cpp`
- Create: `native_modules/mod-wm-bridge/test/test_wm_json.cpp` (stub now,
  filled in 0B)
- Mirror into BridgeLab; register the target in the BridgeLab solution.
- Reference: `D:/WOW/WM_BridgeLab/src/azerothcore/src/test/CMakeLists.txt`
  (existing GoogleTest pattern — `common`, `mocks`, `server` dirs).

### Task 0A.1: Wire a wm_unit_tests target

- [ ] **Step 1: Read the existing test harness pattern**

Read `src/azerothcore/src/test/CMakeLists.txt` and one existing
`test_*.cpp` to copy the GoogleTest link/registration convention.

- [ ] **Step 2: Write a failing smoke test**

`test/test_wm_effect_registry.cpp`:

```cpp
#include <gtest/gtest.h>
#include "wm_effect_registry.h"
using WmBridge::WMEffectRegistry;

TEST(WMEffectRegistry, IsActiveFalseWhenUnregistered) {
    auto& r = WMEffectRegistry::Instance();
    EXPECT_FALSE(r.IsActive(/*guid*/9990001, /*player*/true, /*spell*/946001));
}
```

- [ ] **Step 3: Add `test/CMakeLists.txt`** producing a `wm_unit_tests`
      executable linking GoogleTest + the bridge sources under test
      (effect registry needs no game engine — pure std).

- [ ] **Step 4: Register target in BridgeLab build**, configure, build.
      Run: `wm_unit_tests`. Expected: 1 test, PASS.

- [ ] **Step 5: Commit** — `test(Core/Bridge): native GoogleTest target`

### Task 0A.2: Characterize WMEffectRegistry fully

- [ ] Port the 24 `ActiveEffectTracker` contract cases that are
      engine-independent (register/unregister/is-active/expire/permanent
      vs timed/player-vs-creature key isolation) into GoogleTest.
- [ ] Build + run. Expected: all green. This is the regression net for
      any future registry change.
- [ ] **Commit** — `test(Core/Bridge): WMEffectRegistry characterization`

---

## Sub-Phase 0B — Unify the JSON Layer (Debt B, Priority 32)

Two parallel JSON APIs exist: `wm_bridge_common.cpp`
(`JsonBegin/End/AppendString/AppendNumber`) and `action_queue.cpp`
(`JsonAppendComma/StringField/NumberField/FloatField/BoolField/RawField`
+ `EscapeForJson` + 3× `ActionResultJson`). Divergent escaping is a latent
correctness bug. Collapse to one.

**Files:**
- Create: `native_modules/mod-wm-bridge/src/wm_bridge_json.{h,cpp}`
- Modify: `wm_bridge_common.cpp` (consume shared, delete dup defs)
- Modify: `wm_bridge_action_queue.cpp` (consume shared, delete local set)
- Test: `test/test_wm_json.cpp`

### Task 0B.1: Characterization tests BEFORE moving anything

- [ ] **Step 1:** In `test_wm_json.cpp`, capture current output of *both*
      APIs for a fixed input matrix (empty, unicode, quote, backslash,
      newline, control char, nested raw, float precision, negative int).
      These assertions encode **current** behavior, divergences included.
- [ ] **Step 2:** Build + run. Expected: green (documents status quo).

### Task 0B.2: Extract the canonical builder

- [ ] **Step 1:** `wm_bridge_json.h/.cpp` — one `JsonWriter` (begin/end/
      append string/number/float/bool/raw) + one `EscapeForJson`. Choose
      the **stricter** escaping (the action_queue variant escapes control
      chars; common.cpp must adopt it — this is the one allowed behavior
      *fix*, explicitly: a bug fix, call it out in the commit).
- [ ] **Step 2:** Update `test_wm_json.cpp` expectations for the unified
      (stricter) escaping. Build + run green.
- [ ] **Step 3:** Rewrite `common.cpp` JSON funcs as thin forwarders to
      `JsonWriter` (keep the `WmBridge::JsonBegin` etc. signatures —
      callers unchanged). Build.
- [ ] **Step 4:** Replace `action_queue.cpp` local JSON helpers +
      `ActionResultJson` overloads with `JsonWriter`; delete the dup
      defs. Build. Expected: 0 errors.
- [ ] **Step 5: Live-proof matrix** — exercise one action of each result
      shape (done / rejected-with-fields / failed-with-numbers /
      context-snapshot) as Jecia; capture the result JSON rows; diff
      against a pre-refactor capture. Identical except the documented
      control-char escaping fix.
- [ ] **Step 6: Commit** — `refactor(Core/Bridge): unify JSON builder
      (fixes divergent control-char escaping)`

---

## Sub-Phase 0C — Table-Driven Action Dispatch (Debt C, Priority 24)

Replace the 26-branch `if (actionKind == "literal")` chain in
`ExecuteClaimedAction` with a registry: `std::unordered_map<std::string,
ActionHandler>`. Same entry point, same policy/scoping pre-checks, same
handler bodies — only the selection mechanism changes.

**Files:**
- Create: `native_modules/mod-wm-bridge/src/wm_bridge_action_registry.{h,cpp}`
- Modify: `wm_bridge_action_queue.cpp` (`ExecuteClaimedAction` → lookup)
- Test: `test/test_wm_action_registry.cpp`

### Tasks
- [ ] **0C.1** Define `using ActionHandler = bool(*)(uint64,uint32,
      std::string const&,std::string const&);` and an `ActionRegistry`
      with `Register(kind, handler)` + `Find(kind)`. GoogleTest:
      register/find/missing-returns-null/duplicate-key-asserts.
- [ ] **0C.2** Keep all 26+ handler functions where they are *for now*;
      add a single `RegisterCoreActions()` that maps each existing
      `actionKind` string → its `Execute*` fn. One source of truth.
- [ ] **0C.3** Rewrite `ExecuteClaimedAction`: keep the
      `IsPlayerGuidAllowed` + `ActionPolicyAllows` pre-checks verbatim,
      then `auto h = registry.Find(actionKind); if (!h) reject;
      h(...)`. Delete the if-chain.
- [ ] **0C.4** Add a build-time guard test: every `NativeActionKind` with
      `implemented=True` in `action_kinds.py` has a registry entry.
      Generate the expected list, assert in GoogleTest (parity fixture).
- [ ] **0C.5** BridgeLab build + live-proof: run debug_ping, one player
      action, one creature action — identical results to pre-refactor.
- [ ] **0C.6** Commit — `refactor(Core/Bridge): table-driven action dispatch`

---

## Sub-Phase 0D — Decompose action_queue.cpp (Debt A, Priority 27)

The 8 domain stub files (`wm_bridge_player_actions.cpp` … `_debug_actions.cpp`,
3–5 lines each, compiled-but-empty) are the **pre-designed target**. Move
handlers into them; each registers itself via 0C's registry.

**Files (move targets, all already exist as stubs):**
- `wm_bridge_player_actions.cpp` ← ExecutePlayer* (7 handlers)
- `wm_bridge_creature_actions.cpp` ← ExecuteCreature* (8)
- `wm_bridge_quest_actions.cpp` ← ExecuteQuest* + quest event emitters
- `wm_bridge_inventory_actions.cpp` ← AddItem/RemoveItem/RandomEnchant
- `wm_bridge_environment_actions.cpp` ← context snapshot, display id
- `wm_bridge_gossip_actions.cpp` ← (empty now; populated in vision P4)
- `wm_bridge_debug_actions.cpp` ← debug_ping/echo/fail
- Shared infra → `wm_bridge_action_support.{h,cpp}` (CompleteAction,
  ResolveScopedOnlinePlayer, ResolvePowerType, OwnedCreatureRef, policy)
- `wm_bridge_action_queue.cpp` shrinks to: poll → claim → registry dispatch

### Tasks (one commit per domain file — independent, low blast radius)
- [ ] **0D.1** Extract shared infra to `wm_bridge_action_support.{h,cpp}`;
      both monolith and future domain files include it. Build green.
- [ ] **0D.2** Move ExecutePlayer* → `wm_bridge_player_actions.cpp`, add
      `AddSC`-style `RegisterWmBridgePlayerActions()` called from registry
      bootstrap. Wire into `mod_wm_bridge_loader.cpp`. Build + the 0C
      parity test stays green. Live-proof one player action.
- [ ] **0D.3** Repeat for creature, quest, inventory, environment, debug
      (one task + commit each; parity test green after each).
- [ ] **0D.4** `action_queue.cpp` now only owns poll/claim/dispatch +
      `PollActionQueue`. Confirm < 400 lines. Build clean.
- [ ] **0D.5** Full live-proof matrix: ≥1 action per domain as Jecia,
      result rows diffed against pre-0D capture — identical.
- [ ] **0D.6** `diff -rq` BridgeLab ↔ native_modules clean. Update
      `docs/WM_PLATFORM_HANDOFF.md` (new file map).

---

## Sub-Phase 0E — Decompose wm_spell_runtime.cpp (Debt D)

8,381 ln = a 5,696-ln anonymous namespace (lines 44–5740, ~27 per-family
mutable state maps + helpers) + 2,639 ln of public `WmSpells::` defs
(5742–8381). `wm_spell_runtime.h` is already a clean seam — callers
(`wm_spell_*_scripts.cpp`) only see the header, so this is invisible to
them if signatures are untouched.

**Hard part:** the shared anonymous namespace. Strategy: lift cross-family
shared helpers/types into `wm_spell_internal.h`; give each family
ownership of *its* state maps (verified single-family access) inside its
own TU.

**Target files (each includes `wm_spell_runtime.h` + `wm_spell_internal.h`):**
- `wm_spell_runtime.cpp` → config, IsPlayerAllowed, CheckShellCast,
  ExecuteShellBehavior (the dispatcher), PollDebugRequests, LoadBehaviorRecord
- `wm_spell_internal.{h,cpp}` → shared: config accessors, counter helpers,
  shared runtime-state structs, common math
- `wm_spell_bonebound.cpp` → Bonebound + Alpha/Priest Echo + companions
  (largest family: bleed/cleave/echo state, ~12 maps)
- `wm_spell_proficiency.cpp` → IntellectBlock + CombatProficiencies
- `wm_spell_broug_guard.cpp`
- `wm_spell_broug_lightness.cpp`
- `wm_spell_broug_empty_court.cpp`
- `wm_spell_broug_abilities.cpp` → Skirmisher/Deflect/CloudStep/QiReversal
  /SilentMeridian/KillingIntentDomain/Predator/Vitality/UniversalParry
- `wm_spell_night_watchers_lens.cpp`
- `wm_spell_lanathel_stance.cpp`

### Tasks
- [ ] **0E.1 Characterization first.** GoogleTest the engine-independent
      pure logic: config parsing, scale/damage/health formulas
      (Bonebound stat math), JSON status builders, counter-key derivation.
      These are the regression net. Build the `wm_spell_unit_tests`
      target (same pattern as 0A). Green = status quo captured.
- [ ] **0E.2 Build the dependency map.** For each of the 27 `g*ByPlayer`
      maps and each anon helper, grep which public functions touch it.
      Produce `docs/SPELL_RUNTIME_SPLIT_MAP.md`: map → owning family, or
      SHARED (→ `wm_spell_internal`). **Stop and review with user if any
      map is touched by ≥2 families** (cross-family coupling changes the
      split boundary).
- [ ] **0E.3 Extract `wm_spell_internal.{h,cpp}`** — only the SHARED set
      from 0E.2. Monolith includes it, still compiles & links. Build +
      0E.1 tests green + live-proof: cast one shell spell, summon
      Bonebound — unchanged.
- [ ] **0E.4 Move one family per task** (order: smallest first —
      Lanathel, NightWatchersLens, Proficiency, then Broug Guard /
      Lightness / EmptyCourt / abilities, Bonebound last). Per family:
      move its defs + its owned state maps + family-private helpers to
      `wm_spell_<family>.cpp`; add to vcxproj/.filters; build; 0E.1
      tests green; **live-proof that family's signature behavior**
      (e.g. EmptyCourt: Broug Empty Court V2 proof; Bonebound: summon +
      bleed + echo proc). One commit per family.
- [ ] **0E.5** `wm_spell_runtime.cpp` now only the dispatcher + config.
      Confirm < 800 ln. Full regression: the live-proof backlog items
      that touch spells (Broug Empty Court V2, Lightness Assassin V1,
      Echo Restorer DPS) all re-proved green.
- [ ] **0E.6** `diff -rq` clean. Update handoff doc + ADR-0007 action
      item note (spell split done, was deferred from vision P3).

---

## Release Definition (Phase 0 done when)

1. `wm_unit_tests` + `wm_spell_unit_tests` exist, green, in BridgeLab.
2. One JSON builder; zero duplicate JSON/escaping defs (grep proof).
3. Action dispatch is table-driven; parity test asserts registry ⊇
   implemented `NativeActionKind`s.
4. `wm_bridge_action_queue.cpp` < 400 ln; handlers live in domain files.
5. `wm_spell_runtime.cpp` < 800 ln; families in `wm_spell_<family>.cpp`.
6. Live-proof matrix recorded: ≥1 action per bridge domain + every
   spell-family signature behavior, byte-identical to pre-refactor
   (except the one documented JSON escaping bugfix).
7. `diff -rq` BridgeLab ↔ native_modules clean.

Then Phase 1 of the vision plan resumes — now adding handlers as
*files + a registry line*, not branches in a monolith, with a native
test harness it inherits for free.

## Self-Review Notes

- Behavior-preserving except one explicitly-flagged JSON escaping bugfix
  (0B.2) — called out in its commit, not silently bundled.
- Each sub-phase is independently shippable and live-provable; 0D/0E
  tasks are one-commit-per-file for minimal blast radius.
- 0E.2 has a hard STOP gate: cross-family state coupling invalidates the
  split boundary and needs a human decision before proceeding.
- Seams (`wm_bridge_common.h`, `wm_spell_runtime.h`, action bus) are
  unchanged — `wm_spell_*_scripts.cpp` and Python bus contract untouched,
  so the existing 817-test Python suite + live backlog are the outer net.
- ADR-0002/0007 honored: no new runner; the registry is passive lookup
  behind the existing single dispatch entry point.
