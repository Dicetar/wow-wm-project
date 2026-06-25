# WM Recovery Handoff

Status: ACTIVE RECOVERY HANDOFF
Created: 2026-06-19 (recovery/planning session)
Repository: `D:\WOW\wm-project` (git, branch `main`)
Predecessor: `docs/PROJECT_ROADMAP_2026_06_11.md` + `docs/NEXT_SESSION_HANDOFF_2026_06_08.md`

> **This is the entry document for a code-recovery / project-finishing effort.**
> It supersedes the prose status claims of older handoffs only where it
> explicitly says so. For operational truth, prefer this file + the commands
> in §6. For product direction, prefer `docs/PROJECT_ROADMAP_2026_06_11.md`.

---

## 0. Read this first (60-second orientation)

WM (World Master) is a **mature, ~85%-built** external-first intelligence
platform for an AzerothCore WoW 3.3.5a private server. It is **not** an
early-stage project and must not be treated as one. A previous session did a
full recovery analysis, then executed Phase 0 (tree stabilization) and the
first slice of Phase 4 (contract gap closure). The remaining work is:

- **Headless work completed:** Phase 2 (replay harness), Phase 4 (contract
  consolidation), and Phase 8 (autoplay decomposition).
- **Operator-gated (needs a human at the WoW client + running server):**
  Phase 1 (live-proof loop) and Phase 5 (bounty full-loop + ADR-0004).

The single biggest risk to this project is **not missing engineering — it is
status inflation** (claiming a feature works because tests pass when it has
never been proven in-client) and **scope drift** (a fresh model "helpfully"
rewriting architecture that is already correct). §7 exists specifically to
prevent both.

### 0.1 Execution update (2026-06-21/22)

- **Phase 0:** complete. The handoff rename and Phase 2 implementation were
  committed separately; the working tree returned clean.
- **Phase 0e:** complete. BridgeLab rebuilt with 0 errors (one existing
  duplicate-loader warning), staged successfully, and native request `1139`
  returned `{"message":"pong","ok":true}` for player 5406.
- **Phase 1:** partial. Runtime startup, chat action, memory, and scene packets
  passed in one live service window. Ambient remains `manual_required`: no
  notable native event occurred after the latest autoplay `started_at`, and
  policy correctly rejected attempts to force quest mutation. Do not promote
  the full loop until a fresh area entry/quest completion produces one
  successful ambient narration and cooldown evidence.
- **Phase 2:** complete at repo level. `python -m wm.proofs replay <file>` uses
  deterministic LM/coordinator fakes while exercising the real intent compiler
  and control validator. The example scores 1.0 for responsiveness, safety,
  memory reuse, action correctness, and non-spam. Concurrent autoplay state
  writes now use unique temporary files with Windows retry handling.
- **Phase 4:** complete. Contract reporting now separates five debug/freeform
  kinds from 31 forward-declared product kinds; real implemented contract gaps
  remain zero.
- **Phase 8:** complete. `_chat_text.py`, `_chat_context.py`, `_compact.py`,
  `_publish_payloads.py`, `_runtime_plan.py`, `_runtime_status.py`, and
  `_scene_helpers.py` now hold the extracted helpers. `service.py` is 2367
  lines (down from 3218), with compatibility imports preserving callers.
- **Launcher reliability:** BridgeLab MySQL startup now polls `mysqladmin ping`
  instead of assuming a fixed five-second startup. The all-in-one launcher also
  waits for world port 8095 and SOAP port 7879 before starting watchers or
  reporting success. A clean stack started with runtime proof
  `proof-20260622141938712548`, and native request `1169` returned `pong`.
- **Launcher target safety (2026-06-23):** BridgeLab deploy/configure helpers
  no longer default `WmBridge`/`WmSpells` allowlists to fixture GUIDs. The
  all-in-one launcher starts core services without a watcher by default; watcher
  modes require an explicit `-PlayerGuid` resolved from the latest online
  `946602` marker. Deploy refuses to run unless bridge scope is explicit (`*`
  only for discovery, or the resolved marker GUID for proof).
- **Current live blocker:** no online character has supplied a fresh `946602`
  marker event. Resolve the newest online marker candidate before scoping
  watcher/autoplay or running live proofs.
- **Launcher milestone gate:** `1218 passed, 31 warnings`; status, skill, and
  native contract validation all passed at that point.
- **2026-06-23 marker/living milestone:** proof execution now resolves the
  marker-selected WM Session, rejects conflicting GUIDs, and records marker
  provenance. The living catalog distinguishes executor readiness from
  gameplay proof. `living.run` is a dry-run-first, job-confirmed command that
  accepts no fixture target, requires a fresh online `946602` marker session,
  executes typed lane actions, enforces multi-actor cleanup, and records
  scoped WM state only after successful apply. Ambient cooldown suppression
  is now journaled and required by the ambient proof packet.
- Context, memory, and native-queue panel jobs now inject the active canonical
  marker-session GUID and reject conflicting explicit GUIDs.
- **Gate after that milestone:** `1228 passed, 31 warnings`;
  status, skill, native-contract, living-catalog, and diff validation pass.
- **Duplicate `character_spell` fix (2026-06-23):** combat-proficiency
  maintenance now checks persistent `character_spell` truth before calling
  `learnSpell`, preventing duplicate `(guid, spell)` inserts such as
  `3838-202`. BridgeLab incremental native build passed with 0 warnings and
  0 errors, then deployed to BridgeLab worldserver pid `34464` with explicit
  wildcard bridge discovery scope (`WmBridge.PlayerGuidAllowList="*"`) and an
  empty spells fixture scope (`WmSpells.PlayerGuidAllowList=""`). Doctor passed
  after SOAP/world-port readiness settled.
- **Phase 5 scenario generation safety (2026-06-23):** ADR-0004 proof no
  longer relies on the static Defias/Guard Thomas marker example. Use
  `python -m wm.arcs.marker_scenario --player-guid $targetGuid --db-profile bridgelab`
  or the panel `arc.marker_scenario.generate` command to emit the Arc Factory
  scenario from the marked character's live level/faction/zone facts, then feed
  that generated JSON to `wm.arcs.factory`.
- **Conversational intent audit hardening (2026-06-24):** the Phase 3
  conversational action path now writes an `intent_audit` journal record for
  rejected, pending, declined, dry-run-failed, applied, and apply-failed intent
  outcomes. This is repo/runtime evidence only; gameplay remains gated on a
  fresh marker-selected live target.
- **Session memory controls/view hardening (2026-06-24):** memory pin/suppress/
  forget applies now require exactly one affected row after the preview lookup.
  `/api/wm/session/memory` returns active memory, source evidence, and
  content-free suppression/forget exclusions for the active marker session.
- **Living lane proof metadata (2026-06-24):** living lane execution now carries
  explicit `outcome` metadata (`success`, `failure`, `cleanup`, `suppression`,
  `revocation`) in response/state/audit records, and proof packets now accept
  suppression/revocation outcomes. Gameplay status remains `UNKNOWN` until
  success/failure/cleanup/suppression packets are captured in-client.
- **Canonical proof provenance hardening (2026-06-25):** proof packets now
  reject marker-target provenance unless it names the canonical marker spell
  `946602`, includes a bridge event id, includes a selection timestamp, and
  matches the proof player GUID.
- **Panel marker job hardening (2026-06-25):** panel command jobs that require
  the active marker target now reject stale, offline, bridge-event-less, or
  conflicting marker sessions during dry-run and re-check the active marker
  session again at apply time.
- **Panel marker bootstrap hardening (2026-06-25):** marker-based session
  bootstrap now selects only candidates with a GUID, `character_online=true`,
  exact canonical marker spell `946602`, and a positive bridge event id. Offline,
  wrong-spell, and event-less candidates are ignored instead of becoming the
  active WM Session.
- **Panel proof API hardening (2026-06-25):** `/api/wm/proofs/run` now returns
  structured `400` responses for invalid proof GUID input or incomplete
  canonical marker provenance instead of leaking proof-runner exceptions.
- **Fixture-GUID cleanup (2026-06-24):** Arc Factory operational notes and panel
  schema defaults no longer name/prefill Jecia or GUID 5406. Legacy Broug
  release/preflight/proof helpers now require an explicit `--player-guid`;
  Broug remains a fixture in tests and Broug-specific content modules only.
- **Current clean gate after latest repo hardening:** `1246 passed, 31
  warnings`; status, skill, native-contract, living-catalog, and diff validation
  pass.

Live proof records:

- runtime: `proof-20260622141938712548`
- chat action: `proof-20260621122742753010`
- memory: `proof-20260621122838667946`
- scene: `proof-20260621123611194788`
- ambient pending: `proof-20260621124240910679`

---

## 1. Verified current state (re-verify on first action)

These numbers were confirmed live at end of the recovery session. **Re-run
the commands in §6 before trusting them** — they are cheap and definitive.

| Item | Value | How to verify |
|------|-------|---------------|
| Branch | `main` | `git branch --show-current` |
| Last stabilization commit | `e57e026 docs: sync handoff...` | `git log --oneline -1` |
| Test suite | **1246 passed, 31 warnings** | `python -m pytest -q` |
| Status validation | `OK` | `python -m wm.status --validate` |
| Native contracts | **64 contracted, 0 implemented-without-contract** | `python -m wm.sources.native_bridge.contracts_cli` |
| Native action surface | 100 kinds, 60 `implemented=True`, 1:1 with C++ registry | §5 cross-check |
| Dirty tree | Re-check; milestone changes are committed phase-by-phase | `git status --porcelain` |
| Live services | **All `not_running`** (cold machine; DB/Auth/World/Watcher/Panel/Autoplay) | `python -m wm.runtime status --json` |

### 1.1 The 8 stabilization commits (Phase 0)

```
e57e026 docs: sync handoff, roadmap, runbook, feature_status to post-stabilization reality
35f63b7 feat(addon): WMBridge.lua client transport updates
13aaa4e feat(bridge-lab): native watch start/stop script updates
b770d55 feat(wm/living): catalog refinement for legend, nemesis, oath, patron
0d907fc feat(wm): proof system, autoplay, runtime status, panel, doctor, content release, spell patch
e1dca43 feat(native-spells): wm_spell runtime expansion + config
a91cda0 feat(native-bridge): enchanting stone + system consumables SQL
79a5dd8 feat(native-bridge): expand typed action surface (gameobject, companion, gossip, creature, player, quest verbs)
503e3ab docs: add June 8 WM handoff   <- previous tip, BEFORE recovery
```

These turned a 71-file dirty tree into a known baseline with **zero
regressions** (1197 passed both before and after). The committed-vs-working
drift flagged in the recovery analysis is **resolved**.

### 1.2 Known uncommitted item (finish or discard deliberately)

`control/actions/native/native_bridge_action.json` has one added entry:
`context_snapshot_request` contract (closes the last `implemented=True`
verb that had no payload contract). It is correct and tested-by-CLI but
**not yet committed**. Either:
- commit it as `feat(native-bridge): add context_snapshot_request payload contract`, or
- it will show as the sole dirty file — do not be alarmed, it is intentional.

---

## 2. What this project IS (the vision — do not drift from this)

WM is a **bounded, local, external-first World Master** for one AzerothCore
3.3.5a character. The desired end state is a GM/director that:

1. **observes** real play through native bridge facts + DB truth;
2. **remembers** durable character-specific facts (journal, not vibes);
3. **speaks and reacts** in-game through typed, audited, scoped actions;
4. **stages** small temporary scenes with cleanup;
5. **generates and publishes** managed quests/items/spells/rewards through
   reviewable gates (draft → validated → published → retired);
6. **proves** every live claim with runtime/DB/native/client evidence;
7. keeps the **LLM strictly advisory and schema-bound** — never direct mutation.

### 2.1 Non-negotiable architectural rules (never violate these)

These are load-bearing. They exist because earlier experiments failed
without them (see `docs/WORK_SUMMARY.md` "Known limitations"):

- **The LLM never writes SQL, shell, GM commands, or freeform mutation.**
  Direct apply is gated behind `WM_LLM_DIRECT_APPLY=1` and registered
  contracts only. Manual and LLM proposals share the *same* coordinator path.
- **Never reuse stock live spell IDs as WM carriers.** Stock `697`, `8092`,
  `1860`, etc. stay stock. WM uses shell banks (`940000+`, `946000+`,
  `947000+`).
- **Never mutate a published content slot casually.** Use the disposable-pool
  model (`wm.reserved.db_allocator`): grab a fresh unused ID, publish, mark dirty.
- **Mutations flow only through typed action kinds, release packets, or shell
  behaviors** — never raw SQL, never ad hoc GM, never direct LLM.
- **DB ownership boundary is strict:** AzerothCore tables = mechanical truth;
  `wm_*` tables = memory/policy/provenance/rollback. Never add custom columns
  to core AC tables.
- **A feature is not done because code exists.** Use the label ladder (§7.3).
  For gameplay-facing features the target is `LIVE_WORKING` before "complete".
- **Do not revive retired prototype transports** (combat_log scraping, hidden
  client messages, Eluna). The native bridge is the durable substrate.
- **Stop after repeated failed attempts and write down the failure mode.**
  Cap fresh-ID burn at ≤3 per proof cycle before writing the structural root cause.

---

## 3. Phase status (the roadmap, with block reasons)

Condensed from `docs/PROJECT_ROADMAP_2026_06_11.md`. Priority: P0 = critical
path, P1 = reinforces critical path, P2 = after P0/P1 green.

| Phase | Goal | Status | Block reason | Priority |
|------|------|--------|--------------|----------|
| **0** | Stabilize dirty tree | **DONE** (8 commits, 1197 green) | — | — |
| **0e** | Rebuild BridgeLab native modules | **DONE** | Native request 1139 returned `pong` | — |
| **1** | Repeatable live-proof session | **PARTIAL** | Runtime/chat/memory/scene pass; fresh ambient event still required | **P0** |
| **2** | Replay/eval harness + marker reliability | **DONE** | Offline CLI, scoring, fakes, and concurrent state-write hardening complete | — |
| **3** | Conversational action loop productization | PENDING | Depends on Phase 1 proof | P1 |
| **4** | Native contract consolidation | **DONE** | context snapshot contract and debug/product report split complete | — |
| **5** | Bounty full-loop + ADR-0004 | BLOCKED | Needs running server + client | **P0** |
| **6** | Memory/subject/context live proof | PENDING | Depends on Phase 1 | P1 |
| **7** | Living world lanes (gameplay) | PENDING | Catalog-ready, gameplay UNKNOWN | P2 |
| **8** | autoplay/service.py decomposition (2367 lines) | **DONE** | Seven helper modules extracted; full gate green | - |

**Critical path:** 0e → 1 → 5. Nothing in 2/3/4/6/7/8 should be prioritized
over getting 1 and 5 proven, *except* that 2/4/8 can be advanced headlessly
while waiting for an operator window.

---

## 4. CRITICAL environment gotchas (these cost real time — read once)

This session discovered hard tooling constraints. **Do not re-discover them.**

### 4.1 The bash tool strips backslashes from arguments
`D:\WOW\wm-project\.tmp\foo.py` becomes `D:\WOW\WOWwm-project.tmpfoo.py`
(backslashes eaten: `\w`→`w`, `\.t`→`.t`). This breaks:
- `cd /d D:\WOW\wm-project` → "too many arguments"
- Absolute paths with `\` → file-not-found
- `.venv\Scripts\python.exe` → mangled

**Fix: use FORWARD SLASHES everywhere.**
- `cd D:/WOW/wm-project` (drop the `/d` flag — bash `cd` doesn't take it)
- `python D:/WOW/wm-project/.tmp/script.py`
- `D:/WOW/wm-project/.venv/Scripts/python.exe` (if you need venv specifically)

### 4.2 The `/d` flag on `cd` is cmd-only, not bash
`cd /d D:/WOW/wm-project` fails with "too many arguments". Use plain
`cd D:/WOW/wm-project`.

### 4.3 `cmd /c "..."` wrappers swallow stdout in this harness
Do not wrap commands in `cmd /c`. Use the Bash tool directly with
forward-slash paths.

### 4.4 PowerShell one-liners with `$variables` get mangled
`powershell -NoProfile -Command "... $idx ..."` loses the `$` through the
bash→cmd bridge. **Prefer Python one-liners or temp `.py` scripts** for
anything non-trivial. Python is robust; PowerShell quoting is not.

### 4.5 The default `python` on PATH works and has the venv active
`python -m pytest`, `python -m wm.status`, `python .tmp/x.py` all work
without activating the venv explicitly. The `wm` console script also works
(`wm doctor`, `wm status`).

### 4.6 The WoW 3.3.5a client locks `patch-z.mpq`
A running client locks the MPQ. **Close the client before reinstalling a
refreshed MPQ** or the write silently fails and you debug ghosts.

### 4.7 Windows process scan is degraded on this host
`Get-CimInstance Win32_Process` returns access-denied. Runtime falls back
to limited `Get-Process`. This is expected; do not reintroduce WMIC hacks.
Python services use heartbeat markers (`watcher`/`panel`/`autoplay`) which
are reliable; `db`/`auth`/`world` still rely on name-matching (known gap).

---

## 5. Reliable working methods & skills (commands that actually work)

### 5.1 Validation gate — run before AND after every change
```bash
cd D:/WOW/wm-project
python -m pytest -q                              # target: 1228 passed
python -m wm.status --validate                   # target: OK
python scripts/validate_agent_skills.py          # target: OK
```
After native C++/SQL changes, also: `python -m wm.doctor --profile bridgelab --summary`
(target: 0 FAIL, 0 UNKNOWN, 8 checks).

### 5.2 Contract audit (the thing that catches drift fast)
```bash
cd D:/WOW/wm-project
python -m wm.sources.native_bridge.contracts_cli
# target: "implemented w/o contr.: (none, debug/freeform excluded)"
```

### 5.3 Cross-check: Python kinds ↔ C++ registrations
```python
# .tmp/_xcheck.py
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KINDS
import json
from pathlib import Path
contracts = json.loads(Path("control/actions/native/native_bridge_action.json").read_text(encoding="utf-8"))["payload_contracts"]
py_impl = {k.kind for k in NATIVE_ACTION_KINDS if k.implemented}
# every implemented kind MUST have a contract:
missing = sorted(py_impl - set(contracts))
assert not missing, f"implemented-without-contract: {missing}"
print("OK: all implemented kinds contracted")
```
Run: `python .tmp/_xcheck.py`. For C++ side, grep
`registry.Register("` across `native_modules/mod-wm-bridge/src/*.cpp`.

### 5.4 The CLI is the operator surface
`wm <area>.<command> [args]` == `python -m wm.<area>.<command>`. Run
`wm --list` for the catalog. Examples:
```bash
python -m wm.control.inspect --event-id 123 --summary
python -m wm.control.new --event-id 123 --recipe kill_burst_bounty --action quest_grant
python -m wm.control.validate --proposal <path> --summary
python -m wm.control.apply    --proposal <path> --mode dry-run --summary
python -m wm.runtime status --json
python -m wm.autoplay status --summary
python -m wm.panel summary --json
```

### 5.5 Commit style (match existing history)
Conventional commits with scope: `feat(native-bridge): ...`, `feat(wm): ...`,
`feat(wm/living): ...`, `docs: ...`. Multi-paragraph bodies OK; cite file
groups in the final paragraph. See §1.1 for the pattern.

### 5.6 When to write a temp script vs a one-liner
- **One-liner OK** if it's `python -m <module>` or a single `python -c "..."`
  with no `$` and no backslash paths.
- **Temp script** (`python .tmp/x.py`) for: multi-step logic, any regex,
  cross-file audits, JSON manipulation. Delete or leave `.tmp/_*.py` (gitignored).

---

## 6. Anti-drift rules (READ BEFORE ANY "HELPFUL" REWRITE)

This section exists because a fresh model's instinct is to "improve"
working code. **That instinct is the biggest threat to this project.**

### 6.1 Do not refactor what is already correct
- The external-first Python-brain / C++-body / MySQL-truth split is **the**
  architecture. Do not propose moving logic into C++ or into Eluna or into a
  web service.
- The control-contract-first design (`wm.control.coordinator`) is correct.
  Do not add a second action runner beside the WM action bus (ADR-0002).
- The disposable-pool ID model is correct. Do not switch to in-place mutation.
- If something looks "over-engineered," read its ADR first (`docs/adr/`).
  There are 7 ADRs and they exist because the simpler version was tried and
  failed.

### 6.2 Do not inflate status
- `REPO_WORKING` (tests pass) ≠ `LIVE_WORKING` (proven in-client).
- A proof packet must tie evidence to the latest service `started_at`. Old
  journal rows must not satisfy a fresh proof gate.
- Never mark a feature `WORKING` without in-client proof artifacts. The
  label ladder (§7.3) is the contract.

### 6.3 Do not invent payload contracts for unimplemented verbs
- Of 100 native action kinds, 36 are `impl=False` (forward-declared). They
  should NOT get payload contracts yet — a contract written without the
  C++ executor is a guess that will over-constrain the future implementation.
- Add a contract **only** when (a) the verb is `impl=True`, or (b) you are
  writing the C++ body in the same change. Verify with
  `python -m wm.sources.native_bridge.contracts_cli` that
  `implemented w/o contr.: (none)`.

### 6.4 Do not broaden scope to chase interesting features
- The roadmap is explicit: do not start a new feature lane before the
  live-proof loop (Phase 1) is repeatable.
- "Companion behavior packs," "rune systems," "nemesis generator," etc. are
  **Phase 9+** and explicitly gated behind Phases 1–6. They are idea
  catalogs, not permission.

### 6.5 Do not silently change the dirty tree policy
- Commit in coherent chunks; never squash unrelated changes.
- Run §5.1 validation after each commit.
- If you find a dirty tree you didn't make, **stabilize it (Phase 0) before
  adding anything**, exactly as was done at the start of this effort.

### 6.6 When uncertain, cite evidence, then ask
- Cite `file:line` for claims. "The contract is in
  `wm_bridge_environment_actions.cpp:176`" beats "the snapshot function."
- If a decision is genuinely the operator's (which player to scope, whether
  to rebuild now, v1 definition of done), ask — don't guess.

---

## 7. Per-phase execution instructions

### 7.1 Status label ladder (use these exactly)
`BROKEN` → `DESIGN` → `REPO_WORKING` → `BRIDGELAB_WORKING` →
`LIVE_PARTIAL` → `LIVE_WORKING` → `RELEASE_READY`.
Gameplay target = `LIVE_WORKING`. Update `data/specs/feature_status.json`
when a label moves.

### 7.2 Phase 0e — Rebuild BridgeLab native (operator, P0)
The 3 commits `79a5dd8`, `a91cda0`, `e1dca43` changed deployed C++/SQL, so
the running `worldserver.exe` is stale.
```powershell
# From D:\WOW\wm-project
.\incremental-bridge-lab.bat        # or stage-bridge-lab-runtime.bat
.\start-bridge-lab-server.bat       # restart worldserver
# verify:
python -m wm.sources.native_bridge.actions_cli submit --player-guid $targetGuid --action-kind debug_ping --idempotency-key rebuild-ping-1 --wait --summary
```
Acceptance: native `debug_ping` returns `pong`.

### 7.3 Phase 1 — Repeatable live-proof session (operator, P0)
Follow `docs/NEXT_SESSION_HANDOFF_2026_06_08.md` "Next Session Working Order":
1. Launcher: `Stop All WM` → `Start Core` only. Do not start watcher/autoplay
   before marker scoping.
2. Temporarily enable wildcard bridge observation, apply/reapply marker
   `946602`, scope the newest online candidate, then immediately set bridge
   scope to the resolved target GUID.
3. Start watcher/autoplay with the resolved marker GUID.
4. `POST /api/wm/proofs/run {"proof_kind":"runtime_startup","mode":"dry-run"}` → `passed`.
5. Prove `chat_action` (WM chat → in-game reply → autoplay journal `chat`/`deed`).
6. Prove `ambient` (one notable event → one WM line → cooldown holds).
7. Prove `memory` (durable preference → later reuse in separate prompt).
8. Prove `scene` (tiny spawn/say/despawn → `cleanup_status` recorded).
9. Save proof packet IDs + update `data/specs/feature_status.json`.

**Do not mark a feature LIVE_WORKING without the matching proof packet.**

### 7.4 Phase 4 — Contract consolidation (headless, DONE)
`context_snapshot_request` is contracted and `contracts_cli` reports the five
debug/freeform kinds separately from the 31 forward-declared product kinds.
The 31 `impl=False` kinds intentionally remain without contracts (§6.3).

### 7.5 Phase 5 — Bounty full-loop + ADR-0004 (operator, P0)
Two proofs, same clean BridgeLab window:

**Part A — Bounty full loop** (`docs/FULL_LOOP_PROOF_RUNBOOK.md` Part A):
install → trigger → complete → reward → suppress → cooldown → regrant.
Use `python -m wm.reactive.install_bounty --template-key ...` on a fresh
reserved slot. Cap: ≤3 fresh quest IDs per cycle.

**Part B — ADR-0004** (`docs/FULL_LOOP_PROOF_RUNBOOK.md` Part B):
ship **compiler output** (`wm.quests.compiler`), NOT hand-cloned SQL, to a
fresh reserved ID; accept + turn-in + reward in-client; verify reward panel.
On failure, widen the compiler's harvested-defaults in
`src/wm/quests/compiler.py` + `tests/test_arc_compiler_contract.py`, rerun.

On success: relabel `perception.bounty_full_loop` and
`content.arc_reward_factory` to gameplay `WORKING` in `feature_status.json`.

### 7.6 Phase 8 — autoplay/service.py decomposition (headless, P2)
`src/wm/autoplay/service.py` started at **3218 lines** and is currently **2367
lines**. The `AutoplayService` class
(94–1224) touches `self`/settings/state — leave it. Below it are ~70
**module-level pure functions** that are safe to extract into siblings:
- `_publish_payloads.py` (lines ~2280–2518: quest/item/spell payload builders)
- `_chat_text.py` (~2519–2655: sanitize/split/guard/fallback/commands)
- `_chat_context.py` (~2657–2783: identity/remembered-facts/digest)
- `_runtime_plan.py` (~2217–2279: work/publish/rollback/idempotency helpers)
- `_runtime_status.py` (status summary and process/player readiness helpers)
- `_compact.py` (~2150–2216, 2851+, 2954–3003: reducers + parse helpers)
- `_scene_helpers.py` (~2863–2939, 3164–3192: proposals/cleanup/risk)

**Result:** these functions form a dependency web on shared helpers
(`_stable_key`, `_int_or_none`, `_first_text`, `utc_now_iso`). The extraction
removed 851 lines from `service.py`; focused tests and the current full gate
remain green.

### 7.7 Phase 2 — Replay/eval harness (headless, P1)
Offline evaluation only — must NOT change live behavior. Add under
`src/wm/proofs/` (or `src/wm/dev/`): load recorded event stream + fake
native coordinator + fake LM Studio responder; replay through
autoplay/control; score responsiveness, safety (no uncontracted action
applied), memory reuse, action correctness, non-spam. Wire as
`python -m wm.proofs replay <recording.json>`. Add `tests/test_replay_*`.

---

## 8. Open questions for the operator (answer before final v1 decisions)

1. **Repack parity target?** README disclaims byte-for-byte parity. Is v1
   "latest-source rebuild + WM" a clean break, or must custom/repack content
   be re-ported?
2. **DB/Auth/World service-owned markers?** Remaining launcher-reliability gap.
   Acceptable for v1 to keep name-matching for those three?
3. **`wm_brain` DB ownership?** In `.env.example`, referenced little. Is it
   the future home of journal/memory (currently `acore_characters.wm_*`)?

---

## 9. Suggested agent task prompts (copy-paste-ready, each independently safe)

**First task always:**
> "Working in `D:/WOW/wm-project` (git, main). Run the §5.1 validation gate
> (`pytest -q`, `wm.status --validate`). Report the actual numbers. Then
> read `docs/RECOVERY_HANDOFF.md` §1.2 and either commit or discard the one
> uncommitted file. Do not change behavior."

**Phase 8 (decomposition):**
> "Decompose `src/wm/autoplay/service.py` (3218 lines) per §7.6. Extract
> ONLY the pure module-level functions into the named sibling modules; leave
> the `AutoplayService` class in place. Trace shared helpers before each
> extraction. Run `tests/test_autoplay*.py` + full `pytest -q` after each
> extraction. Stop and report if any test regresses. Commit each extraction
> separately with `refactor(autoplay): extract <module>`."

**Phase 5 (live, operator):**
> "Follow `docs/FULL_LOOP_PROOF_RUNBOOK.md` Part A then Part B on a clean
> BridgeLab window (MySQL 33307). Cap fresh-ID burn at ≤3/cycle. Capture
> native request IDs, WM event IDs, DB state at each step. On any failure,
> record the first-failing-phase evidence and STOP. Update
> `data/specs/feature_status.json` for `perception.bounty_full_loop` and
> `content.arc_reward_factory`."

---

## 10. Definition of a successful recovery

The recovery is **done** when:
- [x] Tree is stable and committed (Phase 0 — DONE)
- [x] BridgeLab native rebuilt and `debug_ping` → `pong` (Phase 0e)
- [ ] Phase 1 six-proof loop repeatable from a cold launcher start
- [ ] Bounty full-loop closed in one clean window (Phase 5 Part A)
- [ ] One compiler-generated quest accepted/turned-in/rewarded in-client (ADR-0004)
- [ ] `feature_status.json` gameplay statuses reflect the above proofs
- [x] `autoplay/service.py` under ~2400 lines with tests still green (Phase 8)

Until the first three unchecked boxes are real, **broad feature expansion
stays paused**. This is the project's own discipline, and it is correct.
