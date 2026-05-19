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

| Sub | Debt item | Priority | Risk control | Status |
|-----|-----------|----------|--------------|--------|
| 0A | E — native tests | 18 | enables all the rest | ✅ DONE (commit 615333b, 1f6ea19) |
| 0B | B — JSON dup | 32 | smallest surface, char-tests | ✅ DONE (commit 1c2ba9c) |
| 0C | C — string dispatch | 24 | table behind same entry point | ✅ DONE (commit 66605bb) |
| 0D | A — action_queue monolith | 27 | move into existing stub files | ✅ DONE (commits 1b54bdf + bundled 0D.2–0D.4) |
| 0E | D — spell_runtime monolith | 7 | hardest; harness + playbook ready | ⏳ NOT STARTED |

> **Session checkpoint 2026-05-19:** 0A/0B/0C complete, each
> standalone-tested + real-engine-built + in-engine live-proven +
> committed. Resume note for 0D/0E below ("Resume State").

---

## Sub-Phase 0A — Native Test Harness

> **Decision (2026-05-19, user gate):** BridgeLab is `BUILD_TESTING=OFF`;
> AzerothCore's GoogleTest is FetchContent-downloaded only when testing is
> configured on, and the core `unit_tests` target links the full `game`
> library + `modules` (heavy reconfigure). Phase 0's characterization
> scope (effect registry, JSON, dispatch) is **engine-independent by
> design**. Chosen approach: **(a) standalone zero-dependency micro-harness
> now** — a ~60-line `wm_test.h` exposing gtest-compatible `TEST` /
> `EXPECT_EQ` / `EXPECT_TRUE` / `EXPECT_FALSE` macros, compiled into a
> tiny `wm_unit_tests.exe` with only the engine-independent WM TUs, no
> network, no reconfigure, sub-second build — **and (b) a tracked
> follow-up** (`Task 0A.3`) to port these cases onto the core
> `unit_tests` GoogleTest target during the first phase that needs
> engine-coupled (`Player*`/`Unit*`) tests (vision Phase 2). The macros
> mirror the gtest API, so (b) is a mechanical include-swap.

**Files:**
- Create: `native_modules/mod-wm-bridge/test/wm_test.h` (micro-harness)
- Create: `native_modules/mod-wm-bridge/test/test_main.cpp` (runner)
- Create: `native_modules/mod-wm-bridge/test/test_wm_effect_registry.cpp`
- Create: `native_modules/mod-wm-bridge/test/test_wm_json.cpp` (stub now,
  filled in 0B)
- Create: `native_modules/mod-wm-bridge/test/build_standalone.ps1`
  (MSVC cl.exe direct compile — no CMake reconfigure)
- Mirror all into BridgeLab.
- Reference: `src/azerothcore/src/test/CMakeLists.txt` (the core pattern
  Task 0A.3 will later target via `ACORE_MODULE_TEST_SOURCES`).

### Task 0A.1: Standalone micro-harness + smoke test

- [x] **Step 1: Confirm the core harness reality** (done — BUILD_TESTING
      OFF, gtest is FetchContent, core target links full game lib).

- [ ] **Step 2: Write `wm_test.h`** — gtest-compatible macros: `TEST(s,n)`
      registering into a static vector; `EXPECT_EQ/NE/TRUE/FALSE` recording
      failures with file:line; no exceptions, no deps. `test_main.cpp`
      runs all, prints `[PASS]/[FAIL]`, returns failure count.

- [ ] **Step 3: Write the failing smoke test**

`test/test_wm_effect_registry.cpp`:

```cpp
#include "wm_test.h"
#include "wm_effect_registry.h"
using WmBridge::WMEffectRegistry;

TEST(WMEffectRegistry, IsActiveFalseWhenUnregistered) {
    auto& r = WMEffectRegistry::Instance();
    EXPECT_FALSE(r.IsActive(/*guid*/9990001, /*player*/true, /*spell*/946001));
}
```

- [ ] **Step 4: `build_standalone.ps1`** — invoke `cl.exe` directly:
      compile `wm_effect_registry.cpp` + test TUs + `test_main.cpp`,
      `/std:c++17 /EHsc`, link to `wm_unit_tests.exe`. No CMake.

- [ ] **Step 5: Build + run.** Expected: 1 test, `[PASS]`, exit 0.

- [ ] **Step 6: Commit** — `test(Core/Bridge): standalone native test harness`

### Task 0A.2: Characterize WMEffectRegistry fully

- [ ] Port the 24 `ActiveEffectTracker` contract cases that are
      engine-independent (register/unregister/is-active/expire/permanent
      vs timed/player-vs-creature key isolation) into the micro-harness.
- [ ] Build + run. Expected: all green. This is the regression net for
      any future registry change.
- [ ] **Commit** — `test(Core/Bridge): WMEffectRegistry characterization`

### Task 0A.3: (TRACKED FOLLOW-UP, not Phase 0) Port to core gtest

> Deferred to the first phase that needs engine-coupled tests
> (vision Phase 2 — character lifecycle touches `Player*` login/logout).
> Not executed during Phase 0.

- [ ] Reconfigure BridgeLab with `-DBUILD_TESTING=ON` (regenerates
      solution; module sources auto-collected via `CollectSourceFiles`).
- [ ] Add `native_modules/mod-wm-bridge/test/CMakeLists.txt` registering
      test sources into `ACORE_MODULE_TEST_SOURCES` global property
      (the sanctioned core pattern from `src/test/CMakeLists.txt`).
- [ ] Swap `#include "wm_test.h"` → `#include <gtest/gtest.h>` in the
      test TUs (macro API is gtest-compatible — mechanical).
- [ ] Build core `unit_tests`, run via `ctest`. Expected: WM cases green
      alongside core tests. Retire the standalone harness or keep as the
      fast inner-loop (decide then).

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

> **Correction (2026-05-19, found during 0B.1):** the divergence was
> mis-stated. Exact diff after reading both `EscapeForJson`:
> (1) `common.cpp` escapes `\b`/`\f`; `action_queue.cpp` maps them to a
> space. (2) `common.cpp` iterates `unsigned char`; `action_queue.cpp`
> iterates signed `char`, so every byte ≥0x80 hits `ch < 0x20` and is
> replaced by a space — **action_queue corrupts all UTF-8 / accented
> text** (player names, item names). The correct implementation is
> `common.cpp`'s. Canonical = `common.cpp` logic. The flagged bugfix is:
> action_queue call sites stop corrupting non-ASCII and properly escape
> `\b`/`\f`.

### Task 0B.2: Extract the canonical builder

- [ ] **Step 1:** `wm_bridge_json.h/.cpp` — one `JsonWriter` (begin/end/
      append string/number/float/bool/raw) + one `EscapeForJson` using
      **`common.cpp`'s logic** (unsigned-char iteration; `\b \f \n \r \t
      \\ "` escaped; other `<0x20` → space; bytes ≥0x80 passthrough).
- [ ] **Step 2:** Update `test_wm_json.cpp` expectations for the unified
      (correct) escaping. Build + run green.
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

---

## Resume State (for the next session — 0D & 0E)

**Branch:** `main`. All Phase 0 commits are on main, pushed status: local.
Last commit `66605bb` (0C). Working tree clean except untracked
pre-existing files.

**Canonical source = `D:\WOW\wm-project\native_modules\mod-wm-bridge\`.**
BridgeLab build tree `D:\WOW\WM_BridgeLab\src\modules\mod-wm-bridge\`
is kept byte-synced; `src\azerothcore\modules` is a symlink to
`src\modules`. After every native edit: edit in BridgeLab, build,
prove, then `cp` changed files into `native_modules\`, `diff -rq`
clean, commit.

**Build/test loop (no full reconfigure needed):**
- Standalone native tests: run
  `D:\WOW\WM_BridgeLab\src\modules\mod-wm-bridge\test\build_standalone.ps1`
  (cl.exe, gtest-compatible micro-harness `wm_test.h`, ~26 cases).
  Add new engine-independent TUs/tests to its `$srcs` line.
- Real engine: MSBuild
  `D:\WOW\WM_BridgeLab\build\modules\modules.vcxproj`
  `/p:Configuration=RelWithDebInfo /p:Platform=x64 /t:Build /m:4`.
  New .cpp/.h must be added to that vcxproj **and** `.vcxproj.filters`
  (CollectSourceFiles is NOT used by the generated solution — manual).
- Relink worldserver: MSBuild
  `build\src\server\apps\worldserver.vcxproj` same flags.
- Deploy + restart (visible window, correct CWD): stop worldserver,
  `Copy-Item build\bin\RelWithDebInfo\worldserver.exe run\bin\` (exe is
  locked while running — stop first), then
  `scripts\bridge_lab\Restart-BridgeLabWorldServer.ps1`.

**Stack launch (visible terminals, user-controlled):** the user runs
`D:\WOW\wm-project\start-bridge-lab-all.bat` (PS `Start-BridgeLabAll.ps1`).
Critical: worldserver MUST run with CWD = `run\` (not `run\bin\`) or
`GetConfigPath()+"modules/"` fails to load module configs
(`Config.cpp:766`). The bat/helpers do this correctly. MySQL is
portable `deps\mysql\bin\mysqld.exe` on port 33307 (user acore/acore).
Do NOT hard-`taskkill` mysqld (data-dir risk) — use clean shutdown.

**Live-proof pattern:** insert rows into `acore_world`.`wm_bridge_action_request`
(unique IdempotencyKey, PlayerGUID 5406, Status 'pending'); native poll
(1s) processes; read `ResultJSON`. `debug_ping`/`debug_echo` need no
player online; `debug_echo` echoes payload through `EscapeForJson` (UTF-8
round-trip = JSON-fix regression check). Use
`--default-character-set=utf8mb4`.

**0D — now LOW RISK (0C made it mechanical):**
All 26 handlers are uniform `bool ExecuteX(uint64,uint32,std::string
const&,std::string const&)` in `wm_bridge_action_queue.cpp`'s anon
namespace, registered in `GetActionRegistry()` (lambda-initialized
static). Plan: per domain, move its handlers + their private helpers
into the pre-existing empty stub file
(`wm_bridge_player_actions.cpp`, `_creature_actions.cpp`,
`_quest_actions.cpp`, `_inventory_actions.cpp`,
`_environment_actions.cpp`, `_debug_actions.cpp`; gossip stays empty
until vision P4). Shared infra (CompleteAction, ResolveScopedOnlinePlayer,
ResolvePowerType, OwnedCreatureRef, ActionPolicyAllows, JSON field
helpers, ExtractJson*) → new `wm_bridge_action_support.{h,cpp}`.
Registration: because handlers are anon-namespace (internal linkage),
each domain file exposes a `void RegisterWmBridge<Domain>Actions(
WmBridge::ActionRegistry&)` called from a bootstrap in
`wm_bridge_action_queue.cpp` (which keeps poll/claim/dispatch +
`GetActionRegistry`). Build each domain move, standalone+modules build,
relink, live-proof one action of that domain, commit per domain.
Target: `wm_bridge_action_queue.cpp` < ~400 lines. Wire any new
loader-registered scripts into `mod_wm_bridge_loader.cpp` only if a
domain needs a ScriptObject (most don't — they're plain functions).

**0E — HIGHEST RISK, has a user-decision gate:**
`native_modules\mod-wm-spells\src\wm_spell_runtime.cpp` = 8,381 lines:
forward `namespace WmSpells` (39–42), one giant anon namespace
(44–5740) holding ~27 `g*ByPlayer` mutable state maps + all private
helpers, then public `namespace WmSpells` defs (5742–8381). Header
`wm_spell_runtime.h` is the clean seam (callers
`wm_spell_*_scripts.cpp` only see it). Families: Bonebound/Alpha/Priest
Echo, IntellectBlock/Proficiency, BrougGuard, BrougLightness,
BrougEmptyCourt, Broug abilities (Skirmisher/Deflect/CloudStep/
QiReversal/SilentMeridian/KillingIntentDomain/Predator/Vitality/
UniversalParry), NightWatchersLens, LanathelStance.
**Task 0E.2 STOP GATE:** build `docs\SPELL_RUNTIME_SPLIT_MAP.md`
mapping every `g*ByPlayer` map + anon helper to its owning family or
SHARED. If ANY state map is read/written by ≥2 families, STOP and ask
the user — that cross-coupling changes the split boundary. Do not
proceed past 0E.2 without that map reviewed. Then extract
`wm_spell_internal.{h,cpp}` (SHARED only), move families
smallest-first one-commit-each, characterize pure logic first
(0E.1, same standalone harness), re-prove the spell live-proof
backlog items (Broug Empty Court V2, Lightness Assassin V1, Echo
Restorer DPS) per family. Target runtime.cpp < ~800 lines.

**Stack state at checkpoint:** BridgeLab MySQL + authserver +
worldserver (0C binary, pid was 4388) running in visible windows under
user control. Pre-existing orthogonal issue flagged as spawned task:
corrupt InnoDB index `idx_owner_bot_event` on
`acore_playerbots.playerbots_random_bots` (DB-only repair, not code).
