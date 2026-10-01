Status: PARTIAL
Last verified: 2026-09-14
Verified by: Codex
Doc type: assessment

# Autonomous Director Baseline

This is a dated evidence map for the release spec, not a replacement for operational handoffs. Paths below identify inspected code at local HEAD `5a0ee41eb1fd9d9bd32db1fa7e0b780adf707122`; re-check when implementing. Agreed vocabulary is in [CONTEXT](../../../CONTEXT.md).

## Verification

- `git status -sb`: main is 57 commits ahead of the locally recorded origin/main; remote refs were not fetched. Existing operational changes and untracked docs remain; see Git directly for their current contents.
- `python -m pytest -q`: **BROKEN on this host**, 1 failed, 1245 passed, 31 warnings (36.85 seconds). Failure: `tests/test_runtime_dll_guard.py::RuntimeDllGuardTests::test_guard_passes_and_fails_on_hash_mismatch`; the PowerShell child cannot resolve `Get-FileHash`. This establishes a failure, not its complete root cause.
- The ability tracker and its tests are now tracked. The older "untracked 24 tests" warning is obsolete.
- `python scripts/validate_agent_skills.py`: WORKING.
- `python -m wm.status --validate`: WORKING. This validates status consistency, not live truth.
- `python -m wm.sources.native_bridge.contracts_cli --json`: 100 declared, 64 contracted, no implemented product-contract gap. Three implemented debug kinds lack contracts intentionally; 31 product declarations remain unimplemented.
- `python -m wm.doctor --profile bridgelab --summary`: NOT READY; both DBs on 33307 and SOAP on 7879 refused connections. Config exists with wildcard discovery scope. No runtime start or live mutation performed.
- GitHub CLI was found at `.wm-tools/github-cli/bin/gh.exe`; open and closed issue listings were empty. Existing canonical ready-for-agent label is available.

## Current Code Versus Required Behavior

| Area | Evidence inspected | Assessment and next work |
| --- | --- | --- |
| Environment | `src/wm/autoplay/world_context.py`; `native_modules/mod-wm-bridge/src/wm_bridge_environment_actions.cpp` | Native presence, perception, snapshots and recent events exist. The chat location helper sets fresh from Online alone; perception compacting exposes counts and timestamps, not detailed payload. Add time/map/instance relevance checks and targeted snapshots for decisions; do not rebuild sensing wholesale. |
| Natural-language actions | `src/wm/autoplay/intent.py`, `intent_extract.py`, `tools.py`, `service.py` | Six graduated conversational verbs; broader content lane labels are not equivalent to executable chat requests. Extend typed routing for content/notes/missing mechanics. Request idempotency currently incorporates wall-clock seconds; durable origin IDs need proof across retries. |
| Memory | `src/wm/autoplay/memory_extract.py`; `src/wm/character/journey.py`, `memory.py`, `reader.py` | Durable character steering and pin/suppress/forget paths exist. Extraction explicitly excludes world instructions. Add Author's Notes ownership/scopes/revisions and planning retrieval using this foundation. |
| Initiative | `src/wm/autoplay/ambient.py`, `agenda.py`, `policy.py`, `state.py` | Event selection, cooldowns, lane budgets and pause exist. No On Demand/Moderate/Active preset match found in inspected autoplay/panel/control paths. Separate new opportunities from existing obligations. |
| Execution outcomes | `src/wm/panel/approval_gate.py`, `cross_lane.py`, `issues_queue.py`; `src/wm/autoplay/verification.py`, `_runtime_plan.py`, `state.py` | Panel pending/issues are process-local; autoplay already has durable issues/drafts/journal. Reuse durable infrastructure. Gate success means callable returned without exception; result verification primarily checks outer applied status. Lane-name rollback availability is not an operation-specific recovery proof. |
| Quest generation | `src/wm/quests/compiler.py`, `validator.py`; `src/wm/arcs/marker_scenario.py`; ADR 0004 | Compiler and schema-adaptive publishing exist. Marker selection filters zone/level/spawn count and excludes faction IDs 0/35, which is not authoritative player-relative hostility. Preserve useful count logic, add real feasibility evidence, prove shipped compiler output. |
| Spell generation | `src/wm/abilities/schema.py`, `grant_compiler.py`; `src/wm/autoplay/_runtime_plan.py`; `native_modules/mod-wm-spells/src/wm_spell_runtime.cpp` | Minimal ability schema exposes four effects; grant compiler emits learn/apply-aura steps and assumes behavior exists elsewhere. Native supported behaviors inspected are named special-purpose handlers. Autoplay ability lane unconditionally returns maintenance work. Generic composition and its release path need implementation/proof. |
| Client/server publishing | `src/wm/spells/unified_dbc_publish.py`, `shell_audit.py`, `client_patch_pending.py` | Shared materialization, audit, backup and pending client patch already exist. Staging accepts any audit status other than BROKEN; staging is not installed/deployed/visible proof. Extend deployment receipts and gate grants on actual matching readiness. |
| Shared-world changes | Existing native creature/gameobject/quest/environment action handlers; content release/rollback | Atomic verbs and rollback tools exist; no dependency-aware continuity plan found in inspected control/content/autoplay paths. Plan impact coverage, typed lifecycle and conditional recovery. Check current quest action support before assuming fail/retire semantics; prose can be stale. |
| Development requests | `src/wm/panel/issues_queue.py`; durable autoplay issues | Local issue handling exists. No automatic GitHub development-request flow found in inspected runtime paths. Add delivery/dedup/status on existing durable records. |
| Proof | `src/wm/proofs/replay.py`, `runner.py`; `tests/test_proofs.py` | Replay exercises real intent extraction/compiler/validator with fake replies and coordinator. Memory scoring uses fixture references and an in-memory set; it does not establish persistent-note retrieval or a full director lifecycle. Extend at the session boundary. |

## Important Interpretation

- Missing generic orchestration does not mean publishers, action contracts, sensing, or memory must be replaced.
- Runtime dependency outages are not evidence of a source regression. Conversely, the failing full suite cannot be reported green.
- Existing source tests and current-state claims do not prove the new product scope. The release must demonstrate content behavior and world continuity in-client.
- Shared-world authority is a new agreed requirement. Existing managed-only guards cannot simply be disabled; implement bounded, typed operations carrying dependency and recovery evidence.
- Optional firm notes are an advanced setting, not a new mandatory approval form for every request.

## Existing Test Boundaries

Prefer the public session/autoplay flow and current dependency injection. Focused prior art includes:
`tests/test_autoplay.py`, `tests/test_autoplay_state_concurrency.py`, `tests/test_character_memory.py`, `tests/test_memory_extract.py`, `tests/test_arc_marker_scenario.py`, `tests/test_quest_publish.py`, `tests/test_quest_rollback.py`, `tests/test_proofs.py`, `tests/panel/test_cross_lane_wiring.py`, `tests/test_native_payload_contract.py`, and shell/client/server DBC tests.

Required manual/live evidence is separate from these tests. Reuse the current full-loop proof runbook and canonical marker provenance; never invent a fixture target for operations.

## Planning Artifacts

The GitHub spec and tickets are the canonical work tracker after publication. Local SPEC and ticket files are dated authoring snapshots; follow README links for current issue status. This assessment contains source paths intentionally; implementation decisions in the spec and tickets refer to module responsibilities to avoid brittle file-level prescriptions.
