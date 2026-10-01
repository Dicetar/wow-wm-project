Status: PARTIAL
Last reviewed: 2026-09-30
Evidence: direct file inspection, not execution
Doc type: research / source assessment

# Current System And Gaps

## Inspection Boundary

Inspected local source, current-state routers, September plans, and selected native execution paths. Local `main` reports 57 commits ahead of its remote-tracking branch and has substantial modified/untracked work. No fetch was performed, so that is local tracking information, not a fresh remote audit. No files were reset, staged, committed, or pushed.

The May and September test counts in older documents are historical. Neither those counts nor the presence of a skill prove today's working tree is healthy. Native handler findings below are source-level failure windows, not reproduced incidents.

## Useful Assets To Preserve

| Existing area | Evidence / responsibility | Consequence |
|---|---|---|
| Python/Pydantic core | `pyproject.toml`: Python >=3.11, Pydantic 2.x, PyMySQL | No language rewrite needed for typed contracts |
| Action catalog | `src/wm/control/registry.py`: registry, policies, recipes, hashes | Extend this authority instead of a parallel tool registry |
| Native bus | `native_modules/mod-wm-bridge/src/wm_bridge_action_queue.cpp`: player scope and policy before registry dispatch | Correct location for a second enforcement boundary |
| Native spell module | `native_modules/mod-wm-spells/src/` | Combat mechanics stay server-side; not model round trips |
| Structured generation | `src/wm/llm/lmstudio.py`: schema response mode, parsing, local endpoint | A useful provider adapter exists already |
| Context and memory | `src/wm/context/`, `src/wm/character/`, `src/wm/journal/` | Consolidate ownership; do not add another general memory service first |
| Autoplay and governor | `src/wm/autoplay/`, `src/wm/autonomy/` | Existing scheduling/policy surface to evolve |
| Publishing and presentation | Managed release paths, shell bank, `docs/CONTENT_REQUIRED_FIELDS.md` | Encode past content mistakes as compiler checks |
| Operator surface | `src/wm/panel/`, canonical WM Session routes documented in handoff | Keep one operator surface; improve its truth model |
| Durable pilot | `src/wm/autoplay/durable_native.py`, `sql/bootstrap/wm_director_request.sql` | A narrow transactional starting point, not universal durability |

## Priority Findings

### P0: Coordinator Source Restored; Runtime Baseline Unverified

At initial inspection, `src/wm/control/coordinator.py` was zero bytes, while `src/wm/control/__init__.py:2` and `_cli.py:8` imported `ControlCoordinator` and `scene_play.py:13` imported `ControlExecutionResult`. Its local diff consisted solely of deleting the tracked 178-line implementation. The tracked implementation was restored in place and `git diff -- src/wm/control/coordinator.py` is now empty.

Remaining action: verify imports and the runnable baseline when checks are authorized. Restoration establishes source parity, not runtime correctness.

### P1: Native Claim Recovery Can Repeat A Non-Idempotent Effect

`wm_bridge_action_queue.cpp`, `RecoverExpiredClaims`, returns expired claimed requests to pending when attempts remain. `ExecutePlayerAddItem` in `wm_bridge_inventory_actions.cpp:69` changes inventory, saves through `CharacterDatabase`, then calls `CompleteAction`. `CompleteAction` in `wm_bridge_action_support.cpp:414` records the receipt in `WorldDatabase` separately.

Inference: a failure after a durable inventory effect but before a durable completion receipt can leave an eligible request to execute again. The queue's idempotency key prevents a duplicate request row; it does not by itself prevent re-execution of that same row. The exact crash outcome depends on database/core scheduling and needs fault injection. No duplicate grant was reproduced here.

Action: classify each handler as read-only, idempotent-set, transactional entitlement, or non-repeatable. For uncertain non-repeatable effects, reconcile or park; do not automatically retry. Reward ownership must be tied to request identity where the actual durable effect is saved.

### P1: The Durable Pilot Is Deliberately Narrow

`DirectorLedger.accept` hashes proposals and rejects origin/scope mismatch. `transition` compares revision and state inside a transaction. `run_durable_native_intent` does not resubmit an unknown outcome; it looks up the native receipt and can park as `needs_operator`. These are useful controls.

Limitations: the service uses the pilot only for `world_announce_to_player` when `durable_native_intent_enabled` is true; the default is false (`service.py:116,987`). A native `done` maps to pilot `verified`, which is not general proof of client-visible delivery or intended gameplay. The pilot also does not repair native queue retries beneath it. Generalize the contract deliberately, not by renaming this one path universal.

### P1: Approval State Is Not A Durable Release Record

`src/wm/panel/approval_gate.py:55` stores pending proposals in a Python list with process-local IDs. `approve` removes the item before invoking its applier; a normal return yields `ApplyResult(ok=True)` regardless of nested result meaning. That reports invocation success, not necessarily native or gameplay success. `dry_run` and `approve` exist separately, but this class alone does not bind approval to an immutable preview hash. Other callers may impose more controls; do not claim all routes bypass preview.

Action: persist proposal revision, artifact hash, validation report, authorization scope, expiry, and execution receipts. Preserve existing outer guards while making these invariants explicit at the shared boundary.

### P2: Model Fallback Can Hide A Capability Change

`LmStudioClient.generate_json` retries HTTP 400 from schema mode using text mode. `generate_text` can extract text from `reasoning_content` after empty message content. These are real source behaviors, not theoretical provider limitations.

Action: negotiate and record provider capability before a run. Unsupported schema mode can route to an explicitly qualified draft-only mode; do not quietly downgrade execution eligibility. Missing final content should be a typed failure, not evidence that extracted reasoning is player-safe final text. Always run application semantic validation even with constrained output.

### P2: File Replacement Is Not Multi-Record Transactionality

`AutoplayStateStore.write_json` uses temporary files and replacement; seen-key collections are bounded in `state.py`. This helps individual file persistence but does not atomically bind a player obligation, proposal, policy decision, reserved content, queue request, and outcome. Bounded caches are not durable reward deduplication.

Action: use a relational ledger for authoritative lifecycles. Keep files for exports, diagnostics, and immutable artifacts, not competing authoritative status.

## What Was Not Established

- Actual current suite outcome, live server health, model identity, GPU/VRAM, latency, throughput, or cost.
- Every action handler's retry safety; the inventory example establishes a reason to audit the rest.
- Complete caller coverage of approval gates, authentication, or policy enforcement.
- Whether all untracked pilots should be adopted; that is a separate ownership/review decision.

The evidence supports targeted architectural repairs. It does not justify declaring every subsystem broken or discarding the existing integration.
