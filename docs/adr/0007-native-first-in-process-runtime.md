Status: PROPOSED
Last verified: 2026-05-19
Verified by: Claude
Doc type: adr

# ADR 0007: Native-First In-Process WM Runtime

## Context

The WM platform routes every live game mutation through a DB-polling
bridge: Python writes `wm_bridge_action_request`, C++ `PollActionQueue`
claims one row per `actionPollIntervalMs` cycle, executes it, writes a
result row, Python polls the result. ADR-0002 established that new
capability extends this bus rather than spawning a parallel runner.

That decision still holds for *authored mutations* (spawn this NPC, grant
this item, publish this quest) — those originate from Python reasoning and
LLM output, so the DB seam is correct.

But a class of logic does not originate from Python reasoning. It is pure
in-process bookkeeping that fires on game hooks and needs live `Player*` /
`Unit*` pointers:

- Effect enforcement (no aura on target ⇒ effect must not tick)
- Kill / event counters feeding journal context
- Threshold evaluation (kill count crosses N ⇒ nemesis/bounty eligible)
- Active-character lifecycle (login ⇒ attention aura, logout ⇒ strip)

Running these through the bus costs 250 ms–1 s latency per cycle, one
action per cycle throughput, and 2× DB round-trips for what is a map-write
or a hash-map lookup. The user directive: *"Python bridge is ASS, use
native stuff implementing it into core. There is no need for slowdowns and
complications if it can be built natively."*

Forces:
- Project ships with full C++ source; rebuilding worldserver is cheap.
- BridgeLab (`D:\WOW\WM_BridgeLab`) is a working MSVC build/test env.
- Python must still own LLM, journal persistence, arc decisions, authoring
  — those are external I/O and reasoning, not game state.
- ADR-0002 must not be violated: no second C++ *action runner*.

## Decision

In-process, hook-driven bookkeeping moves into native C++ singletons that
run synchronously on the game thread. The DB action bus is retained
unchanged for authored mutations. Native bookkeeping writes its durable
record to DB as an *audit trail*, not as a command channel.

Rules:

- A capability is **native** if it (a) fires on a game hook and (b) needs
  a live `Player*`/`Unit*` or (c) is a counter/gate with no LLM input.
- A capability stays **Python** if it needs LLM, journal context, or any
  external service, or it authors new world content.
- Native bookkeeping records state to DB for Python to *read*; Python
  never polls it back to drive C++.
- No new C++ action runner. Native singletons are passive registries /
  evaluators invoked from existing hooks, not a parallel queue.
- The `wm_bridge_action_request` bus remains the only command channel
  from Python to C++.

Reference implementation already landed: `WMEffectRegistry`
(`mod-wm-bridge/src/wm_effect_registry.{h,cpp}`) — in-process effect gate,
O(1) `IsActive`, registered on `AddAura`, unregistered on `OnAuraRemove`,
swept on `OnUpdate`. Python `ActiveEffectTracker` retained as audit layer.

## Options Considered

### Option A: Keep everything on the DB action bus

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (no new code paths) |
| Cost | High runtime cost — latency, throughput ceiling |
| Scalability | Poor — 1 action/cycle bottleneck under load |
| Team familiarity | High |

**Pros:** One mental model; all mutation auditable in one table.
**Cons:** Effect ticks gated by a 250 ms+ poll; counters lag; cannot
enforce "no aura ⇒ no effect" within a tick.

### Option B: Native-first for in-process bookkeeping (chosen)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium — new singletons, but passive and small |
| Cost | Near-zero runtime cost (hash-map / map-write) |
| Scalability | Scales with game thread, no queue bottleneck |
| Team familiarity | Medium — C++ module work, already in BridgeLab |

**Pros:** Synchronous enforcement; no latency; counters always current;
Python freed for what it is good at.
**Cons:** Logic split across two languages; native bugs need a rebuild;
must hold the discipline line (ADR-0002) to not grow a second runner.

### Option C: Full native (move authoring + LLM glue into C++ too)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Very High |
| Cost | Low runtime, very high build/maintenance |
| Scalability | Good runtime, poor iteration speed |
| Team familiarity | Low — LLM orchestration in C++ is hostile |

**Pros:** One process.
**Cons:** Throws away Python's iteration speed for LLM/authoring; rebuild
for every prompt tweak. Rejected.

## Trade-off Analysis

Option A's cost is paid every tick, forever, for logic that has no reason
to leave the process. Option C pays a permanent iteration tax to remove a
seam that is actually load-bearing (Python *should* own LLM/authoring).
Option B draws the line where the data naturally splits: reasoning and
external I/O in Python, live-state bookkeeping in C++, DB as an
audit/command seam with directional rules. The discipline risk (drift into
a second runner) is mitigated by keeping native pieces passive — registries
and evaluators invoked from existing hooks, never a queue.

## Consequences

- Effect enforcement becomes synchronous and exact (no aura ⇒ no tick).
- Journal counters are always current; arc decisions read fresh state.
- Threshold/nemesis evaluation triggers within the kill hook, not a poll.
- Authoring latency is unchanged (correctly still bus-routed).
- Logic is split across languages — every native capability needs a
  BridgeLab rebuild + live proof before promotion.
- Must re-assert ADR-0002 in review: native additions are passive
  registries/evaluators, not action runners. Any PR that adds a C++ poll
  loop or command queue is architecture drift and rejected.
- The Python↔C++ contract is now directional per table: command tables
  (Python→C++) vs audit tables (C++→Python, read-only for Python).

## Action Items

1. [x] Land `WMEffectRegistry` native effect gate (reference impl).
2. [ ] Native journal counter: increment `wm_journal_counter` directly in
       `OnPlayerKilledCreature`; Python reads, never writes the counter.
3. [ ] Native threshold evaluator: nemesis/bounty eligibility computed in
       the kill hook, emits an *event* (not an action) for Python to author.
4. [ ] Native active-character lifecycle: login applies attention aura,
       logout strips it, via player hooks + `WMEffectRegistry`.
5. [ ] Document the directional table contract in
       `docs/WM_PLATFORM_HANDOFF.md` (command vs audit tables).
6. [ ] Add a review gate: reject C++ PRs introducing a second poll/queue.
