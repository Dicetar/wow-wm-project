Status: PARTIAL
Last reviewed: 2026-09-30
Evidence: proposed interfaces; not callable tools yet
Doc type: design / agent reference

# Make The Simple Path The Correct Path

There are two different agents: the runtime World Master and the coding agent developing WM. Both need small tasks and explicit outcomes, but they must not share privileges. This document is their proposed contract, not a claim that the listed interfaces are installed.

## Runtime WM: One Decision At A Time

Prefer a single constrained response over a tool-calling loop for weak models. The host gathers facts, selects the schema for the current phase, and asks one question. The model returns one of five outcomes:

| Outcome | Meaning | Host behavior |
|---|---|---|
| `no_action` | Nothing useful or appropriate now | Record reason and next eligible trigger; no player spam |
| `ask_player` | One material ambiguity remains | Persist the question and wait; do not infer approval |
| `propose_beat` | A supported experience fits current evidence | Compile preview, evaluate, authorize under policy, execute/reconcile |
| `need_context` | A named fact is missing | Resolve an allowlisted fact group, once within budget |
| `request_mechanic` | Desired experience needs an unsupported capability | Persist/deduplicate a development task; do not claim delivery |

Use a discriminated union and reject unknown fields. Each variant has only the fields it needs. For models that cannot handle the union reliably, the host can first select a decision enum and then request the selected variant's small schema. Count both calls against the same budget.

### Input Packet

Host supplies: task ID, session reference, evidence frame ID, current request, applicable explicit notes, active obligations, relevant nearby entities, allowed capability cards, freshness/unknowns, and budget. Relevant history is retrieved by the host. Do not include DB schemas, every native verb, entire chat history, or the entire skill catalog.

Entity references should be short and interpretable, such as `nearby_target_1`, with display name and meaningful facts. They are scoped handles, not trusted permissions. The host resolves them to exact IDs and rechecks current scope before use.

### Example Decision

Illustrative only; these references are not live entities:

```json
{
  "outcome": "propose_beat",
  "evidence_ref": "frame_42",
  "capability_ref": "quest.kill_bounty.v1",
  "target_ref": "nearby_target_1",
  "intent": "Help the militia stop raids on the supply road",
  "objective_text": "Defeat the raiders at the marked supply camp, then return to the captain.",
  "narrative_text": "The last supply cart never reached the hill.",
  "reward_profile_ref": "modest_local_reward",
  "reason": "The player asked for a nearby task and the camp is reachable."
}
```

The capability-specific schema may add bounded creative fields. Objective count, reward amount, IDs, faction restrictions, and exact directions must be supplied or validated from compiler evidence, not trusted because the model wrote plausible values. This example does not authorize a quest compiler to accept unspecified targets or coordinates.

### Proposed Tool Facade For Tool-Capable Models

If tool calling is useful, expose only the operations needed in the current phase:

| Semantic operation | Input | Result |
|---|---|---|
| `get_context` | Host-issued task reference, allowlisted fact group | Small scoped packet with freshness |
| `preview_beat` | Typed proposal referencing supplied handles | Immutable preview reference or typed blockers |
| `submit_beat` | Preview reference | Accepted-for-processing / blocked / awaiting-approval; not "done" |
| `get_result` | Host-issued request reference | Authoritative state and proof refs |
| `request_mechanic` | Experience and missing capability details | Durable task reference or existing duplicate |

The host normally supplies initial context and automatically reconciles results. The model should not poll repeatedly or discover hundreds of tools. `submit_beat` is not a direct mutation: it passes through host policy and fresh validation. Neither arguments nor tool return text can enlarge permissions.

These operation names are design examples. Implement them as adapters to existing owners, then expose them. Do not write a skill telling an agent to invoke them before that implementation exists.

## Predictable Errors And Recovery

Every model-facing error contains `code`, `retryable`, `allowed_next`, and a short explanation. Include field-level errors only when useful; no giant stack trace.

| Code | Correct next step |
|---|---|
| `STALE_CONTEXT` | Host refreshes once; old preview authorization is invalid |
| `MISSING_FACT` | Ask for one named fact group, or defer |
| `UNSUPPORTED_CAPABILITY` | Create/link development task |
| `CLIENT_UPDATE_REQUIRED` | Stage release; explain dependency, do not grant an invisible power |
| `SCOPE_DENIED` | Stop this action; no alternate GUID or tool workaround |
| `SCHEMA_INVALID` | One bounded corrected response if budget remains |
| `SEMANTIC_INVALID` | Return concrete blocker and permitted revision, not permission to fabricate facts |
| `EFFECT_UNCERTAIN` | Host reconciles; never regenerate with a fresh key |
| `POLICY_REVIEW_REQUIRED` | Persist proposal for the authorized reviewer |
| `BUDGET_EXHAUSTED` | Park with next trigger; do not start another agent |

Suggested starting budget, to tune through qualification: at most three model requests per decision, at most one repair, at most one targeted context refresh, and one end-to-end deadline. Every wrapper/retry/editor call consumes the same budget. An editorial call is optional for low-risk routine text and cannot create an unbounded generator/editor conversation.

Do not confuse retries with deliberation. Repeated model sampling cannot repair absent client assets or missing native code.

## Minimal Runtime Instruction

The host can render an instruction of roughly this shape beside the exact current schema:

> Choose one allowed outcome using only the supplied evidence. Use the supplied references exactly. Unknown facts stay unknown. If a capability is missing, request a mechanic. Do not claim that a proposal has already happened. Return only the requested object. The host handles execution and reports results.

This instruction is helpful, not a security boundary. The host must enforce every important rule even when the model ignores it.

## Automatic Development Requests

Missing functionality becomes a durable task automatically under the user's requested workflow. Automatic task creation is not automatic implementation, deployment, or live mutation. A content idea can remain linked and resume after a released capability is available, subject to fresh relevance and player consent where needed.

Host fills a task packet from evidence and compiler failure:

```yaml
task_version: wm.development_request.v1
task_id: host-generated
status: proposed
requested_experience: A thrown strike that consumes this player's owned mark
missing_capability: combat.consume_owned_mark_at_range
origin_request_refs: [host-resolved]
evidence_refs: [host-resolved]
existing_capability_checked: ranged_damage_without_mark_consumption
why_existing_is_insufficient: It cannot enforce mark ownership or consumption
owner_components: [native_spell_runtime, ability_compiler, client_shell_manifest]
allowed_changes: Implement the missing mechanic and its presentation contract
forbidden_changes: No replacement of unrelated stock spells or reward behavior
client_requirements: Visible button, correct range and tooltip, visible mark
server_requirements: Target validation, ownership check, one consumption per hit
acceptance_scenarios:
  - Eligible hit consumes only the caster's mark and applies the documented result
  - Miss, immune target, and another caster's mark do not consume it incorrectly
  - Existing abilities and unrelated auras remain unchanged
rollback_requirements: Disable new grants and remove only owned runtime state
verification_policy: Follow the operator's current authorization for checks
deployment_authority: separate-release-step
```

The host resolves actual repository paths and adds exact symbols where known. Unknown ownership is a triage blocker, not an invented path. Task deduplication uses capability signature plus relevant semantics/version; merge related requests without merging unrelated players' private narrative. Track `proposed -> triaged -> implementing -> review -> released` or `rejected`; the runtime only resumes after a released version passes capability discovery.

Export to the existing issue tracker through an authorized integration when configured. Otherwise keep a local durable task and show it in the panel. Do not lose the task just because GitHub is unavailable.

## Local Coding Agent: A One-Task Work Card

Give the agent one task, not "finish WM". The card contains:

1. The observable result in one sentence.
2. Exact owning files/symbols and the baseline revision/dirty-worktree warning.
3. Inputs, outputs, and invariants that cannot change.
4. The next small edit, with one normal example and one failure example.
5. Authorized verification commands, or an explicit "checks not authorized; report unverified".
6. Stop condition and the exact handoff fields.

Example first assignment: "Investigate why `ControlCoordinator` is missing from the empty owning module; reconstruct the intended implementation without discarding local changes. Do not migrate the director or touch live state." That is materially more manageable than asking a weak agent to implement this entire architecture.

The coding agent's final report is: changed files; behavior changed; checks actually run; remaining blocker; next permitted action. `WORKING` requires applicable proof, `PARTIAL` means incomplete proof or functionality, `BROKEN` means a demonstrated failure, and `UNKNOWN` means insufficient evidence. A tool's successful exit does not prove gameplay.

## Keeping This Cheap

- Load one skill and task-specific references, not every manual.
- Return small typed summaries and evidence references; retain full logs outside the prompt.
- Cache stable capability metadata by version, not mutable player facts indefinitely.
- Resolve IDs, schemas, and candidate filtering in code before asking the model.
- Use deterministic handling for repeated known commands and obligation cleanup.
- Ask for brief decisions, not a long reasoning transcript.
- Escalate difficult tasks only under configured cost/privacy policy; a stronger model still has the same permissions.

Simple tools reduce avoidable errors. They do not make an unqualified model safe: the evaluation gate decides what that model is allowed to do.
