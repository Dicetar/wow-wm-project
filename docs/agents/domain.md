# Domain Docs

Engineering skills use a single domain context for this repository.

## Before exploring

- Read root `CONTEXT.md` when it exists.
- Read ADRs under `docs/adr/` that affect the work.
- If either source is absent, proceed silently. Domain-modeling creates files lazily when terms or durable decisions are resolved.

## Layout

```text
/
|-- CONTEXT.md
|-- docs/
|   `-- adr/
`-- src/
```

## Vocabulary

Use canonical terms from `CONTEXT.md` in issue titles, plans, tests, and code. Do not drift to rejected synonyms. A missing concept may indicate either invented language or a domain-model gap; resolve it through domain-modeling before spreading it.

## ADR conflicts

Surface conflicts with an existing ADR explicitly. Do not silently override a durable decision.
