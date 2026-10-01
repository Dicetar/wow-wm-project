Status: PARTIAL
Last reviewed: 2026-09-30
Evidence: proposed design grounded in inspected code; not implemented
Doc type: design

# Two Architecture Paths

All interfaces and records below are proposals unless explicitly identified as existing. Names describe responsibilities, not new packages that must be created verbatim.

## Shared Principle: Three Different Authorities

1. **Model:** interprets natural language, identifies opportunities, proposes narrative and gameplay intent, explains ambiguity. It cannot authorize itself or declare its own effects proven.
2. **Harness:** owns scope, policy, capability catalog, content compilation, durable lifecycle, dispatch, reconciliation, and authoritative player memory.
3. **Game server:** owns actual world state, combat timing, movement validity, character operations, and native enforcement. Client installation owns presentation facts not observable solely from the server.

The development agent is outside this runtime triangle. It can implement missing mechanics through a reviewed development task; runtime WM does not gain shell/SQL access when a capability is missing.

```text
native events + player requests + due obligations + Author's Notes
    -> durable intake and evidence projection
    -> deterministic eligibility / initiative scheduling
    -> bounded model decision (or no model for deterministic work)
    -> typed beat proposal
    -> capability resolution + deterministic compiler preview
    -> editorial assessment where needed
    -> immutable release artifact + policy decision
    -> durable dispatch intent
    -> existing publishers / native bus
    -> receipts + state reconciliation + client/gameplay proof
    -> obligations, memory, world consequences, operator timeline

missing supported mechanic -> durable development task, not fake execution
```

## Path A: Evolve The Existing Repository

Keep the present packages and entry points. Consolidate behind their existing owning interfaces:

| Responsibility | Existing owner to extend | Change |
|---|---|---|
| Native event intake | `sources/native_bridge` and event spine | Evidence freshness, gaps, source identity, durable cursor |
| Context assembly | `context` plus current character/journal readers | One canonical packet, no independent competing memory truth |
| Initiative and obligations | `autoplay` / `autonomy` | Durable due work; presets do not discard obligations |
| Model boundary | `llm` | One validated decision contract; qualified provider modes |
| Policy/compiler coordination | `control` and managed release pipeline | Immutable previews and one authorization contract |
| Durable intent | Existing `DirectorLedger` pilot | Generalize only after native retry categories are defined |
| Game execution | Native registry and managed publishers | Effect identity, reconciliation, bounded cleanup |
| Operator truth | Existing panel | Persisted statuses, evidence, uncertainty, development tasks |

Do not create a new `harness` service alongside autoplay that owns the same requests. Extract smaller internal functions from the large service only as the ticket requires. Migrate one lane at a time with exactly one active writer for each scope; shadow mode may propose but cannot reserve IDs, publish, grant, or send player messages.

Keep compatibility APIs as adapters. Their output may map new statuses to older displays, but must not turn `submitted` into `verified`.

## Path B: Clean Sheet, Same Product

Choose this only for a separate prototype or an explicitly approved replacement. The question is what we would design without accidental historical coupling, not permission to delete current integration.

**Initial deployment:** one Python application package, an API process, a worker process, the existing MySQL-compatible service, a local model endpoint, and the worldserver with native modules. Workers can share code without sharing in-memory authority. No mandatory message broker, vector DB, agent swarm, or cloud account.

**Selected implementation stack:** Python/Pydantic domain models; Pydantic AI core behind `ModelPort`; SQLAlchemy Core repositories and explicit WM-only migrations; FastAPI operator/API boundary; native C++ typed adapter. Pin dependencies and keep a reproducible lock/install path during implementation. Existing game schema and native semantics remain subject to AzerothCore compatibility.

```text
wm/
  domain/        decision, obligation, effect, release, notes, consequence
  application/   intake, decide, compile, authorize, dispatch, reconcile
  ports/         model, world_read, effect_executor, release_store, ledger
  adapters/      local_model, mysql, native_bridge, publishers, operator_api
  workers/       due_work, dispatch, recovery, projection
```

These are ownership boundaries, not instructions to split every function into an interface. Domain objects do not import HTTP clients or DB connection factories. The operator API and MCP adapter call the same application operations. Native support is deliberately domain-specific; neither architecture tries to make WoW DB publishing universally generic.

### What Is Different From Path A?

- Every request is durable at intake; there is no file-backed pending authority to migrate.
- Every compiler is preview-only until an immutable manifest is authorized.
- Model SDK/API plumbing is typed from the outset instead of progressively adapted.
- Capabilities declare proof/retry/cleanup contracts before becoming visible to the model.
- The panel reads projections of authoritative state rather than retaining its own execution lifecycle.

It still needs the same client patching and native mechanics. A clean Python design cannot remove those costs. Porting existing publishers and regression scenarios is cheaper and safer than re-discovering every required game field.

## Core Records

| Record | Minimum durable fields |
|---|---|
| Evidence frame | Frame ID, player/world scope, observed-at and received-at, source cursor, fact references, freshness/coverage, client capability evidence |
| Request | Origin ID, principal, selected session scope, input reference, state/revision, created-at, deadline, causation ID |
| Decision | Decision version, evidence frame, note revisions, model/config/prompt versions, typed outcome, short reason, bounded budget usage |
| Obligation | Owner, promised outcome, accepted/active state, trigger/due condition, resolution/replacement policy, originating release |
| Release artifact | Content hash, compiler/capability version, reserved IDs, typed operations, preconditions, dependency/proof plan, compensations |
| Authorization | Artifact hash, principal/policy version, permitted scope/effects, expiry, approval or automatic-policy reason |
| Effect | Stable key, artifact step, executor/version, retry class, state/revision, lease/fence, receipt, reconciliation evidence |
| Development task | Missing capability signature, requested experience, related request IDs, acceptance scenarios, affected components, constraints, status |
| World consequence | Cause, affected entities/players/quests, ownership/revision, start/end conditions, continuation/restoration plan |

IDs are generated by the host. Model-provided references must resolve within the evidence frame and current authorized session; a believable name or copied raw GUID is not sufficient.

## Durable Lifecycle

Proposed request path:

```text
received -> grounded -> proposed -> validated -> authorized -> dispatching
         -> applied -> verified -> resolved
```

Alternative states are `no_action`, `awaiting_clarification`, `awaiting_capability`, `blocked`, `failed`, `uncertain`, and `cancelled`. `awaiting_capability` links to a task and does not erase a player promise. A typed rejection says whether another proposal is allowed; it does not authorize arbitrary retries.

Use separate effect and obligation states. A quest publication request can resolve while the accepted quest obligation remains active for days. `applied` means an executor receipt exists; `verified` requires the artifact's explicit proof predicate. Server evidence alone cannot prove a new client tooltip is correct.

Each transition uses expected state/revision. Persist decision/artifact before dispatch. Insert dispatch intent with its state change in one transaction. Retries use the same request/effect identity, never a new random key to escape deduplication. A revised proposal receives a new artifact hash and invalidates old authorization.

### Native Effect Safety

| Class | Example | Recovery rule |
|---|---|---|
| Read-only | Inspect selected character | Retry within budget |
| Idempotent desired state | Ensure an owned flag has a particular value | Recheck ownership/version; retry same effect key |
| Durable entitlement | Award one specific managed reward instance | Unique grant identity in the actual effect persistence path; reconcile before retry |
| Non-repeatable/opaque | Increment without durable identity, one-time message/scene commitment | Unknown result parks for reconciliation/operator; no blind replay |

Do not classify an aura as idempotent merely because its spell ID is the same: reapplication may refresh duration, reset charges, trigger procs, or remove another effect. The exact native behavior determines retry class.

A worker lease prevents simultaneous claim ownership only when checked, and stale workers need fencing. A lease timeout does not prove the previous worker had no side effect. Claiming and executing on the world thread must respect the core's database scheduling; inspect that API before replacing queries.

For inventory, recording an entitlement in the same character-side durable operation is preferable to relying on a separate world queue receipt. This must be integrated with core inventory persistence, not patched using speculative raw SQL around an in-memory item. Until proven, an ambiguous grant is `uncertain`.

Compensation is conditional: remove only the entity/version WM still owns. Do not restore an entire old world snapshot over another event, a player's progress, or legitimate later loot.

## Content Is Compiled, Not Guessed

The model supplies player-facing intent and references. The compiler owns the required DB records and invariants. Its output includes a dependency graph and explanations of blockers.

| Content | Compiler evidence required before eligibility |
|---|---|
| Quest | Fresh owned ID; usable starter/ender; level/faction conditions; target hostility for this player; sufficient reachable spawns/respawn plan; objective credit path; clear directions; reward and continuation |
| Creature / object | Valid template/model dependencies; usable interaction flags; supported map/phase/position; placement checks; lifetime, ownership and cleanup |
| Item | Template validity, display/icon, equip/use constraints, complete tooltip, actual effect carrier, binding/grant scope, owned-instance handling |
| Ability | Native behavior present and versioned; shell family and fresh identity; target/range/LOS/cost/GCD/CD; trigger/consume rules; visible state; client/server payload compatibility |
| Scene / world change | Typed steps, timing limits, affected players/quests, interruption behavior, spawn ownership, restoration or replacement outcome |

Template spawn counts are necessary evidence, not proof of current population or accessibility. Distinguish map template availability from live reachability, faction hostility, phasing, and exhaustion caused by other players.

Bind client manifest hash, server DBC hash/version, and native behavior version to any release needing them. A preinstalled generic shell cannot display arbitrary new names/icons unless the client payload supports that mapping. If the client update requires restart, stage the release; do not promise instant delivery. Unsupported mechanics require a development task even when a visually similar stock spell exists.

## Sensing, Initiative, And Memory

Use native events to maintain projections, with periodic authoritative reconciliation for missed events. Retain source IDs and detect gaps. Cheap deterministic filters collapse duplicate kills/combat events into opportunities; do not invoke a model per tick. Combat-speed mechanics stay entirely native.

The context packet separates facts, explicit notes, inferred preferences, available capabilities, and unknowns. Include timestamps and evidence references. Never present an inferred memory as a current DB fact. Keep player-known information separate from director-only information to prevent narrative spoilers.

On Demand suppresses unsolicited new experiences, not observation or resolution of accepted work. Moderate and Active expand candidate frequency/initiative only inside the same policy envelope. Safety, feasibility, and continuity checks are unchanged.

Author's Notes are versioned and scoped. World notes and character notes may both apply; scope alone does not silently resolve conflicting firm constraints. Store a clarification request when those conflict. A forget request updates retrieval eligibility and derived summaries; it must not erase mandatory execution audit or turn an unresolved reward into a duplicate grant.

## Security And Failure Containment

- Player chat, NPC text, imported lore, and external MCP responses are untrusted data. They cannot change policy or tool grants.
- Separate model service credentials from operator/deployer and DB mutation credentials. The model endpoint receives no database passwords.
- Enforce player/map/phase/radius/TTL/quantity limits in code and again where native effects execute.
- Rate-limit per player and world; enforce shared-world entity budgets independently of initiative presets.
- On model outage, continue already-defined deterministic obligations and cleanup. Defer new creative decisions.
- On uncertain world state, withhold unsafe mutations and expose the reason. Do not fill missing facts with plausible fiction.
- A kill switch stops new effects; already-applied owned temporary state requires reconciliation, not silent abandonment.

## One Operator Flow

The panel should answer: who is selected, what WM actually knows, which policy applies, what it is trying to do, what it owes the player, which effect is uncertain, and what evidence supports completion. Show development requests alongside blocked experiences. Allow inspect/reconcile/cancel/pause through typed operations, never a raw escape-hatch textbox.

This is where the harness becomes usable: a model failure becomes an understandable status with a bounded next action, rather than a broken quest that the player diagnoses from screenshots.
