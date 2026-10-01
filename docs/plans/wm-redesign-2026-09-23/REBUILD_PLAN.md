Status: PARTIAL
Last verified: 2026-09-24
Verified by: Codex
Doc type: design

# WM Rebuild Plan: A Personal World Master

## Executive Decision

**Repair and consolidate the existing platform; rebuild the director's decision flow. Do not rewrite the game core or start a new agent framework.**

The product is a world that notices what a player does, develops that character's story, and delivers unusual but functioning experiences. Quests, scenes, companions, items, and powers are delivery tools. Passing tests, adding infrastructure, and producing narrative text are not the experience itself.

This plan makes the technical decisions delegated by the user. It preserves the [agreed product language](../../../CONTEXT.md) and [September release requirements](../wm-autonomous-director-v1/SPEC.md). It refines implementation order and acceptance, rather than erasing the existing work. Implementation has begun; see [current status](IMPLEMENTATION_STATUS.md) before enabling any new lane.

**Delivery strategy:** prove a small, genuinely personal play loop early, then expand its creative vocabulary. Reliability work must unlock a named player outcome. Do not wait for universal spell generation or arbitrary world editing before showing the user a worthwhile session.

## 1. What Success Feels Like

An illustrative session, not a hardcoded character script:

1. A player explores ruins and expresses an interest in forgotten magic. WM remembers the instruction and distinguishes exploration from incidental kills.
2. When the player is available, a brief encounter draws on something actually discovered. The player can engage, decline, or continue playing.
3. Engagement opens a short personal arc with a choice that changes its continuation. A quest may help track progress, but not every beat adds a quest.
4. The payoff is a useful, visible item, power, companion interaction, or world consequence supported by deployed capabilities. A renamed stock reward alone does not satisfy the full creative goal.
5. On a later login, WM recalls the decision and follows through. A player who prefers combat encounters gets a materially different opportunity from the same location.

The director may surprise the player. It must not invent past achievements, diagnose personality from gameplay, force engagement, expose undiscovered plot information, or call an unfinished mechanic a reward.

### Product Requirements

| ID | Requirement | Observable acceptance |
| --- | --- | --- |
| R1 | Understand current play | Decisions cite fresh, correctly scoped evidence; missing facts cause a refresh, deferral, or silence |
| R2 | Remember the individual | Explicit notes and actual choices alter later content across logout/restart; no cross-character leakage |
| R3 | Create more than text | An authored beat produces a scene, achievable objective, functioning reward, or persistent consequence |
| R4 | Respect player agency | Decline, ignore, pause, and direction changes have coherent outcomes; no repeated nagging |
| R5 | Maintain personal arcs | Started beats, promises, relationships, progress, and consequences survive interruption |
| R6 | Deliver unusual powers | At least one generated trigger/effect composition works, is visible, and differs mechanically from a rename |
| R7 | Edit before publishing | Content passes deterministic feasibility and explicit narrative-quality review |
| R8 | Publish honestly | Accepted, applied, visible, and behavior-verified are distinct states with evidence |
| R9 | Change the world coherently | Supported shared-world changes handle affected quests, players, expiry, and restoration |
| R10 | Recover safely | Retries/restarts do not duplicate rewards or overwrite later legitimate world changes |
| R11 | Work without a coding agent | Ordinary play, notes, approved content, and cleanup operate through the runtime |
| R12 | Stay understandable | One operator view explains current stories, decisions, blockers, maintenance, and recovery |

## 2. Current Baseline and Main Problems

Inspected local HEAD: `5a0ee41eb1fd9d9bd32db1fa7e0b780adf707122`, with pre-existing dirty documentation and operational work preserved. Fresh verification on September 23:

- Full Python suite: **1,245 passed, 1 failed, 31 warnings**. The failing DLL-guard subprocess cannot resolve `Get-FileHash`; root cause is not yet established.
- BridgeLab doctor: **NOT READY**. World/character DB on port 33307 and SOAP on 7879 refused connections. Config reports wildcard observation scope. No services were started and no live content was changed.
- Native report: 100 declared kinds, 64 contracted, zero implemented product-contract gaps. Thirty-one declared product kinds remain unimplemented. Declaration counts are not capability proof.
- GitHub PRD #5 and tickets #6-#20 are still open as of the read-only tracker check. No ticket was modified or closed.

### Source-Confirmed Problems

| Finding | Evidence | Plan consequence |
| --- | --- | --- |
| Personal context is lost before automatic generation | `context/pack.py:56` returns `character_state`, `memory`, and `native_context_snapshot`; `autoplay/service.py:2306` reads other player keys and omits memory/snapshot. A pure-function probe reproduced `player={}` and both omissions | Repair the real builder-to-generation contract before tuning prompts |
| Automatic creativity is intentionally shallow | `autoplay/service.py:2252` maps event types to lanes; `:2294` asks for one low-risk reaction; `:2306` specifies no rewards | Replace event-to-lane selection with grounded opportunity and beat selection, while preserving deterministic execution limits |
| Missing facts still solicit an answer | `llm/prompts.py:7` instructs conservative drafting even with missing required facts | Add explicit need-evidence, defer, unsupported, and no-action outputs |
| Existing critique is not a full editor | `llm/critique.py:36` checks basic quest fields and forbidden keys | Keep checks; add continuity, personal relevance, pacing, novelty, and reward-meaning review |
| Replay does not prove the full director | `proofs/replay.py:29` uses a fake coordinator; `:83` starts in-memory remembered references | Test through the real director and persisted memory/recovery boundaries |
| Response fallback can reinterpret reasoning text | `llm/lmstudio.py:119` falls back when final content is empty; helper `:208` searches reasoning text | Require valid final response content; no guessed player-facing answer from internal reasoning |
| A second partial context/governor design already exists | `autonomy/decision_context.py:45` expects flattened fields rather than the actual session-pack shape; `autonomy/governor.py:74` offers a budget evaluator | Extend and wire these modules where useful; do not create a third context/governor implementation |
| Durable files are not a transactional lifecycle | `autoplay/state.py:202` updates draft/status/journal separately; `:259` and `:281` cap seen/dedup keys; `:372` atomically replaces individual files only | Move authoritative request/effect progress to a transactional ledger; keep files as diagnostics/projections |
| Panel state and completion evidence are too weak | `panel/approval_gate.py:53` stores pending work in a list; `autoplay/verification.py:35` treats outer applied status as verified; `_runtime_plan.py:65` infers rollback from lane name | One durable owner; effect-specific reconciliation and conditional compensation |
| Ability generation is not an executable generic power lane | `autoplay/_runtime_plan.py:28` always sends the ability lane to maintenance | Implement and prove composition/deployment before advertising it as usable |

These findings support a targeted rebuild, not a claim that all existing systems are broken. Additional source findings and design alternatives are summarized in the architecture sections below. Current in-client behavior remains **UNKNOWN** until fresh proof.

## 3. Architecture Decision

Choose a **staged director inside the existing Python application**, backed by durable operation records. Keep synchronous game mechanics in native hooks. Do not introduce microservices, Kafka, Redis, a graph database, or a general multi-agent runtime.

```text
Native game hooks / player direction / existing obligation
    -> canonical evidence + identity
    -> per-character attention and obligation scheduler
    -> relevant context + notes + capability readiness
    -> sensory interpretation and opportunity selection
    -> creative beat proposal + pure compilation preview
    -> deterministic preflight + editorial verdict
    -> freeze approved release artifact and bind reserved identities
    -> policy + fresh-state recheck
    -> existing publishers / coordinator / native action bus
    -> execution reconciliation + visible outcome evidence
    -> journey, memory, obligations, next opportunity
```

These are responsibilities, not eight processes or mandatory model calls. The panel and in-game chat must enter the same request lifecycle, not own competing execution paths.

### Alternatives Considered

**A. One compact director:** `accept(scope, input)`, `advance(now, budget)`, `inspect(scope, request_id)`. Callers cannot accidentally run stages in the wrong order. Alone, however, this can hide another giant coordinator and block recovery behind a slow model call. Take its public interface, but keep explicit internal stages and scheduling.

**B. Staged in-process director, chosen:** use the compact external interface, with separately testable evidence, opportunity, creative/editorial, and reconciliation modules. Reuse `wm.autonomy`, `wm.autoplay`, journey state, and existing publishers. It provides the best balance of explainability, incremental migration and local operations. The cost is explicit versioned contracts and durable transition bookkeeping.

**C. Separate durable workers/services:** model jobs, publishing, recovery and memory each consume durable work independently. It offers isolation and scaling but adds deployment, ordering, ownership and compatibility burdens before workload evidence warrants them. Retain durable jobs/claims from this design inside the current application; split processes only if measured latency or isolation requirements justify it.

One independent compact-design review completed. Two other delegated reviews hit usage limits; staged/worker alternatives and their source checks were completed by the main reviewer, not independently validated by three agents. The chosen architecture is recorded in [ADR 0008](../../adr/0008-durable-player-experience-director.md).

### Public Interface and Data Contracts

The proposed interface is an internal Python interface, not a new network service:

```python
receipt = director.accept(authenticated_scope, input_with_stable_origin)
progress = director.advance(now=clock.now(), budget=work_budget)
view = director.inspect(authorized_scope, request_id=receipt.request_id)
```

`accept` durably deduplicates and records a typed event, player instruction, note edit, or initiative change. It acknowledges receipt, not success. `advance` performs bounded eligible work, including overdue obligations and reconciliation. It must not wait synchronously for generation before servicing cleanup. `inspect` has no side effects: opening the panel cannot submit snapshots or replay actions.

Use existing Pydantic/dataclass conventions, with additive versions where contracts change:

| Contract | Required information |
| --- | --- |
| Evidence frame | Original scope/source IDs, world identity, observation timestamps, availability/coverage, relevant history/notes, freshness and missing-fact markers |
| Opportunity | Evidence references, arc/obligation reference, reason for acting, intended player benefit, expiry, pacing cost, no-action alternative |
| Beat proposal | Meaningful outcome, choice/decline paths, capability requirements, visible artifacts, continuation, reward budget and scope |
| Editorial verdict | Proposal/content hash, rubric findings, accept/revise/reject, concrete defects and revisions consumed |
| Execution manifest | Approved content hash, resolved IDs, policy/note/catalog revisions, ordered effect keys, preconditions, expected receipts and compensation rules |
| Outcome | Per-effect accepted/applied/verified evidence, unresolved visibility or behavior requirements, resulting obligations and recovery state |

Concrete names are implementation details; do not create pass-through wrappers around every existing module. Preserve origin and scoped authority throughout, even where legacy adapters currently reclassify a proposal as `manual_admin`.

### Ownership

| Owner | Writes | Must not own |
| --- | --- | --- |
| Native bridge/spell runtime | Authoritative observations, atomic action results, synchronous combat behavior and native cleanup | LLM calls, narrative planning, arbitrary model-generated commands |
| Director scheduler | Request transitions, opportunities, deadlines, pacing and obligation scheduling | Client presentation claims or fabricated gameplay facts |
| Context/memory module | Provenance-aware retrieval, note revisions, episodic summaries and justified inferences | Promotion of model speculation into authoritative world state |
| Creative/editorial stages | Typed proposals and bounded review verdicts | Database IDs, permissions, deployment readiness, direct mutation |
| Existing compilers/publishers | Validated artifacts, reserved IDs, publication/recovery receipts | Quietly changing approved content into something else |
| Reconciler | Durable effect/outcome verification and conditional compensation | Assuming a timeout means nothing happened |
| Panel | Operator commands and projections of authoritative state | A second pending-work store or autonomous executor |

### Keep, Repair, Replace, Defer

| Decision | Scope |
| --- | --- |
| Keep | Native event/action bus, native combat hooks, control registry, quest/item publishers, reserved IDs, shell bank, journey/memory tables, release/proof tooling, existing LM Studio transport |
| Repair | Context handoff, freshness/scope, real capability readiness, runtime/result reconciliation, chat request identity, note retrieval, client deployment receipts |
| Replace incrementally | Event-to-lane reaction selection; in-memory authoritative pending work; outer `applied` as completion; forced drafts on missing facts; reasoning-text response fallback |
| Consolidate | Chat/panel/automatic entrypoints behind one lifecycle; duplicate model configuration and context paths; capability rosters as one evidence-backed view |
| Defer | Cloud-model migration, vector/graph memory, new orchestration frameworks, new frontend framework, universal ability language, arbitrary stock-script rewrites |
| Retire only after parity | Superseded demo routing, obsolete aliases, duplicate launch paths and unused legacy transports; prove no remaining callers before deletion |

Do not remove tested special-purpose native mechanics just because generic composition is coming. Keep them as adapters/regression cases until equivalent behavior is proven.

## 4. Sensory and Personalization Design

**Perception means game-state understanding, not continuous screenshot watching.** Native events and targeted snapshots are authoritative. Client images are proof/debug aids unless a future feature demonstrates a need for runtime vision.

Build one versioned evidence frame containing identity, world/map/instance/phase, timestamp and sequence, current situation, relevant actors, active objectives, capability revisions, applicable notes, selected history, and missing/stale facts. Separate server truth from what the player has learned; hidden plot facts may constrain feasibility without entering player-facing prose.

- Reuse existing context loaders. Pass the active runtime settings/client explicitly; never silently query a different environment.
- Preserve required notes, active obligations, and safety facts during compaction. Optional flavor/history is the first content removed. Missing required sections invalidate generation input rather than becoming empty dictionaries.
- Determine freshness per fact/action: a historical achievement can be old; a nearby target or combat state cannot. Store actual age, source, and relevance. Refresh volatile facts before execution.
- Coalesce repetitive events into meaningful episodes. A raw kill is evidence, not an automatic request for a story. Tag WM-originated effects to prevent self-triggering loops.
- Infer only gameplay preferences, with evidence and uncertainty. Explicit notes outrank inferred preferences; preferences never override firm constraints or execution policy.
- Keep Author's Notes distinct from episodic history, inferred tendencies, and active obligations. Character scope defaults for player speech; World scope requires authorized operator direction.
- Preserve pin/suppress/forget across extraction retries and same-key upserts. Store a suppression/tombstone revision separately from generated text so replay cannot resurrect deliberately removed content. Do not rely on English cue substrings to recognize standing instructions.
- Use existing relational state and entity/time/tag retrieval first. Add semantic search only after a measured recall failure that structured retrieval cannot fix.

The sensory model may interpret a summary and propose an opportunity; deterministic code decides which facts exist. Give it `act`, `wait`, `need_evidence`, or `no_op` choices. It cannot manufacture observations or turn untrusted NPC/player text into tool permissions.

## 5. Creative and Editorial Design

### Create Experiences Before Picking Delivery Formats

Creative input is a grounded opportunity plus relevant character history, notes, unresolved threads, world tone, actual capabilities, and an intervention budget. Output an **experience beat**, with:

- player-facing purpose and connection to evidence;
- intended change, choice/decline path, continuation, and expiry;
- required mechanics/actors/assets and scope;
- expected visible result, reward cost, and consequence;
- existing arc/obligation links and reusable pattern identity.

The compiler chooses supported delivery artifacts. The LLM may compose them but does not assign production IDs. Allocate via the existing reserved-slot system, not truncated hashes or model numbers. Failure after an identity reaches a client follows the existing fresh-ID/retirement rules.

First creative vocabulary: a short two-to-three-beat arc, a temporary actor encounter, an authored quest with achievable choices/outcomes, a character-scoped visible reward, and a later callback. Existing living-world/nemesis/patron/companion patterns are candidate ingredients, not automatic proof of readiness.

Variation must change an objective, decision, mechanic, relationship, or consequence. Changing names and adjectives is insufficient. Track recent pattern/target/reward usage so novelty is assessed across sessions, not only within the current prompt.

### Two Kinds of Review

1. **Deterministic preflight:** supported capabilities, scope, fresh targets, achievable objectives, actor presence, rewards, client/server compatibility, budget, cleanup, dependencies, and existing contract validators. Reject unsupported work before expensive revision.
2. **Editorial review:** evidence grounding, personal relevance, understandable directions, continuity, player choice, non-repetition, pacing, and satisfying payoff. Return accept, revise with specific defects, or reject. Reviewer sees evidence and the proposal, not the generator's private reasoning.

A positive editorial verdict cannot waive a failed mechanical gate. Review the actual normalized/compiled player-visible content, and invalidate the verdict after substantive edits. Exhausting revisions means defer/reject, never publish the last draft by default.

Use the current configured local model first, with separate role prompts and structured outputs. Start with creator plus editor; call sensory interpretation only for a meaningful episode that needs it. One bounded revision is the default. Shared-model agreement is not independent correctness evidence; gameplay tests and human playtest feedback remain necessary.

### Pacing Defaults to Tune in Playtests

These are initial tuning values, not validated balance claims:

- Moderate: at most one unsolicited new substantial beat per 10 minutes and two unresolved unsolicited starts per character. Callbacks and accepted obligations are scheduled separately, but still avoid interruption.
- Active: five-minute minimum between new substantial beats, at most three unresolved unsolicited starts. On Demand: no unsolicited starts.
- Explicit requests bypass the unsolicited-start cooldown, not capability, reward, scope, or recovery rules.
- Avoid unsolicited dialogue during combat/loading/death recovery. Do not postpone native combat mechanics or emergency cleanup behind this rule.
- Bound the entire generation attempt to 90 seconds, at most five role calls including one revision/review pair. Late results require fresh-state revalidation. Start with one model request in flight per endpoint and fair per-character scheduling.
- Acknowledge an explicit request after durable receipt without waiting for generation; target under two seconds on the local test rig. Show pending/deferred status rather than filling the delay with invented progress. This target must be measured before release.
- Measure actual model latency and context capacity before enabling autonomy. Trim optional history before notes/obligations; reject oversized required context rather than silently losing constraints.

Rewards initially favor bounded sidegrades and distinctive utility so the early test isolates personalization from power inflation. This is not a permanent ban on strong progression or the roadmap's wild powers. Enforce authored numeric budgets in code; prevent reward farming through repeated prompts/declines/retries. Change the progression policy explicitly rather than through accidental generation drift.

## 6. Execution and Recovery Contract

No network or model request runs synchronously on the worldserver's gameplay thread. Combat timing, aura gating, costs, cooldowns, and native expiry remain native. Python authors and schedules, using the existing command bus.

Use durable identities from the source event or client-generated command token plus authenticated character and request kind. Content version and individual effect identities are separate. Never use current wall-clock seconds as the logical identity of a retry.

Canonical lifecycle:

```text
received -> needs_evidence / needs_clarification / deferred
         -> planned -> reviewed -> ready -> applying -> awaiting_result
         -> verified / failed / awaiting_maintenance / reconciling
         -> compensating -> compensated / needs_operator
```

Every transition records the previous revision, reason, input/artifact references, and resulting evidence. Persist intent before sending an effect. Store native request IDs and receipts. A stale worker must not commit after another worker has reclaimed its work.

### Durable Storage Decision

Add WM-owned InnoDB request/step/transition/outbox tables to the **existing configured world database**, alongside control-proposal records. Retain character notes, arcs, unlocks and rewards in their existing character-domain tables. The ledger owns operational progress; journey tables own game progression. References/reconciliation connect them rather than duplicating both truths.

Use a small **PyMySQL transactional adapter for the ledger only**, with parameterized statements, bounded connect/read/write timeouts, and credentials from existing settings. Do not rewrite all legacy DB access. The current `MysqlCliClient.query` launches a fresh process per call, so separate calls cannot hold one transaction. PyMySQL's documented connection/parameter/commit interface supports the required transaction boundary. Pin and test the selected dependency version during M1; none is installed by this plan. [Official transaction example](https://pymysql.readthedocs.io/en/latest/user/examples.html).

- Request rows have unique origin keys, scope, state/revision, next eligible time, deadline, claim owner/expiry and fencing generation. Step rows have unique effect keys, immutable input hashes, native/publication references and result evidence.
- Claim and transition use conditional updates inside short transactions. No model call, native wait, or file install occurs while holding a DB transaction. Duplicate acceptance returns the existing receipt.
- Commit the intended step and dispatch record together. The dispatcher submits through existing publishers/native queues using the same stable effect key. If it crashes after submission, it reconciles the downstream receipt before retrying.
- Ledger fencing alone cannot cancel a native effect already accepted. Test downstream deduplication and late-result handling for each operation; reject autonomy for operations lacking a safe retry/reconciliation contract.
- Versioned transition history stores concise reasons/evidence references. Local JSON status, draft exports and journals become projections, never competing writers of authoritative lifecycle state.
- Keep a durable input cursor and reward/effect deduplication keys beyond diagnostic-log retention. Bound storage through explicit archival rules only after pending work and replay horizons are resolved.
- When the DB is unavailable, stop accepting new durable commands with an honest unavailable response. Native timed cleanup continues; after reconnection, reconcile overdue work before admitting new mutations.

### Migration and Rollback

1. Back up relevant databases, local pending records, capability manifests and client/server assets. Rehearse restoration into an isolated test target before schema migration.
2. Add versioned tables/contracts without destructive changes. Import legacy records idempotently with original scope/provenance; ambiguous pending work becomes `needs_operator`, not silently applied or discarded. Do not invent original note wording or timestamps.
3. Run shadow decisions without effects and compare old/new context and choices. Use one execution owner per character; never dual-run mutating old/new loops.
4. Cut panel/chat/automatic callers over one proven lane at a time. Verify backlog counts, outstanding grants, note revisions and recovery links before switching the next lane.
5. If a cutover fails, disable new starts and keep the new reconciler available to drain/recover its outstanding work. Do not route those same effect keys back through an unaware legacy executor. Return to the old lane only after reconciliation; retain new tables for audit.
6. Retire old writers/aliases only after caller and recovery parity tests. Database rollback is not a blanket undo for content already seen by players; use the operation's conditional compensation and fresh-ID rules.

### Outcome and Failure Rules

- Distinguish schema validity, artifact publication, native acceptance, effect application, visible presentation, and behavioral proof. Pre-proven capability versions may use their recorded presentation/mechanic proof for ordinary grants; verify the new grant, not manually re-prove the entire mechanic every time.
- Use at-least-once processing with idempotent effects and reconciliation. Do not promise an atomic transaction across worldserver memory, MySQL, and client files.
- If an effect has an ambiguous result, query authoritative receipts/state before resending. Unsupported reconciliation means `needs_operator`, not an automatic duplicate.
- Prepare and validate replacements before disabling existing content. Compensation checks ownership/revision and records conflicts rather than overwriting a newer legitimate change.
- Service/model outage stops new creative work, not existing deterministic cleanup and recovery. The UI may show cached state as stale; it must not accept a supposedly durable request into volatile memory.
- Use separate controls for stopping new stories, stopping new execution, and emergency mutation stop. Explain which recovery/cleanup remains active; do not hide an unconditional cleanup bypass.

## 7. Powers and Shared-World Scope

**Powers:** build a deliberately small, versioned composition vocabulary inside `mod-wm-spells`, using existing proven mechanics where possible. Initial target: an on-cast/on-hit trigger, bounded damage/heal/timed-modifier effects, target restrictions, resource cost, cooldown, stack limit, and visible state. These are build targets, not advertised current capabilities. Unsupported combinations fail as a whole.

Prove both an active composition and a triggered variation on two selected characters. Check targeting, proc recursion, rate limits, death/logout/unequip cleanup, resource consumption, persistence and revoke. Existing special kits stay regression fixtures, not default identities.

Use already installed client assets/shells during play. New visible identities or presentation changes requiring DBC/MPQ work remain staged until matching client/server deployment is recorded. File staging, shell learning, and generated descriptions do not prove combat behavior. Do not promise unlimited fresh visible spells without client maintenance.

**World changes:** preserve the user's agreed shared-world authority. Start with one supported bounded transformation family, not arbitrary deletion of stock content. Its impact plan lists affected actors, quest relations/drops/services, online and offline progress, dependency coverage, before-state, replacement paths, scope, and restoration conditions.

Serialize conflicting changes to the same world resources. A character preference cannot become a World directive. Unknown script/quest dependencies block that particular change and create a capability gap; they do not justify disabling every world feature or blindly mutating it.

First prove a temporary event with a quest continuation and conditional restoration. Then a lasting transition with offline catch-up. The model provides intent/narrative; typed code applies progress transfer, failure/retirement, compensation, and duplicate-reward prevention.

**Missing capabilities:** create one deduplicated local development request and deliver it to the configured GitHub repository with redacted context. Delivery uses an outbox and rate limits. Issue closure does not enable content; deployed capability evidence does. Reconsider deferred ideas against current intent and world state rather than executing them blindly.

## 8. Delivery Milestones

No calendar promises until native build, client installation, model performance, and live access are measured. Complete each milestone's evidence gate; do not substitute documentation volume for completion.

| Milestone | Player outcome | Main work | Exit gate | Existing tracker |
| --- | --- | --- | --- | --- |
| M0: Trustworthy baseline | A reproducible place to test without damaging ongoing play | Diagnose DLL guard; snapshot versions/config; verify explicit scope; record clean proof fixtures and supported capability baseline | Full suite green without exclusions; BridgeLab scoped ping/read-only snapshot; rollback/backup rehearsal | #6, #8 |
| M1: Reliable personal attention | WM knows who/where the player is, remembers direction, and does not lose work | Context contract fix; durable request lifecycle; note scopes/revisions; freshness; opportunity selection; initiative; real-session replay foundation | Context round-trip tests; restart/duplicate tests; changed notes invalidate pending work; On Demand retains obligations | #7-#12; start #20 harness |
| M2: First personal playtest | A short generated arc, real scene/choice, visible useful reward, and remembered consequence | Beat planning, editor, existing quest/item/scene compilers, validated callback scheduling, operational panel | Two different characters get meaningfully different outcomes from the same test situation; accept/decline/completion/reward/cleanup proven; one restart | Expand #14, #20; explicitly add editorial/scene/callback acceptance |
| M3: Distinctive power growth | Earn a new functioning composition through play | Small native composition catalog; deployed-shell reuse; client readiness receipts; grant/revoke; development-request delivery | Active + triggered compositions with visible matching behavior; deployment-pending case; unsupported mechanic yields one issue | #13, #15, #16 |
| M4: Coherent world consequences | Encounters and choices can alter existing shared content | Impact coverage; conflict ownership; temporary replacement/restoration; lasting quest transition; offline catch-up | Temporary and lasting cases; crash during transition; later edits preserved; no stranded quests or duplicate rewards | #17-#19 |
| M5: Release and simplify | Play ordinary sessions without Codex maintaining them | Full-session evals, pacing/reward tuning, operator polish, supported-path consolidation and proven cleanup | Release matrix below; unresolved critical defects zero; migration/recovery rehearsed | #20, PRD #5 |

M1 foundations can proceed in parallel where write ownership is separate. M2 does not depend on generic spells or shared-world transitions; it uses a supported reward/scene vocabulary. M3 and M4 extend the same lifecycle after M2. Development-request delivery need not block the first personal playtest. No second backlog should be created just to rename these phases.

Requirement coverage: M1 establishes R1/R2/R4/R10; M2 proves R3/R5/R7/R8/R11/R12 in one small loop; M3 adds R6; M4 adds R9; M5 re-verifies all R1-R12. M2 is an early personal-play milestone, not completion of the full release.

### Source Work Map

| Packet/area | Existing code to extend | Regression surface |
| --- | --- | --- |
| Baseline | `scripts/bootstrap/Test-RuntimeDllGuard.ps1` | `tests/test_runtime_dll_guard.py`, full suite |
| Evidence/notes | `context/pack.py`, `context/builder.py`, `autonomy/decision_context.py`, `autoplay/world_context.py`, character memory/journey and chat extraction | Real builder-to-model request tests; note revision/suppression and snapshot-correlation tests |
| Ledger/lifecycle | `autoplay/state.py`, `autoplay/service.py`, `control/store.py`, panel approval adapters; new narrow ledger adapter | Existing autoplay/state concurrency tests plus real MySQL multi-process failure injection |
| Selection/pacing | `autonomy/governor.py`, `autoplay/policy.py`, current opportunity selection; existing arc/journey state | Fake clock, note changes, obligation priority, WM-origin feedback and multi-character fairness |
| Creative/editorial | `autoplay/llm.py`, `llm/prompts.py`, `llm/critique.py`, `autoplay/scene_compose.py`, content release and quest compiler | Malformed/rejected/revised beats; same compiled artifact reviewed and published |
| Execution/powers | `autoplay/_runtime_plan.py`, `autoplay/verification.py`, control coordinator, native bridge/spell runtime, DBC publisher | Native payload/quest/shell regressions plus deployed behavior, grant and compensation proofs |
| Whole experience | `proofs/replay.py`, `proofs/runner.py`, WM Session panel routes | Real lifecycle replay, persistent memory, browser smoke and recorded in-client sessions |

Paths in this map are under `src/wm/` unless otherwise shown. The implementation agent must read current versions before editing; line references above describe the inspected baseline.

### First Implementation Packets

1. **Baseline repair:** reproduce `tests/test_runtime_dll_guard.py` alone; diagnose child PowerShell command/module resolution; fix without bypassing hash verification; rerun focused and full suites. Preserve unrelated MySQL/log work.
2. **Context round trip:** use a real `build_session_context_pack` shape in a regression test; assert active notes, profile, selected history, current snapshot and missing-data flags reach the actual LLM request; test exclusions for forgotten notes and other characters.
3. **Durable request pilot:** one supported native action through panel/chat -> request -> claim -> apply -> result. Inject crashes at every side-effect boundary and prove no duplicate effect before generalizing the lifecycle.
4. **Capability truth:** join contracts, implemented handlers, deployment versions and proof metadata. Show usable-now, maintenance-required, unsupported, and temporarily-unavailable separately. Never replace these with a single registered/ready boolean.
5. **Grounded opportunity pilot:** the same event sequence plus different notes yields different justified candidates or silence. Verify no unconditional lane choice, no generation from stale context, and no reward/actor mutation during planning.
6. **One reviewed beat:** creator -> deterministic checks -> editor -> immutable compiler output -> existing publisher -> actual outcome. Include a rejected proposal and a revision that still fails. Then compose the short arc, not a parallel one-off script.

Packets 2-5 feed M1; packet 6 is the first M2 slice. Keep commits/reviews small and behavior-focused. Do not reorganize the whole repository before these flows work.

## 9. Evaluation and Release Gates

Extend the existing proof runner and replay; production and tests must use the same orchestration interface. Fakes belong at model/native/clock/transport boundaries, not as a second director implementation.

| Gate | Required proof |
| --- | --- |
| Deterministic correctness | Tests for wrong character/instance, stale/missing/future observations, malformed model output, unsupported capability, changed notes, budget exhaustion, and rejected editorial output |
| Durability | Real transactional-store integration tests with separate worker processes; duplicate ingestion; stale claim fencing; restart after each effect; late result and uncertain outcome reconciliation |
| Memory | Real note retrieval and updates, suppression/forgetting, return after logout, contradictory inferences, provenance and scoped isolation |
| Content | Actual compiler artifact reaches publisher; achievable objectives; reachable actors; visible accurate reward; no invisible/no-op mechanics |
| Agency and pacing | Decline ignored content without nagging; On Demand starts nothing unsolicited; existing obligations continue; WM effects do not trigger unbounded new work |
| Continuity | Replacement failure, offline participant, expiry while stopped, conflicting world edit, quest progress transfer and no duplicate compensation |
| Live outcome | In-client acceptance/completion/reward, working composed powers, cleanup/restoration, maintenance staging/re-entry and recovery from an injected interruption |

Initial quality evaluation: at least 12 fixed scenario pairs with changed history/notes, plus free play. Score grounding, personal relevance, player agency, novelty, pacing, clarity, and payoff on anchored 1-5 rubrics. Start with target median >=4 per dimension and no individual scenario below 3 without a documented fix/retest. These are provisional release targets, not scientific claims; the user's playtest judgment is decisive for enjoyment. A model judge may assist triage but cannot be the sole grader.

Every positive personalization score needs a traceable reason beyond changing the character's name. Include a memory-free baseline to show that history improves choices, not just prompt length. Quiet sessions can pass when no relevant opportunity exists; interaction count is not a quality metric.

Release sample: at least one 30-minute session per initiative preset, across at least two character identities, plus return-after-restart and offline-continuity cases. All R1-R12 have evidence links. No cross-scope action, duplicate grant, false completion, unresolved critical continuity defect, or unbounded generation loop is acceptable.

Record model/version, prompt/schema/catalog revisions, latency, role-call count, token usage when provided, context omissions, verdicts, request/effect references and concise decision explanations. Do not collect private chain-of-thought. Keep player-sensitive context out of external traces and GitHub issues by default.

## 10. Operator Experience and Operations

Keep WM Session as the primary screen. Show selected character, runtime readiness, initiative, active arcs/obligations, recent meaningful outcomes, Author's Notes, pending maintenance, and recovery. Put technical diagnostics behind detail views. Do not make the player operate a queue of approvals for already authorized supported content.

Use progressive modes: shadow decisions -> explicit request with supported execution -> Moderate autonomy -> broader capability families. The same contracts apply throughout. Progression between modes requires the listed evidence, not a calendar date.

Keep local development tools out of the runtime. Existing skills and shell/source reads suffice to implement the plan; optional Serena/Context7 installation must not become the critical path. Langfuse or other tracing infrastructure is optional after local correlated records demonstrate what is missing.

Operational cleanup follows usefulness, not folder size alone. Inventory source, native build caches, client assets, database files, backups and logs separately. Default diagnostic retention is the latest five completed run bundles per producer, with active runs and pinned proof incidents protected. Keep durable game state, deduplication identities, migrations and recovery evidence outside disposable logs. Use database-supported binlog purging only after checking backup/replication requirements; never recursively delete database internals as log cleanup.

## 11. Decision and Anti-Drift Rules

- This plan is the September rebuild execution guide; `CONTEXT.md` governs vocabulary and accepted product intent. Current evidence governs operational status. The older specification remains requirements history; disagreements must be reconciled explicitly.
- Every task names a player outcome, affected R IDs, source evidence, acceptance test and rollback/recovery effect. No generic cleanup sprint without a named payoff.
- Preserve wild features and shared-world authority as destinations. A deliberately narrow early playtest is not permission to reduce the product to polite commentary or bounties.
- No freeform model SQL/GM/shell/config/code mutation. No second native action bus. No stock spell hijacking. No model-created permissions or magic capability readiness.
- Do not solve reliability by permanent per-action confirmation. Do not solve creativity by removing validation.
- Update existing issues before executing expanded scopes. Keep original issue identities and dependencies; add missing scope only where it cannot fit coherently. This planning session leaves the remote tracker unchanged.
- Keep exact verification results and a short next-task handoff; avoid multiplying competing roadmaps. Archive superseded documents only after links and status are reconciled.
- Record unresolved assumptions rather than silently promoting them to requirements. Revisit architectural decisions only with evidence of a bottleneck or a product change.

### Decisions Reserved for the User

No blocking clarification is needed to start. Ask before a material change such as cloud spending/private-context upload, public/multi-tenant hosting, unattended client installation/server restarts, a substantially different power/economy philosophy, or relaxing world-continuity safeguards. Ordinary architecture, implementation ordering, scoped refactoring, and tests are delegated.

### Next Action

Begin packet 1 and the context-contract regression in packet 2. They establish a trustworthy test floor and fix a directly demonstrated personalization failure. Then prove the durable request pilot before adding more autonomous effects. Do not begin with MCP installation, a frontend rewrite, or a new bespoke named-character content pack.

## 12. Risks and Planning Verification

| Risk | Response / decision trigger |
| --- | --- |
| Local model is too slow or unreliable for role separation | Benchmark the real endpoint; reduce unnecessary calls/context and keep asynchronous pending work. Discuss hosted inference only if measured local results cannot meet the experience |
| Generated content is correct but dull | Compare personal-history versus memory-free scenarios and obtain user playtest judgment at M2; improve selection/choices/payoff before expanding mechanics |
| Existing native mechanics do not compose safely | Prove one narrow composition first, including proc recursion and cleanup; reject unsupported combinations and keep proven special handlers |
| World dependency coverage is incomplete | Limit autonomy to the covered transformation family; retain explicit unknowns and development requests instead of pretending universal coverage |
| Migration duplicates execution or loses legacy notes | One owner, stable keys, reconciliation before cutover, suppression-aware import and rollback rehearsal |
| Scope grows faster than playable results | Gate expansion on M2 evidence; defer optional infrastructure and catalog breadth, not personal agency or continuity |

Methods applied: `wm-workflow`, `gameplay-architecture`, `codebase-design`, `domain-modeling`, interface comparison, and the WM content/live-proof constraints. The inspected memory-systems and agentic-eval references informed temporal/provenance separation and bounded editorial review; they were not installed or treated as execution authority. See the [tool/skill assessment](TOOLS_AND_SKILLS.md).

Recorded baseline commands: `python -m pytest -q` (one failure, 1,245 passed); `python -m wm.doctor --profile bridgelab --summary` (not ready); `python -m wm.sources.native_bridge.contracts_cli --json` (zero implemented product-contract gaps). The context-loss probe used synthetic data through the real compaction function and performed no DB/game operations.

Planning-file checks: local Markdown links and ASCII content checked; `git diff --check`, `python scripts/validate_agent_skills.py`, and `python -m wm.status --validate` passed. No native build, model benchmark, client verification, game mutation, package installation, issue write, commit or push was performed. Implementation remains **DESIGN_ONLY**; the independently reproduced context defect and DLL-guard failure remain unresolved by this plan.
