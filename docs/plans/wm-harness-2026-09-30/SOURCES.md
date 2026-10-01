Status: PARTIAL
Last reviewed: 2026-09-30
Evidence: primary-source research register
Doc type: reference

# Research Sources And Limits

Access date for this register: 2026-09-30. Sources describe general mechanisms; WM recommendations are our engineering synthesis, not vendor certification. No external benchmark is treated as a prediction of local WM performance. Mutable docs should be rechecked and dependency versions pinned at implementation time.

## Primary Sources

| Source | Used for | Important limit |
|---|---|---|
| [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Workflow versus agent distinction; start with simple composition | Originally 2024; page itself warns tooling has changed |
| [Anthropic: Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) | Semantic tool design, concise results, model-specific evaluation | Vendor experience, not a guarantee for weak local models |
| [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Incremental tasks and explicit continuation evidence | Coding-agent examples; not a WoW runtime transaction design |
| [Anthropic: Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Distinguishing transcript, grader, and actual outcome | Model graders still need calibration |
| [Pydantic AI: Output](https://pydantic.dev/docs/ai/core-concepts/output/) | Typed output and validation modes | Syntax/typing does not establish gameplay feasibility |
| [Pydantic AI: Agents](https://pydantic.dev/docs/ai/core-concepts/agent/) | Model-run limits and adapter selection | Total WM budget must include wrappers and retries |
| [Pydantic AI: Durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/) | Integration options, not a required all-in-one architecture | External effect safety still belongs to WM/native handlers |
| [Pydantic: Coding-agent skills](https://pydantic.dev/docs/ai/overview/coding-agent-skills/) | Implementation-time skill candidate | Not installed as part of this research |
| [LangGraph: Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Checkpointed workflow state | Cannot atomically commit WoW effects |
| [LangGraph: Official graph reference](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/graph-api.mdx) | Node restart/idempotency implications | Source is mutable; inspect the chosen release |
| [Temporal: Workflow definition](https://docs.temporal.io/workflow-definition) | Determinism, replay, versioning responsibility | Extra runtime/operational design required |
| [Temporal: Activity definition](https://docs.temporal.io/activity-definition) | External work and retry semantics | Does not make inventory grants exactly once |
| [LM Studio: Structured output](https://lmstudio.ai/docs/developer/openai-compat/structured-output) | Local schema output and model limitations | Actual model/backend must be qualified |
| [llama.cpp: Grammars](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) | Subset support for JSON Schema constraints | Grammar validity is not semantic truth |
| [vLLM: Structured outputs](https://docs.vllm.ai/en/v0.21.0/features/structured_outputs/) | Dedicated-serving alternative | Versioned reference, not a recommendation to install that version |
| [MySQL: Locking reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) | Transactional queue-claim design | 8.4 reference; deployed version was not queried |
| [SQLAlchemy: Update/delete](https://docs.sqlalchemy.org/en/20/tutorial/data_update.html) | Conditional update/row-count handling | ORM/library cannot invent correct concurrency invariants |
| [Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html) | Atomic intent persistence and delivery boundary | Relay can duplicate; world effect still requires reconciliation |
| [Idempotent consumer](https://microservices.io/patterns/communication-style/idempotent-consumer.html) | Durable deduplication principle | Processed ID must align with actual effect transaction |
| [FastAPI: Features](https://fastapi.tiangolo.com/features/) | Typed API/OpenAPI option for clean sheet | Not selected for an immediate panel rewrite |
| [MCP: Tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | Interoperability and tool annotation limits | Transport protocol is not authorization |
| [Agent Skills specification](https://agentskills.io/specification) | Progressive disclosure and skill packaging | WM frontmatter convention is deliberately narrower |
| [OpenTelemetry: GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/) | Trace vocabulary/interoperability | Several conventions are evolving; keep WM event semantics stable |

## Local Evidence

See [current system](CURRENT_SYSTEM.md) for exact code owners and observed defects. Product authority comes from [CONTEXT.md](../../../CONTEXT.md), [required content fields](../../CONTENT_REQUIRED_FIELDS.md), [ADR 0008](../../adr/0008-durable-player-experience-director.md), the [September plan](../wm-redesign-2026-09-23/REBUILD_PLAN.md), and direct user requirements.

Prior Deploychan intake is documented in [.agents/skills/wm-skill-intake/SKILL.md](../../../.agents/skills/wm-skill-intake/SKILL.md). This research does not claim another MCP installation or make Deploychan a runtime dependency.

## How To Challenge This Recommendation

Bring a concrete competing implementation against the same scenarios: restart with an outstanding reward, lost native receipt, conflicting notes, unsupported mechanic, stale client payload, and a weak local model. Compare correctness, useful outcomes, debugging effort, and operator burden. A library's popularity or a more elaborate architecture diagram is not sufficient evidence.

Open questions: actual host/model resource envelope, desired simultaneous players/realms, remote access requirements, deployed DB/core versions, and the runnable baseline after restoring the coordinator. These affect sizing and rollout, not the central separation of creative decisions from deterministic effects.
