# wow-wm-project

An external-first **World Master** platform for **AzerothCore 3.3.5**.

This repository starts with the first hard dependency the rest of the project needs:

- a local configuration layer
- bootstrap SQL for WM-owned tables
- a **Target Resolver v1**
- a Windows deployment guide
- a phased roadmap grounded in your actual AzerothCore exports

## Current stance

- **External-first**: the WoW server is the runtime target, not the source of truth for project code.
- **Lookup-first**: raw AzerothCore fields should be translated into usable facts before any model sees them.
- **Journal-first**: player/NPC history belongs in WM-owned tables, not in core AzerothCore tables.
- **No Eluna dependency** in the first implementation track.

## What is in this bootstrap

- `docs/ROADMAP.md` — phased roadmap from lookup ingestion to live publishing
- `docs/DEPLOYMENT_WINDOWS.md` — setup guide for a Windows machine
- `sql/bootstrap/wm_bootstrap.sql` — WM-owned journal and enrichment tables
- `src/wm/...` — Python package with a working resolver CLI
- `tests/test_target_resolver.py` — basic unit coverage for resolver behavior
- `data/lookup/sample_creature_template_full.json` — small sample lookup dataset

## First practical milestone

The first real vertical slice is:

> resolve a creature entry into a clean, LLM-ready target profile

That profile is what later quest generation, journal summarization, and event reactions will build on.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
python -m wm.main resolve-target --entry 1498 --lookup data/lookup/sample_creature_template_full.json
```

## Example output

```json
{
  "entry": 1498,
  "name": "Bethor Iceshard",
  "mechanical_type": "HUMANOID",
  "faction_id": 68,
  "service_roles": [
    "QUEST_GIVER"
  ]
}
```

## Immediate next implementation steps

1. replace the sample lookup JSON with your real export
2. add DB-backed enrichment lookup
3. add DB-backed player journal lookup
4. expose resolver output to later prompt-building code
5. add a publish pipeline for generated quests
