Status: DESIGN_ONLY
Last verified: 2026-09-24
Verified by: Codex
Doc type: adr

# ADR 0008: Durable Player Experience Director

Decision: selected for the rebuild under the user's delegated design authority; not yet implemented or live-verified.

## Context

WM already has native sensing/actions, publishers, journey state, and local-model integration. Its automatic generation drops personal context, chooses reactions by event lane, and lacks a single transactional request lifecycle across panel/autoplay/execution. A broad rewrite would discard useful capabilities without directly improving player experience.

## Decision

- Build explicit sensory, opportunity, creative/editorial, execution, and reconciliation stages inside the existing Python application. Reuse `wm.autonomy` and `wm.autoplay`; expose one compact accept/advance/inspect interface to existing callers.
- Keep synchronous mechanics and native cleanup in game hooks. Keep authored mutations on the existing action bus and publishers. This preserves ADR 0002 and the native/Python distinction discussed in ADR 0007 without declaring its unfinished tasks complete.
- Persist operation lifecycle in new WM-owned transactional tables in the existing world database, alongside control audit. Keep character progression/notes in their existing domain tables. Local JSON is a projection, not the lifecycle authority.
- Use a narrow parameterized PyMySQL ledger adapter with short transactions. Retain legacy DB clients outside that scope. A separate CLI invocation per query cannot provide a multi-operation transaction.
- Use stable input/effect identities, conditional claims, fencing, dispatch records and outcome reconciliation. No claim of exactly-once distributed execution or atomic rollback across server runtime and client assets.
- Deliver one personal arc/scene/reward/continuation loop before universal power composition or broad shared-world alteration. Those remain later release requirements, not removed product goals.

## Alternatives

A single opaque director is easy to call but risks another blocking god object. Separate microservices/workers improve isolation but impose deployment and coordination overhead without workload evidence. Choose a compact public interface with staged internals and durable work; add process isolation only if measurements justify it.

## Consequences

One runtime remains understandable and compatible with the current lab. Costs are additive schema migrations, a focused dependency, explicit contracts and concurrency/recovery testing. Model failures cannot be allowed to stall cleanup. Native receipts and client presentation remain separate proof obligations. Old/new execution must never both own the same character's effects during cutover.

The [rebuild plan](../plans/wm-redesign-2026-09-23/REBUILD_PLAN.md) defines migration, milestones and acceptance. Revisit this decision for measured model/reconciliation starvation, genuinely independent deployment needs, or a user-approved change to hosting scope, not because an agent framework is available.
