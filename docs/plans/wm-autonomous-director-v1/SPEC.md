# WM Autonomous Director V1

## Problem Statement

WM has substantial operator, native sensing, publishing, and gameplay infrastructure, but the user still needs a coding agent to keep ordinary WM experiences working. Finishing this release means WM observes actual play, understands natural-language direction, creates playable content, handles consequences, and reports real results through a universal operator panel.

Prior failures included objectives on unsuitable or insufficient targets, missing actors, missing rewards, incorrect spell presentation, and disconnected mechanics. A valid draft, successful DB write, or passing source test alone does not establish a playable result.

The existing released operator scope remains useful history. This is an extension with new acceptance criteria, not a claim that earlier releases never worked.

## Solution

WM becomes an autonomous director for one local AzerothCore 3.3.5a server. It uses existing typed capabilities to react, author content, and change the shared world within approved policy. It remembers explicit direction as Author's Notes, offers three initiative presets, and automatically files development requests when a needed mechanic is unsupported.

The player can ask for an experience in ordinary language. WM either delivers a supported, verified result; reports pending deployment; asks a material clarification; or explains a concrete blocker and links a development request when appropriate. It does not claim a requested effect exists merely because its shell or description exists.

## User Stories

1. As a player, I want WM to recognize my current location and surroundings so its reactions fit what is actually present.
2. As a player, I want WM to distinguish current observations from stale or missing data so it does not invent nearby targets.
3. As a player, I want meaningful actions to produce relevant consequences so the world responds to play.
4. As a player, I want ordinary movement and repetitive kills to remain quiet when nothing useful follows.
5. As an operator, I want On Demand, Moderate, and Active presets so I can choose WM's level of initiative.
6. As a player, I want Moderate by default so WM participates without continuously interrupting me.
7. As a player, I want On Demand to continue existing quests, stories, consequences, and cleanup so changing pace does not strand content.
8. As a player, I want natural-language commands to request quests, supported spells, scenes, and world changes without knowing database IDs.
9. As a player, I want a request to survive a service restart so I do not need to repeat it.
10. As a player, I want duplicate delivery of a command or event to avoid duplicate rewards or world changes.
11. As a player, I want WM to report applied, pending, failed, or deferred work honestly.
12. As a player, I want standing instructions such as "give me fewer quests" remembered across sessions.
13. As an operator, I want a dedicated Author's Notes view so I can inspect and correct the direction WM follows.
14. As an operator, I want World and Character note scopes so broad setting direction and personal progression can coexist.
15. As a player, I want in-game notes to default to my character so an ordinary preference does not silently rewrite world-wide direction.
16. As an operator, I want to edit, disable, remove, and optionally expire notes while retaining their source and history.
17. As an operator, I want an optional firm-constraint setting so a small number of non-negotiable directions can be distinguished from ordinary preferences.
18. As a player, I want meaningful ambiguity or conflicting firm constraints surfaced before the conflicting action.
19. As a player, I want generated quests to use attackable targets with achievable objectives and reachable start/turn-in paths.
20. As a player, I want concrete quest directions above narrative description so I know what to do and where.
21. As a player, I want generated quest rewards to appear correctly and arrive exactly once.
22. As a player, I want new spells to combine tested mechanics with meaningful parameters rather than just rename an existing spell.
23. As a player, I want spell costs, targeting, durations, cooldowns, icons, tooltips, and visible effects to agree with actual behavior.
24. As a player, I want WM to distinguish a spell available now from one awaiting a client patch or server restart.
25. As an operator, I want unsupported mechanics to become automatic, deduplicated GitHub development requests that a coding agent can implement.
26. As an operator, I want those requests to include intent, missing capability, expected behavior, acceptance tests, and known deployment requirements.
27. As a player, I want WM to reconsider deferred content after the required capability is deployed and verified, using the current world and my current preferences.
28. As a player, I want shared-world changes to have causes and account for dependent quests, drops, actors, and player progress.
29. As a player, I accept an event failing or retiring an accepted quest when WM explains the consequence and provides a coherent continuation.
30. As an operator, I want temporary changes restored after expiry or interruption without overwriting unrelated newer changes.
31. As an operator, I want persistent world changes to handle affected offline players when they return.
32. As an operator, I want the panel to show why WM acted or stayed quiet, what it used, what remains pending, and how recovery is progressing.
33. As an operator, I want tests and live evidence separated so release status does not exaggerate readiness.
34. As an operator, I want the system to work for different selected characters, with earlier named characters serving only as fixtures.
35. As a player, I want WM to keep useful conversation, observation, and required cleanup available when generation or GitHub is temporarily unavailable.

## Implementation Decisions

### Existing ownership and execution

- Extend the existing session API, autoplay service, context builders, character journey/memory, content publishers, control coordinator, action bus, shell bank, and proof runner. Do not create parallel general-purpose middleware.
- Python owns decisions, orchestration, validation, durable state, publishing, audit, and recovery. Existing native modules own sensing, atomic actions, and synchronous combat behavior.
- LLM output is a typed proposal or content composition. Deterministic code determines database rows, IDs, target eligibility, deployment dependencies, and allowed execution. No freeform SQL, GM commands, shell commands, config writes, or live self-modifying code is introduced.
- Human-authored and generated proposals use equivalent validation and execution gates. Policy-bounded autonomy substitutes standing authorization for repeated confirmation; it never substitutes prose for validation.
- Existing per-verb high-risk confirmation defaults are implementation baseline, not the agreed product ceiling. Proven, policy-authorized shared-world plans may run automatically with continuity checks. Do not solve this by globally marking risky native verbs as safe.
- Keep the selected canonical marker provenance and speaker identity attached to every request. A World scope is an explicit impact scope, not wildcard permission for unrelated native mutations.

### Durable request and result contract

- Extend existing durable storage for request identity, source event, original instruction, resolved intent, note/capability revisions, context evidence, artifacts, native references, and recovery state.
- Model received, clarification-needed, planned, previewed, applying, awaiting-result, awaiting-maintenance, verified, failed, compensating, and deferred outcomes using existing state conventions where possible. Pending work and deadlines remain visible after restart.
- Stable origin identity survives retries, process restart, and cross-channel duplicate delivery. The same compiled artifact is previewed and applied; changed facts or revisions require revalidation.
- Native queue acceptance, terminal execution, effect verification, and client visibility are distinct evidence stages. A non-throwing applier or generic "applied" envelope cannot establish all of them.
- Unknown execution outcomes are reconciled against receipts before retries. Multi-step work uses durable progress and conditional compensation; do not promise a transaction spanning DB, server runtime, and client files.

### Capability-backed content

- Derive a capability view from existing action contracts, native implementations, shell behaviors, release schemas, and proof/deployment metadata.
- Classify a requested capability as usable now, awaiting deployment/maintenance, unsupported, or temporarily unavailable. Surface the evidence and exact missing requirement in panel and planner context.
- Do not advertise every schema variant as implemented. A grant compiler that teaches a shell is not evidence that numeric damage, scaling, triggers, or cleanup have been realized.
- First-release composition proves a small reusable effect vocabulary, including a real trigger-plus-effect combination, usable by more than one character. Extend existing native runtime where generic parameterized behavior is missing. This is agent-developed infrastructure, not runtime code generation.
- Exact supported primitives and combinations are a versioned, tested catalog; unsupported combinations are rejected as a whole rather than silently losing requested mechanics.
- New visible identities use fresh managed IDs and required client assets. Already deployed, matching capabilities can run during play; new DBC/client payloads stay visibly staged until their prerequisites are satisfied.
- Keep the existing rule against repurposing stock spell IDs as permanent WM carriers. Existing proven character kits remain regression fixtures.

### Author's Notes and language

- Extend existing conversation steering into a distinct, editable Author's Notes surface with World and Character scopes.
- Preserve original wording, normalized direction, provenance, scope, active state, revision, and optional expiry. Explicit author direction stays distinguishable from observed memory and WM inference.
- Standing instructions persist by default; explicitly temporary requests do not become permanent notes. In-game scope defaults to the speaking character.
- Ordinary notes are preferences. Firm constraints are optional advanced metadata. More specific preferences may override broader preferences, never firm constraints. Conflicting applicable firm constraints request clarification only for affected work.
- Retain revisions rather than silently overwriting contradictory instructions. Explicit changes supersede earlier direction; unresolved contradictions remain visible.
- Apply relevant notes to perception interpretation, planning, content generation, and execution rechecks, not dialogue alone. A changed note invalidates incompatible pending work.
- Natural-language input routes to immediate tasks, notes, temporary instructions, or clarification. Identity and authorization come from the authenticated session, not from model-produced claims.

### Initiative and observation

- Presets are On Demand, Moderate (default), and Active. They change initiative, opportunity selection, pacing, and configurable budgets; execution gates do not change.
- On Demand still observes and remembers, answers requests, advances already-started stories and accepted quests, fulfills promised consequences, and performs cleanup.
- Moderate reacts selectively and avoids competing with unresolved content. Active seeks more opportunities but still requires relevance and avoids repetition.
- Freshness is based on timestamps and matching world identity, not an online flag alone. Expired, future-dated, wrong-map/instance/phase, or unavailable evidence is handled explicitly.
- Use relevant native context on demand when a proposed action needs more detail than ambient summaries provide. Faction-ID exclusions and spawn counts alone do not establish player-specific attackability or feasibility.
- Use event identity, persistent pacing state, deadlines, and bounded generation attempts. WM's own effects do not create uncontrolled reaction loops. Silence can be an intentional, inspectable decision.

### Quest reliability

- Compiler output is the shipped quest artifact. Extend existing validators, target resolution, and publisher contracts rather than cloning and manually fixing live rows.
- Validate target attackability, level, availability, phase/access, objective count, expected replenishment where relevant, prerequisites, start/end paths, reward truth, and concrete directions.
- Recheck volatile evidence before apply. Failure produces an actionable reason without burning live IDs or silently substituting a different objective.
- Generated content must pass readback, runtime availability, and player-visible acceptance/reward proof. Reward generation and progress transitions must be idempotent.

### World continuity

- Shared-world alterations, including stock spawn removal, are allowed when a meaningful cause and an executable continuity plan exist.
- Preview affected spawns/templates, quest relations and prerequisites, drops, services, live and offline progress, and any supported script/event dependencies. State coverage and unknown dependencies explicitly.
- Unknown impact blocks only the affected unsupported change and can produce a development request. It is not evidence that the entire world is safe to rewrite.
- Stage and validate replacement paths before disabling old content. Track concrete affected entities, before-state, ownership/revisions, deadlines, outcomes, and conditional recovery.
- First prove a bounded temporary encounter transformation with a quest continuation and restoration; then prove a lasting quest transition and offline catch-up. This establishes an extensible operation family without claiming support for every stock script.
- Failure or retirement of accepted quests is permitted with an explanation and coherent continuation. Preserve earned progress where semantically appropriate; compensation must not duplicate rewards.
- Restoration and rollback respect later legitimate changes. Conflicts are surfaced instead of overwriting unknown state.

### Automatic development requests

- Missing mechanics automatically create GitHub issues without per-issue confirmation, with duplicate detection, configurable rate limits, and panel visibility.
- Extend existing durable issue/proposal infrastructure with a delivery record; the current process-local panel queue alone is insufficient.
- Include originating intent, minimal relevant context, the evidence for the capability gap, expected behavior, examples, acceptance tests, known deployment needs, and deferred-content references.
- Publish through a configured repository integration. Strip credentials, unrelated chat, account identifiers, and private context not needed by the coding agent. Model output cannot choose arbitrary destinations or commands.
- Offline/auth/rate-limit failures retain a pending delivery locally. Reconcile ambiguous remote responses before retrying so restart or network failure does not create duplicate issues.
- Use separate issue lifecycle and capability lifecycle. Closing an issue does not establish availability; deployed version and proof determine when deferred content can be reconsidered.
- Reconsideration is not blind execution: recheck current intent, notes, selected target, world facts, expiry, and policy.

### Operator surface

- Keep WM Session as the primary operator flow. Present current scope, initiative preset, Author's Notes, request outcomes, development requests, maintenance, and recovery in that flow.
- Explain why WM acted, deferred, or stayed quiet using concise decision evidence. Do not expose raw internal prompts as ordinary product copy.
- Migration preserves current character notes, pending work where recoverable, and compatibility callers. No fixture GUID becomes a default.

## Testing Decisions

- Primary boundary: observed event or natural-language input plus session/context -> real planning/validation/execution orchestration -> durable outcome visible through the session API and panel. Use existing injected LM, clock, DB/native, and publisher boundaries; avoid a second test-only planner.
- Extend existing replay rather than equating its canned response score with runtime proof. Exercise actual memory retrieval, initiative decisions, state restart, typed compilation, result reconciliation, and outputs.
- Use focused contract/native tests for physical mechanics and publisher behavior, where whole-session tests cannot locate a failure accurately.
- Preserve current marker, native guard, quest compiler, shell audit, memory, state concurrency, and rollback tests. Do not weaken them to obtain a green suite.
- Test duplicate events/commands, concurrent workers, restart after each side-effect boundary, wrong/stale target, changed notes, delayed native failure, malformed LLM output, missing capabilities, GitHub outage, and partial deployment.
- Quest regression corpus includes friendly/neutral unsuitable targets, too few accessible spawns, missing questgiver/model, incorrect reward display, unreachable turn-in, and changed active content.
- Spell corpus includes no-op shell bindings, wrong self/hostile targeting, resource/cooldown mismatch, missing icons/durations, stale DBC/MPQ, unrelated aura removal, and cross-character isolation.
- World-transition corpus includes already-accepted quests, offline participants, replacement publication failure, expiry while server is down, conflicting edits, and no duplicate reward.
- Acceptance requires a green full suite without ignored failures, reproducible from a tracked checkout, relevant native builds/tests, browser smoke, and recorded live proof. A test-environment failure is reported accurately, not excused as green.
- Run one representative recorded play session for each preset and across at least two selected character identities. Proposed release sample: 30 minutes per preset, with a fixed event/request corpus plus free play; repeat required cases after one restart.
- Mandatory outcomes: supported quest acceptance/completion/reward, composed spell behavior, maintenance staging/re-entry, persistent notes, unsupported mechanic -> one development issue, temporary world restoration, lasting quest continuation, and recovery from one injected interruption.
- Required invariants: no duplicate grants, no cross-scope execution, no unhandled quest stranding, no false completion, and no unresolved release-blocking defects. Timing budgets and generation deadlines are configurable and recorded; the runtime must report pending work rather than block indefinitely.
- Repo, native, deployed server, and in-client evidence are separate. New release capabilities remain PARTIAL until their required evidence is present.

## Out of Scope

- Runtime generation, compilation, or installation of arbitrary new native code.
- Universal support for all imagined mechanics or every stock quest script in the first release.
- A replacement game core, a second action bus, or a new general-purpose agent framework.
- New bespoke Broug/Jecia story content as a completion milestone.
- Multi-tenant hosting or a multi-operator administration product.
- Unattended server restarts or client patch installation outside the established maintenance workflow.
- A blanket ban on shared-world changes; these are explicitly in scope through supported continuity plans.
- A promise of zero bugs or proof inferred solely from model confidence.

## Further Notes

This spec synthesizes user decisions made on 2026-09-14. The source baseline is local commit 5a0ee41eb1fd9d9bd32db1fa7e0b780adf707122 plus pre-existing uncommitted operational/docs work. Existing milestone prose and this proposed release are different scopes.

Fresh baseline: 1,245 tests passed and one DLL-guard test failed because its PowerShell subprocess could not resolve Get-FileHash; 31 warnings. Skill/status validation passed; native reporting shows 64 contracted kinds and no implemented product-contract gap. BridgeLab DB and SOAP were unreachable during planning. No new gameplay proof is claimed.

Implementation tickets are complete, bounded flows and may proceed when their actual blockers are done. The floor repair gates release verification, not independent design work. Do not push or absorb unrelated local changes as part of a ticket.
