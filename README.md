# wow-wm-project

An external-first **World Master** platform for **AzerothCore 3.3.5**.

This repository is no longer just a bootstrap. It now contains a working first live-content vertical slice for quests:

- target resolution and lookup translation
- live DB-backed bounty quest generation
- schema-aware quest validation and publish preflight
- rollback snapshots and publish logs
- SOAP-driven runtime sync after publish
- live quest editing for titles and rewards
- reserved-slot utilities for WM-managed ID ranges

## Archived docs

The original bootstrap-era docs are preserved under `docs/archive/`.

Use the archived files if you want the original resolver-first framing:

- `docs/archive/README.bootstrap.md`
- `docs/archive/ROADMAP.bootstrap.md`

## Current project stance

- **External-first**: the WoW server is the runtime target, not the source of truth for project code.
- **Lookup-first**: raw AzerothCore fields should be translated into usable facts before any model sees them.
- **Validation-first**: the LLM never writes directly to the game.
- **Journal-first**: player/NPC history belongs in WM-owned tables, not in core AzerothCore tables.
- **Managed IDs**: live WM content should use reserved-slot ranges instead of improvised IDs.
- **Runtime-aware**: DB publish is not enough; publish and rollback must account for live worldserver reload state.
- **No Eluna dependency** in the first implementation track.

## What works today

### Translation and lookup

- Target Resolver v1
- live DB target profile lookup
- candidate/ranking helpers for DB-backed subject selection
- lookup registries and enum decoding support

### Quest content pipeline

- generate bounty quests from live creature data
- compile quest drafts into SQL using live schema compatibility checks
- validate before publish
- snapshot old rows before apply
- publish to DB with structured result output
- trigger SOAP runtime reload commands after publish
- edit live quest title / rewards / reward text
- inspect and compare generated quests against known-good quest rows
- rollback a published quest to the latest stored snapshot

### Slot / registry groundwork

- reserved-slot models and allocator utilities
- DB-backed reserved slot allocator
- quest publishing requires a managed reserved slot
- duplicate quest-title protection for the same questgiver
- reserved-slot seeding utility for WM-owned ID ranges

## Bootstrap SQL

The WM bootstrap SQL now owns these major table families:

- journal / enrichment tables
- publish log and rollback snapshots
- reserved ID range table for managed quest/item/spell slots

Apply:

```bash
mysql -u root -p acore_world < sql/bootstrap/wm_bootstrap.sql
```

## Quick start

### 1. Create a virtualenv and install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
```

### 2. Configure `.env`

Set at minimum:

```dotenv
WM_WORLD_DB_HOST=127.0.0.1
WM_WORLD_DB_PORT=3306
WM_WORLD_DB_NAME=acore_world
WM_WORLD_DB_USER=root
WM_WORLD_DB_PASSWORD=

WM_SOAP_ENABLED=1
WM_SOAP_HOST=127.0.0.1
WM_SOAP_PORT=7878
WM_SOAP_USER=soap
WM_SOAP_PASSWORD=soap
WM_SOAP_PATH=/
```

### 3. Seed a reserved quest range

```bash
python -m wm.reserved.seed --entity-type quest --start-id 910000 --end-id 910099 --mode apply --summary
```

### 4. Generate a bounty quest draft

```bash
python -m wm.quests.generate_bounty --questgiver-name "Marshal McBride" --target-name "Kobold Vermin" --quest-id 910005 --summary
```

### 5. Publish it live with runtime sync

```bash
python -m wm.quests.live_publish --draft-json .\artifacts\generated_bounty.json --mode apply --runtime-sync auto --summary --output-json .\artifacts\generated_bounty_live_apply.json
```

### 6. Edit it live

```bash
python -m wm.quests.edit_live --quest-id 910005 --title "Marshal's Bonus Kobold Bounty" --reward-money-copper 2400 --reward-item-entry 6948 --reward-item-count 1 --reward-xp 4 --mode apply --runtime-sync auto --summary
```

### 7. Roll it back

```bash
python -m wm.quests.rollback --quest-id 910005 --mode apply --runtime-sync auto --summary --output-json .\artifacts\quest_910005_rollback.json
```

## Current operational rule

For fresh quests and major objective behavior changes:

> publish / rollback to DB, send runtime reload commands, and still be ready to restart worldserver if live behavior is stale.

The project treats runtime sync as a real step, not an optional cosmetic extra.

## What is next

The next development focus is:

1. stabilize the quest platform
2. harden rollback and slot governance
3. make generation context-aware using resolver + journal data
4. expand from quests into safer item-slot workflows

See `docs/ROADMAP.md` for the current plan.
