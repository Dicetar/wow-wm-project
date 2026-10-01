Status: DESIGN_ONLY
Last verified: 2026-09-23
Verified by: Codex
Doc type: design

# WM Redesign: Tools, Skills, and Review Method

Follow-up: [WM Rebuild Plan](REBUILD_PLAN.md) now contains the selected architecture, migration, implementation packets, and player-experience acceptance gates. This document remains the discovery record.

## Decision

Start the redesign with the existing WM workflows. Trial Serena for semantic code navigation and Context7 for dependency documentation when needed. Use two inspected community skills as design references: persistent memory and agent evaluation. Do not install a large agent framework or skill bundle to begin the review.

Tool discovery is complete for this first phase. This document is not a completed architecture review, implementation plan, or gameplay-readiness claim. No new MCP or skill was installed or registered. The existing September plan remains intact.

## Product Anchor

WM is a player-following World Master, not just a chat interface, bounty generator, or operator panel. The intended experience is:

```text
Observe play -> interpret evidence and intent -> retrieve relevant memory
-> choose whether to intervene -> create feasible content -> editorial review
-> validate and publish -> observe actual consequences -> update memory
```

This is a product flow, not a requirement for eight independent agents or eight model calls. Sensory interpretation, creative authoring, and editorial judgment need explicit responsibilities; deterministic code must still enforce execution contracts.

Preserve the agreements in [CONTEXT.md](../../../CONTEXT.md): policy-bounded autonomy, supported content, development requests, shared-world continuity, deliberate quest transitions, initiative presets, and scoped Author's Notes. Supported actions do not need per-action confirmation. New mechanics, client patches, and restarts remain staged under the agreed rules.

Start the later code audit from [the September 14 work index](../wm-autonomous-director-v1/README.md), its [specification](../wm-autonomous-director-v1/SPEC.md), and [assessment](../wm-autonomous-director-v1/ASSESSMENT.md). They record a PRD and 15 tickets. Their test and service results are historical, not results from this session. Reconcile and revise that work instead of silently creating a competing backlog.

## Separate Three Things

| Layer | Purpose | Boundary |
| --- | --- | --- |
| Coding-agent skills | How we investigate, design, implement, and verify WM | Instructions, not product functionality |
| Development MCPs | Give the coding agent access to code navigation, documentation, or traces | Tool availability does not establish correctness |
| WM runtime capabilities | What the in-game director can actually observe and cause | Typed contracts, policy, native support, client presentation, and evidence |

Adding an MCP to Codex does not give WM new senses or mechanics. No proposed development integration should become a required game-runtime dependency by accident.

## MCP Assessment

| Integration | Finding | Recommendation |
| --- | --- | --- |
| Deploychan | Direct HTTP JSON-RPC discovery and read calls succeeded; server reported `deploychan` version `1.30.0` | Keep as optional discovery/reference source |
| Serena | Official documentation describes symbol/reference navigation and Python/C++ support; not tested against WM | Highest-value optional code-audit trial |
| Context7 | Official documentation describes version-specific library documentation retrieval; not connected here | Useful when dependency/API questions arise |
| GitHub | Existing connector and repository tracker already available | Reuse; no duplicate tracker setup |
| Langfuse | Authenticated data MCP exists, with read and write operations | Defer until instrumented LLM runs justify trace tooling |
| OpenAI Docs | Public documentation MCP exists | Conditional on OpenAI-specific integration work; not a reason to replace LM Studio |

### Deploychan: What Was Actually Tested

Endpoint: [user-supplied Deploychan MCP](https://mcp.deploychan.webcam/mcp).

- `initialize` and `tools/list` succeeded through direct HTTP, not an installed Codex connector.
- Seven advertised tools: `search_knowledge`, `get_item`, `list_skills`, `get_skill`, `onboard`, `next_step`, `list_recommended`.
- Read calls exercised: `list_skills`, `search_knowledge`, and `get_item`.
- The ten returned skill packs mainly concerned installation, voice, social content, image workflows, notes, and agent tooling. None directly covered WM's player-driven director and gameplay verification problem.
- Search produced potentially useful context/evaluation research leads, but also unverified claims. Validate leads against original sources; do not treat curation as proof.
- Only generic discovery queries were sent. No repository contents or credentials were uploaded. Returned instructions were treated as external content, not authority.

Verdict: discovery surface **WORKING** for the calls above; content trust and suitability require item-by-item review. Not a code-analysis engine or a replacement for WM's runtime.

### Candidate Acceptance Checks

**Serena:** start with read-oriented exploration. Check the actual Windows language-server setup and native compile configuration. Trial finding a Python publisher, its callers, a C++ action handler, and its registration. Compare results with `rg` and source reads. Exclude generated lab/build/vendor trees. Keep only if navigation improves materially. Serena's own guidance recommends its official setup rather than marketplace recipes. [Official project](https://github.com/oraios/serena), [language support](https://oraios.github.io/serena/01-about/020_programming-languages.html).

**Context7:** resolve an actual dependency/version and verify a retrieved API example against the installed version. It is a documentation aid, not an authority on WM's patched AzerothCore branch. Keep private code and secrets out of queries. Official web documentation remains the fallback. [Official MCP documentation](https://github.com/upstash/context7/blob/master/packages/mcp/README.md).

**Langfuse:** first define correlation from source event through model run, draft, editorial decision, publication, and native result. Instrument only what is needed, with redaction and retention rules. Its MCP is not read-only by default; restrict write tools for analysis. The vendor also recommends its skill/CLI in suitable shell environments, so MCP is not mandatory. [Official MCP documentation](https://langfuse.com/docs/api-and-data-platform/features/mcp-server).

## Existing Skills to Use

Load the narrowest workflow for the current step, not every skill at session start.

| Skill | Role and expected output |
| --- | --- |
| `wm-workflow` | Repo evidence, dirty-worktree preservation, truthful status, bounded changes |
| `domain-modeling` | Agreed vocabulary and ownership of facts, notes, intentions, capabilities, consequences |
| `codebase-design` | Identify existing modules worth deepening rather than duplicating |
| `gameplay-architecture` | State ownership, native/Python boundaries, lifecycle and recovery design |
| `design-an-interface` | Compare alternative sensory/director/editorial interfaces before choosing |
| `wm-content-release` | Feasibility, typed proposals, required visible content fields, release boundaries |
| `wm-live-bridge-lab` | Actual sensing/action/gameplay proof and lab discipline |
| `research` | Focused unresolved technical questions, primary sources, saved conclusions |
| `diagnosing-bugs`, `tdd`, `code-review` | Implementation-stage diagnosis, regression tests, and review |

Use `ask-matt` as a router when useful, not a reason to restart setup or re-interview accepted decisions. Caveman changes communication length, not technical rigor or artifact completeness.

The installed generic `architecture-review` workflow assumes a GDD/studio directory structure that WM does not use. Borrow its requirement-to-decision traceability method; do not impose unrelated engine setup or documentation scaffolding. `writing-shape` is an article-development workflow, not the right driver for this architecture task.

## External Skills: Source-Inspected Shortlist

Discovery used skills.sh and `npx skills find` for context engineering and LLM evaluation, followed by direct inspection of the actual `SKILL.md` sources. Popularity is a discovery signal, not a correctness or security guarantee.

| Candidate | Useful material | WM-specific caveat | Decision |
| --- | --- | --- | --- |
| [memory-systems](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/blob/main/skills/memory-systems/SKILL.md) | Persistent identities, temporal validity, retrieval, consolidation | Do not adopt a graph database by default. Newer inferred facts cannot override authoritative observations or firm notes. Critical execution records must be durable, even if optional semantic memory can retry asynchronously | Primary design reference |
| [agentic-eval](https://github.com/github/awesome-copilot/blob/main/skills/agentic-eval/SKILL.md) | Separate generator/evaluator responsibilities, rubrics, bounded revision | A model PASS is not proof. Failed validation or exhausted revisions must not fall through to publication. Test player outcomes independently | Primary editorial/evaluation reference |
| [context-engineering](https://github.com/addyosmani/agent-skills/blob/main/skills/context-engineering/SKILL.md) | Focused context, restartable handoffs, preserving scope and verification | Mostly overlaps existing repo rules. Avoid its blanket clarification gates and heuristic context thresholds as mandatory policy | Reference only; no installation needed now |

Discovery snapshot on 2026-09-23: GitHub `agentic-eval` had about 10.3K listed installs and its parent repository 39.3K stars; Addy Osmani's `context-engineering` about 39.8K installs and its parent repository 98.7K stars; the memory-systems parent repository about 18.0K stars. The context-engineering collection's 3.9K installs were not an individual memory-systems install count. Counts are dated signals and do not rank WM suitability.

Do not activate entire collections, vendor memory stacks, recursive inference systems, or multi-agent frameworks merely because they appear in these references. Inspect licenses, pinned revisions, bundled scripts, and dependencies before later adoption.

## Missing WM-Specific Methods

These are proposed additions to existing project workflows, not implemented skills or new runtime modules:

1. **Director design review:** trace a player experience through evidence, interpretation, timing, generation, editorial checks, supported execution, and consequence. Include doing nothing as a legitimate outcome.
2. **Scenario evaluation:** replay whole sessions; check identity, freshness, continuity, feasibility, pacing, persistence, and player-visible results. Use human-calibrated rubrics for narrative quality, deterministic assertions for safety and state.

Prefer adding concise checklists to the existing skills after the architecture audit. Create separate skills only if the workflows are repeatedly useful and have distinct ownership.

Minimum scenarios for the future evaluation set:

- Player changes zone or disconnects while a draft is being generated.
- Duplicate events, retries, or restart occur after publication but before acknowledgement.
- An inferred preference conflicts with a Character or World Author's Note.
- A requested power needs an unavailable native mechanic or client asset.
- A shared-world event affects accepted quests and an offline character.
- On Demand prevents unsolicited new experiences but continues existing obligations.
- Editorial review rejects an attractive but infeasible or repetitive proposal.
- Publishing succeeds at the API layer but the grant, visible presentation, or gameplay behavior fails.

## Method for the New Draft

1. **Recover intent:** produce a short product brief from user decisions, `CONTEXT.md`, roadmap, and September spec. Separate accepted requirements from historical implementation compromises.
2. **Audit actual flow:** inspect `src/wm/`, `control/`, native bridge/spell modules, tests, and operational entrypoints. Map ownership and record file/line evidence. Recheck important historical claims before promoting them to current status.
3. **Build an evidence matrix:** requirement -> existing code -> missing behavior -> automated test -> live proof. Use `WORKING`, `PARTIAL`, `BROKEN`, `UNKNOWN`; do not invent completion percentages.
4. **Compare architecture options:** explicit staged director within the existing service; a more consolidated director with strict validation; durable worker separation if failure/recovery needs warrant it. Compare latency, context quality, state ownership, retry behavior, cost, and operational burden. Do not select an agent count first.
5. **Draft contracts and failure handling:** sensory evidence versus inference; persistent notes versus memory; feasible capability reporting; bounded editorial revisions; execution idempotency; continuity/compensation; model timeout and unavailable-model behavior.
6. **Write migration decisions:** keep, repair, replace, retire. Link changes to existing tickets before adding new ones. Preserve working publishers/action bus unless concrete evidence supports a replacement.
7. **Define a first end-to-end proof:** actual play produces a grounded, generated, reviewed, published experience whose outcome is observed and survives recovery. A successful demo must not silently narrow the eventual product to bounty generation.

Expected next deliverable: one navigable redesign draft with the product brief, current-system map, evidence matrix, architecture comparison, chosen decisions, migration order, and acceptance scenarios. New infrastructure is not a prerequisite for writing it.

## Anti-Drift Rules

- Current user direction governs product intent; repository evidence governs claims about implementation. Old release success does not prove the broader director works.
- Keep accepted, proposed, and unknown decisions visibly separate. Never rewrite accepted autonomy into permanent manual approval or unsupported freeform mutation.
- Every recommended subsystem must solve a named failure or requirement and state why existing code cannot do it.
- Preserve provenance: observations, user notes, model inferences, drafts, and execution results are different records with different authority.
- Keep requirement IDs and acceptance scenarios stable across rewrites. Explain removals and scope changes explicitly.
- Separate schema validity, publication acknowledgement, native execution, client visibility, and gameplay success.
- Reuse existing skills and tracker. Do not spend the redesign session on tool setup that does not unblock evidence gathering.
- Do not claim independent agent review if alternatives were compared sequentially by one agent.
- Save concise decisions, evidence paths, exact verification results, unresolved risks, and next work at each handoff. Keep `AGENTS.md` a router, not an expanding transcript.
- The user's latest-five log preference concerns disposable diagnostic logs. Do not reinterpret it as permission to delete world state, active obligations, durable execution history, or required recovery evidence.

## Session Scope and Verification

- Changes: this research/design document and a documentation-index link only.
- External activity: documentation/skill-source reads, skill-directory searches, and read-only Deploychan discovery calls. The discovery CLI may use its normal npm cache; no skill pack was installed.
- No service startup, database mutation, gameplay action, commit, push, issue modification, or MCP configuration change.
- No Python/native test suite or live gameplay test rerun. Historical September results remain historical.
- MCP recommendations other than the tested Deploychan calls are **UNKNOWN on this workstation** until connected and checked. The architecture redesign remains **DESIGN_ONLY**.
