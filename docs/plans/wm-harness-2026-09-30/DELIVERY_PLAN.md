Status: PARTIAL
Last reviewed: 2026-09-30
Evidence: implementation plan; no work package below is claimed complete
Doc type: plan

# Delivery Plan

## Rules For Executing This Plan

Use Path A by default. This is a sequence of bounded changes, not authorization to run every item or rewrite the repo at once. Preserve the September R1-R12 scope. Map new work to existing tickets where equivalent; do not create duplicate tracking trees.

Before implementation, identify local ownership, agree the first ticket, and record baseline plus dirty files. Do not commit the whole working tree. Tests/builds/live operations follow the user's current authorization. The acceptance scenarios below specify future gates, not checks that ran during research.

## Work Packages

| ID | Deliverable | Existing owner / starting points | Depends on | Completion evidence |
|---|---|---|---|---|
| H0 | Verify runnable baseline | Restored `control/coordinator.py`, its importers, current untracked pilots | None | Authorized full suite collects/passes from tracked checkout and repeats without temp cleanup |
| H1 | Native retry-safety inventory and first repair | Native queue, action support, inventory/player handlers | H0 | Every exposed action classified; uncertain non-repeatable effects do not blindly replay |
| H2 | Canonical durable request/effect lifecycle | `autoplay/durable_native.py`, director SQL, control audit | H1 | Unique identity, revision transitions, durable dispatch, recovery, effect-proof distinction |
| H3 | Immutable compiler preview and authorization binding | Control/release compilers, panel approval gate | H2 | Apply uses exact preview artifact; changed payload/policy/scope/expiry rejected |
| H4 | Canonical small evidence/decision contract | Context builder, proposal adapter, LM Studio client | H0; execution waits for H3 | Five outcome variants, freshness, scoped handles, bounded errors and model budget |
| H5 | Unsupported-mechanic task lifecycle | Capability registry, existing issue-tracker adapter/panel | H2,H4 | Missing mechanic creates one durable actionable task and linked waiting request |
| H6 | Universal end-to-end content proof | Existing publishers/native bridge/panel | H3,H4,H5 | Supported request becomes playable content, survives restart, records resolution; unsupported request does not fake success |
| H7 | Durable obligations, notes, shared-world consequences | Journey/memory/journal/autonomy owners | H2,H6 | Presets, pause, note revisions, coherent quest replacement, conditional cleanup |
| H8 | Local-model qualification and efficiency | LLM adapter, bounded traces, scenario runner | H4; live eligibility waits for H6/H7 gates | Measured task success, unsafe-action rejection, latency/token baseline, model-specific capability profile |
| H9 | Operator release/readiness consolidation | Panel, doctor, release/proof docs | Prior packages | One view reflects authoritative stages and exact blockers, with recovery instructions |

H4 can be developed read-only before the effect work is complete. It cannot bypass H1-H3 to turn proposals into live effects. H8's dataset design begins early; its final qualification uses the completed paths.

## H0: Exact First Task

**Outcome:** verify the restored coordinator and establish a runnable baseline without losing another agent's work.

The empty local coordinator was restored after its diff and callers were inspected; the file now matches HEAD. Check its importers and the current working tree for any related changes before making further repairs.

Deliver a narrowly scoped baseline report. Do not bundle untracked lore/durable-native experiments, DB maintenance, or framework installation. When testing is authorized, the gate is the unignored suite on tracked content, followed by a repeat run; report local-only test contributions separately. No present test count is asserted here.

## H1-H3: Correctness Before More Autonomy

Start with the demonstrated inventory receipt window. List each action's durable effect location, idempotency identity, reconciliation query, cleanup policy, and worst crash point. Disable unsafe automatic retry per action, not by breaking all existing actions indiscriminately.

Extend the pilot to distinguish `submitted`, `applied`, and proof-qualified `verified`. Carry immutable operation payloads and hashes. Bind authorization to the compiled artifact, not the model's original prose. Revalidate volatile conditions immediately before apply; stale context should produce a clear outcome, not an opportunistic content substitution.

Required failure cases: two workers; lost response after submit; crash after effect before receipt; expired scope; same key/different payload; changed preview; policy revoked before dispatch; restart with pending obligation. Native DB/in-memory crash behavior needs integration evidence, not just Python mocks.

## H4-H5: The Weak-Model Boundary

Implement one discriminated decision model in the existing model adapter. Host resolves a limited capability/target set. Remove silent execution eligibility after provider schema fallback. Bound total retries across generator, editor, SDK, and HTTP layers. Missing final output is an error.

Implement automatic development-task creation using actual compiler capability failures. The packet must contain the requested experience, checked existing capability, missing behavior, client/server work, acceptance scenarios, and deployment boundary. A task is not a reward. Returning "cannot yet do this; task created" is honest progress, not refusal to support creativity.

Optional Pydantic AI trial happens here behind the adapter. Compare identical fixtures and limits to the current client. Adopt only if it improves maintenance/correctness without changing domain semantics; otherwise retain the small existing client.

## H6: First Universal Playable Slice

Use any explicitly selected scoped test character, not a hardcoded personal arc.

1. Player asks for a nearby meaningful encounter or task.
2. WM obtains current world/character facts and applicable notes.
3. Compiler offers only feasible targets, presentation, and rewards.
4. Model proposes supported content; same release path handles automatic policy or required operator review.
5. Player receives and completes the content; the actual reward and visible state match the artifact.
6. Restart mid-lifecycle and show no duplicate award or lost obligation.
7. Ask for one unsupported mechanic; show the generated development task and waiting status instead of pretending delivery.

Include at least one feasible non-quest beat so the product is not reduced to kill bounties. Include an existing supported ability only when its client manifest and runtime semantics are proven. New mechanics remain staged.

## H7-H9: Finish The Product Contract

Preserve accepted obligations when changing presets or restarting. Demonstrate a world change that removes/replaces a quest target with a coherent continuation, not a blanket prohibition on spawn changes. Reconciliation must protect other players and later legitimate state.

Qualify the local model by task category, not one aggregate score. Make the panel show pending promises, evidence age, current policy, model capability profile, uncertain effects, development tasks, and client readiness. Avoid a second dashboard with conflicting statuses.

## Migration And Rollback

- Introduce schema migrations additively. Inventory existing pending files/DB rows before importing them.
- Give each migrated request a provenance ID and one authoritative owner. Do not replay historical requests as new work.
- Shadow the new decision path without effects first; compare outputs on the same evidence snapshots.
- Switch a selected scope/capability to the new writer; disable the legacy writer for that same scope.
- Roll back routing only after draining or reconciling pending new effects. Keep their ledger, IDs, and obligations readable.
- Retain immutable artifacts and native receipts across code rollback. Never recycle published/retired visible IDs.
- For client/native releases, record exact payload/build compatibility and staged rollout requirements separately from Python rollback.

## Requirement Traceability

| Prior requirement | Harness delivery |
|---|---|
| R1 Fresh perception | H4 evidence age/coverage and native reconciliation |
| R2 Personal memory | H7 scoped notes and evidence-backed memory |
| R3 Real experiences | H6 player-visible content and non-quest beat |
| R4 Player agency | H4 clarification; H7 presets/declines/notes |
| R5 Durable arcs/obligations | H2,H7 persistent commitments and continuations |
| R6 Mechanically real powers | H3 capability/compiler checks; H5 missing-mechanic tasks; H6 proof |
| R7 Feasibility and editorial review | H3,H4 deterministic checks and bounded editorial rubric |
| R8 Distinct proof levels | H2,H9 receipts versus visibility versus behavior |
| R9 Shared-world continuity | H7 cause, affected parties, replacement/restoration |
| R10 Restart/retry correctness | H1,H2 crash handling and ownership-aware compensation |
| R11 Runtime without coding agent | H6-H8 independent supported operation |
| R12 One operator surface | H9 canonical session timeline |

## Clean-Sheet Experiment, If Chosen

Do not implement all of Path B before comparing it. Build a non-live prototype of the same request -> preview -> authorization -> simulated effect -> reconciliation path with one persisted obligation. Use the same crash cases and small model contract. Compare code ownership, operational steps, and time to diagnose a failure against Path A. A new API framework alone is not evidence that replacement is worthwhile.

No calendar estimate is asserted. H1-H3 involve native/persistence semantics and carry the highest uncertainty; content proof depends on available client/server lab state. Estimate after H0 and the action inventory, not from document length.
