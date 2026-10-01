Status: PARTIAL
Last reviewed: 2026-09-30
Evidence: primary documentation; no comparative benchmark
Doc type: research / decision proposal

# Technology Selection

## Selection Criteria

The target is a Windows-operated WoW 3.3.5a installation with an existing Python control plane and C++ worldserver modules, not a generic cloud agent demo. Rank technologies by correctness of external effects, fit with current code, local-model interoperability, operator burden, inspectability, and reversible adoption. Model quality and throughput remain unmeasured on this host.

Separate four decisions: model inference, model-call orchestration, durable business state, and native effect execution. A package that solves one does not automatically solve the others.

## Orchestration Shortlist

| Option | What it could replace | WM judgment | Adoption decision |
|---|---|---|---|
| Explicit Python state machine + Pydantic | Ad hoc lifecycle branches | Small dependency cost; WM must implement transaction/recovery rules correctly | Select for director lifecycle now |
| Pydantic AI core | Provider calls, typed outputs, bounded model interaction | Fits existing Python/Pydantic; useful adapter, not the game authority | Preferred clean-sheet model SDK; bounded current-stack trial |
| LangGraph | Branching model workflows and checkpoints | Valuable if graph state/checkpoint inspection becomes the dominant problem; overlaps current director concepts | Defer, not stack alongside another workflow engine |
| Temporal | Durable long-lived workflow scheduling/replay | Strong candidate for many durable waits, workers, or realms; additional runtime and versioning obligations | Conditional later adoption, not first repair |
| General coding-agent harness | Open-ended code/research tasks | Appropriate for development tickets, not live game authority | Keep outside runtime WM |

Pydantic AI documents typed output modes and application output validators. Prompt-only structured output is less reliable than native/tool output, and schema dictionaries do not necessarily provide the same validation as typed models. Use explicit Pydantic models and semantic validators; do not interpret a framework object as proof of safe content. Its usage limits can bound model activity, but WM must also bound wall-clock time and cumulative retries across wrappers. [Output](https://pydantic.dev/docs/ai/core-concepts/output/), [agents](https://pydantic.dev/docs/ai/core-concepts/agent/).

LangGraph provides checkpointed state. Its documentation describes persistence, while its graph reference explains that resumed nodes can restart from the beginning. That makes side-effect placement and idempotency important. A graph checkpoint is not an atomic transaction with WoW inventory. WM already needs its own action receipts regardless of graph adoption. [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [graph reference](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/graph-api.mdx).

Temporal distinguishes deterministic workflow code from activities that perform external work. Activity retries still require idempotent external effects. If selected later, place model calls and bridge interactions in activities, keep recorded decisions immutable, and plan workflow-code versioning before deployment. Do not put blocking LLM calls in worldserver updates. [Workflow definition](https://docs.temporal.io/workflow-definition), [activity definition](https://docs.temporal.io/activity-definition).

Pydantic AI also documents durable-backend integrations. That makes a future adapter feasible; it is not a reason to deploy all supported backends. [Durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/).

### Why Not Adopt An Entire Harness Framework Now?

The present failures include empty local source, nontransactional lifecycle edges, and uncertain native retries. A new framework will not repair these. First formalize the domain contract and the effect boundary; then replace a measured weak component behind an interface. Anthropic's distinction between predefined workflows and model-directed agents is useful here: WM needs creative model decisions inside a largely predetermined release workflow. Its early article explicitly notes that the tooling landscape has changed; use the principle, not its old package list. [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

This is not a blanket anti-framework position. For a fresh implementation, Pydantic AI and FastAPI remove routine plumbing. For this repo, adopt only where replacing existing complexity has a clear benefit and regression gate.

## Persistence And Delivery

**Current stack:** retain the current MySQL-compatible installation and PyMySQL for incremental ledger work. Use a WM-owned schema or explicitly owned tables, versioned migrations, real transactions, unique constraints, and compare-and-set revisions. Verify the deployed database version/engine before relying on version-specific SQL.

**Clean sheet:** choose MySQL/InnoDB on the existing game database service for the first single-installation product, with separate credentials/ownership for WM. Prefer SQLAlchemy Core for repository/transaction plumbing and explicit migrations for WM tables. Do not put core-owned AzerothCore tables under automatic ORM migration. This choice minimizes an extra operating service; it is not a claim that MySQL is universally better than PostgreSQL.

**PostgreSQL alternative:** sensible if the director becomes independently hosted or the selected durable engine requires it. That adds another store and a cross-database delivery boundary. Do not introduce it merely to obtain a vector extension. **SQLite alternative:** useful for isolated fixtures, exports, or single-process prototypes; avoid making it an additional authoritative ledger beside the current bridge without a specific deployment reason.

MySQL documents row locking and `SKIP LOCKED` for queue-like access, with caveats about inconsistent views. Use exact deployed-version semantics, indexes, bounded transactions, and verified claim ownership; never assume that selecting a pending row grants ownership. SQLAlchemy documents row-count checks useful for conditional updates. Neither substitutes for correct state transitions. [MySQL locking reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html), [SQLAlchemy updates](https://docs.sqlalchemy.org/en/20/tutorial/data_update.html).

Adopt the **transactional outbox** principle: record state change and intended dispatch together. A relay may deliver more than once, so consumers must deduplicate. An inventory save and a separate world DB receipt are still not one transaction. WM needs per-action reconciliation/entitlements, not an unsupported claim of exactly-once execution. [Outbox](https://microservices.io/patterns/data/transactional-outbox.html), [idempotent consumer](https://microservices.io/patterns/communication-style/idempotent-consumer.html).

Do not add Redis, Kafka, or a separate task broker to the initial design. Add a broker only after measured database-queue contention, fan-out, or operational needs justify a second delivery system. One application and a database-backed worker are enough to establish the product contract.

## Model Serving And Qualification

| Candidate | Place in WM | Decision |
|---|---|---|
| Existing LM Studio | Current local development/operator endpoint | Keep; qualify actual model/backend/schema combination |
| llama.cpp server | Headless local inference alternative | Trial when service operation or resource control needs it |
| vLLM | Dedicated inference host with suitable hardware/concurrency | Defer until throughput measurements justify it |
| Remote model provider | Optional escalation/editor/development task | Explicit opt-in for cost and data transfer; never automatic authority escalation |

LM Studio exposes JSON-schema response formatting but warns that not all models handle it adequately. llama.cpp supports a subset of JSON Schema through grammar conversion. vLLM documents structured-output backends. Therefore the deployment record must include model identifier, quantization, inference build, schema mode, context/output limits, and qualification results; an OpenAI-compatible URL alone is insufficient. [LM Studio](https://lmstudio.ai/docs/developer/openai-compat/structured-output), [llama.cpp grammar support](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md), [vLLM structured output](https://docs.vllm.ai/en/v0.21.0/features/structured_outputs/).

No particular model size or brand is selected without host inventory and WM scenario results. Start with the user's installed local model. Route tasks by demonstrated ability: intent extraction, constrained beat selection, narrative writing, editorial review. If a model cannot qualify for live proposals, it can still draft text or create a development request.

Cost measures: accepted useful experiences per model-minute, tokens per validated proposal, repairs per task, and operator correction time. Local inference is not free just because it has no per-token bill. Do not claim percentage savings without a measured baseline.

## Operator API And UI

Keep the current panel while fixing lifecycle truth. Clean-sheet selection: **FastAPI + Pydantic API**, a small operator frontend, and durable worker state exposed through ordinary endpoints. FastAPI generates OpenAPI/JSON Schema from typed models, reducing API/schema duplication. It does not provide WM authorization or execution correctness for us. [FastAPI features](https://fastapi.tiangolo.com/features/).

Use the existing plain JS interface first; a frontend-framework rewrite is not a prerequisite. The important screen is a selected-session timeline with readiness, current intent, pending/active obligations, development tasks, client compatibility, uncertain effects, and proof. If client state management later warrants a framework, decide separately using actual UI complexity.

Default to loopback. Remote access requires authenticated transport, origin/CSRF controls as applicable, scoped roles, and secret redaction. A reverse proxy or tunnel is not authorization. Neither a model instruction nor a tool's friendly description may grant operator authority.

## Tools, MCP, And Skills

Expose semantic operations, not one tool per SQL table. Small grouped tools and concise relevant results reduce selection and context burden; tool ergonomics must be evaluated with the target model, not assumed. [Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents).

MCP is an optional adapter for coding agents/operator clients. It is not the internal bus, permission system, durable scheduler, or proof system. Tool annotations are hints and external content is untrusted. Keep authorization in WM and transport identity in the adapter; do not enable arbitrary discovered servers for runtime WM. [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

Agent Skills supports metadata-first loading and task-specific instructions/resources. Adopt that packaging, with WM's stricter two-field frontmatter convention. The runtime decision model should not need to load repository skills to understand a tool. [Agent Skills specification](https://agentskills.io/specification).

Use existing `wm-workflow`, `wm-content-release`, and `wm-live-bridge-lab`; add only the short `wm-harness-task` developer protocol from this work. `wm-skill-intake` already adapts Deploychan's selective-intake method. Deploychan remains a discovery source, not a live dependency. Pydantic's official [coding-agent skills](https://pydantic.dev/docs/ai/overview/coding-agent-skills/) are an implementation-time candidate if its SDK is adopted, not installed or necessary now. Temporal skills are similarly conditional.

## Memory, Telemetry, And Evaluations

Keep structured Author's Notes, player obligations, world consequences, and evidence-backed episodic memory in relational records. Retrieve by player/world scope, entity, time, active arc, and relevance. Start with exact/lexical retrieval. Add embeddings only after a measured retrieval failure set demonstrates need; semantic similarity must never replace scope, authority, or freshness filters.

Use structured local traces with request/effect IDs immediately. Add OpenTelemetry instrumentation when integrating the consolidated lifecycle; keep WM's stable event vocabulary separate from evolving GenAI attribute conventions. Exporting to a hosted dashboard is optional and privacy-sensitive. [OpenTelemetry GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/).

Evaluate environment outcomes, not just persuasive transcripts. Combine deterministic checks, a calibrated editorial rubric, and live player-visible proof. Model judges cannot certify inventory transactions or client DBC correctness. [Agent evaluations](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

## Reconsideration Triggers

- Adopt Temporal when durable timers, versioned long-lived workflows, and multiple workers are consuming more engineering than the product, after an operational prototype and failure-recovery evaluation.
- Adopt LangGraph only if graph inspection/checkpoint branching demonstrably simplifies the director beyond the existing state machine; do not add it just to draw diagrams.
- Adopt Pydantic AI in the current stack when a bounded provider adapter trial improves correctness/maintenance without increasing retries or changing the release contract.
- Add a retrieval service only when scoped SQL/lexical retrieval misses known relevant facts in a measured dataset.
- Change inference server only after measuring the actual workload, hardware fit, and schema/semantic success.

These are decision gates, not simultaneous roadmap tasks.
