# wow-wm-project

An external-first **World Master** platform for **AzerothCore 3.3.5**.

This repository is no longer just a bootstrap. It now contains a working live-content platform across quests, items, spells, and the first deterministic event spine:

- target resolution and lookup translation
- live DB-backed bounty quest generation
- schema-aware quest validation and publish preflight
- rollback snapshots and publish logs
- SOAP-driven runtime sync after publish
- live quest editing for titles and rewards
- managed item-slot and spell-slot publishers
- reserved-slot utilities for WM-managed ID ranges
- canonical event storage, polling, projection, rules, planning, and execution

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

### Item and spell slot pipelines

- managed item publish groundwork
- managed spell publish groundwork
- quest reward flow that can attach managed items
- reserved-slot models and allocator utilities across quest/item/spell ranges

### Event spine groundwork

- canonical WM event log
- DB-first event polling adapter
- journal projection from canonical events
- deterministic reaction rules with cooldowns
- reaction planner and executor that call the existing quest/item/spell publishers

## Bootstrap SQL

The WM bootstrap SQL now owns these major table families:

- journal / enrichment tables
- canonical event, cursor, cooldown, and reaction log tables
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

Optional event-spine defaults for auto-generated repeat-hunt follow-ups:

```dotenv
WM_EVENT_DEFAULT_QUESTGIVER_ENTRY=1498
WM_EVENT_FOLLOWUP_KILL_COUNT=6
WM_EVENT_DEFAULT_REWARD_MONEY_COPPER=1400
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

### 8. Run the deterministic event spine

```bash
python -m wm.events.run --adapter db --mode dry-run --summary
```

If `WM_EVENT_DEFAULT_QUESTGIVER_ENTRY` is configured and a free managed quest slot exists, repeat-hunt opportunities can now plan a real bounty quest draft instead of falling back to a no-op.

For focused live-safe checks, you can scope the run to one player and override the default questgiver for that run:

```bash
python -m wm.events.run --adapter db --mode dry-run --player-guid 5406 --questgiver-entry 197 --summary
```

Live apply is intentionally guarded. To publish from the event spine, scope the run to one player and confirm the live mutation explicitly:

```bash
python -m wm.events.run --adapter db --mode apply --player-guid 5406 --questgiver-entry 197 --confirm-live-apply --summary
```

## Operational notes

When you need to restore or wipe WM-generated quest IDs, use:

- `docs/CLEANUP_PLAYBOOK.md`

That note documents the practical difference between rollback and purge, the runtime/client cleanup ladder, and the PowerShell-specific cleanup pitfalls we already hit.

## Current operational rule

For fresh quests and major objective behavior changes:

> publish / rollback to DB, send runtime reload commands, and still be ready to restart worldserver if live behavior is stale.

The project treats runtime sync as a real step, not an optional cosmetic extra.

## What is next

The next development focus is:

1. finish hardening the deterministic event spine
2. use that spine to unlock smart contextual reactions
3. keep improving quest / item / spell platform safety where the spine depends on it
4. defer demo selection until the reusable bricks are in place

See `docs/ROADMAP.md` for the current plan.
