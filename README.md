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
- canonical event storage, polling, projection, rules, planning, execution, inspection, and preview
- hidden addon-channel ingestion through `WMOps.log` as the primary live event source
- raw client combat-log tailing as a fallback/debug event source
- shared ref models for players, creatures, NPCs, quests, items, and spells

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
- hidden addon-log adapter backed by AzerothCore addon-message logging
- journal projection from canonical events
- deterministic reaction rules with cooldowns
- reaction planner and executor that call the existing quest/item/spell publishers
- read-only inspect and preview commands for operator visibility
- reusable reactive bounty rules with direct quest grant
- player quest runtime-state polling against the characters DB
- kill-burst suppression while the reactive quest is active, complete, or still cooling down after reward
- raw combat-log ingestion through `WoWCombatLog.txt` as a fallback/debug source

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

Optional combat-log source defaults:

```dotenv
WM_COMBAT_LOG_PATH=D:\\WOW\\world of warcraft 3.3.5a hd\\Logs\\WoWCombatLog.txt
WM_COMBAT_LOG_BATCH_SIZE=200
WM_COMBAT_LOG_PLAYER_NAME=Jecia
```

Optional hidden addon-log source defaults:

```dotenv
WM_ADDON_LOG_PATH=D:\\WOW\\Azerothcore_WoTLK_Repack\\logs\\WMOps.log
WM_ADDON_LOG_BATCH_SIZE=200
WM_ADDON_CHANNEL_NAME=WMBridgePrivate
WM_ADDON_PREFIX=WMBRIDGE
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

### 9. Install a reusable reactive bounty

This flow creates one stable quest definition that is granted directly to the player when WM detects a kill burst. The first safe default is scoped to `5406`, uses `Kobold Vermin` (`6`) as the trigger subject, and turns in to `Marshal McBride` (`197`).

```bash
python -m wm.reactive.install_bounty --player-guid 5406 --subject-entry 6 --quest-id 910000 --turn-in-npc-entry 197 --kill-threshold 4 --window-seconds 120 --post-reward-cooldown-seconds 60 --mode apply --summary
```

Reactive bounty behavior:

- quest `910000` is reusable and marked repeatable
- it has no `creature_queststarter` row
- it keeps `Marshal McBride` as the `creature_questender`
- event processing grants it directly through SOAP instead of publishing a fresh quest ID
- retrigger is suppressed while the quest is active, complete-but-not-turned-in, or inside the post-reward cooldown window

### 10. Use the hidden addon-log source for live kill bursts

The primary live source is now the hidden addon-channel bridge:

- `WMBridge` addon emits hidden addon messages on a private custom channel
- AzerothCore writes that traffic into `WMOps.log`
- WM tails `WMOps.log` through the `addon_log` adapter

Install the addon by copying [WMBridge.toc](D:/WOW/wm-project/wow_addons/WMBridge/WMBridge.toc) and [WMBridge.lua](D:/WOW/wm-project/wow_addons/WMBridge/WMBridge.lua) into:

```text
D:\WOW\world of warcraft 3.3.5a hd\Interface\AddOns\WMBridge\
```

Server-side precondition:

- keep `AddonChannel = 1`
- keep `Logger.chat.addon.msg=4,WMOps`
- keep `Logger.network.soap=4,WMOps`
- keep `Logger.chat.system=4,WMOps`

Read-only source peek:

```bash
python -m wm.sources.addon_log.peek --player-guid 5406 --summary
```

Record canonical kill events from the hidden addon bridge:

```bash
python -m wm.events.poll --adapter addon_log --player-guid 5406 --summary
```

Run the reactive bounty pipeline from addon-log events:

```bash
python -m wm.events.run --adapter addon_log --mode dry-run --player-guid 5406 --summary
python -m wm.events.run --adapter addon_log --mode apply --player-guid 5406 --confirm-live-apply --summary
python -m wm.events.watch --adapter addon_log --mode apply --player-guid 5406 --confirm-live-apply --summary --print-idle --arm-from-end
```

The live loop is:

- `WMBridge` sends `WMB1|type=HELLO` and `WMB1|type=KILL` payloads through the hidden addon channel
- `WMOps.log` is tailed by WM
- `KILL` payloads for `Jecia` (`5406`) become canonical `kill` events
- the kill-burst rule grants quest `910000` directly through SOAP
- `Marshal McBride` stays the turn-in NPC
- runtime-state polling suppresses retrigger while active, complete pending turn-in, or cooling down after reward

The raw combat-log source still exists as a fallback/debug path, but it is no longer the primary live transport.

### 11. Inspect WM state without mutation

Use the read-only operator commands when you want to understand what WM has seen and what it would do next without writing new audit rows.

Inspect recent canonical events, reactions, and active cooldowns:

```bash
python -m wm.events.inspect --player-guid 5406 --summary
```

Preview deterministic plans from the existing canonical event log:

```bash
python -m wm.events.plan --player-guid 5406 --questgiver-entry 197 --summary
```

CLI intent split:

- `wm.events.inspect` = read-only history and cooldown visibility
- `wm.events.plan` = read-only preview of reaction plans and publish preflight
- `wm.events.run --mode dry-run` = operational rehearsal that may still write WM audit rows
- `wm.events.run --mode apply` = guarded live mutation path
- `wm.reactive.install_bounty` = install or refresh a reusable direct-grant reactive quest definition
- `wm.sources.combat_log.peek` = read-only check of the combat-log source and resolution failures
- `wm.quests.purge_range` = wipe disposable quest ranges while skipping reactive reusable quest IDs by default

## Operational notes

When you need to restore or wipe WM-generated quest IDs, use:

- `docs/CLEANUP_PLAYBOOK.md`

That note documents the practical difference between rollback and purge, the runtime/client cleanup ladder, and the PowerShell-specific cleanup pitfalls we already hit.

Reactive quest cleanup guardrails:

- `wm.quests.rollback` refuses to touch quests owned by active reactive rules unless `--allow-reactive` is passed
- `wm.quests.purge_range` skips active reactive quest IDs unless `--include-reactive` is passed

## Rebuilt server workflow

The repo now also carries the rebuild helpers needed to keep a native AzerothCore tree available for WM module development.

Current stance:

- the rebuilt server is a **latest working baseline**
- it is good enough for building and testing a native WM module
- it is **not yet** a faithful replacement for the old repack

Repo-side helpers:

- `scripts/repack/Start-Rebuilt-Server.bat`
- `scripts/repack/Rebuild-Rebuilt-Server.bat`
- `docs/repack-rebuild.md`

Rebuilt runtime layout in the current Windows workflow:

- main configs live under `run/configs/`
- module configs live under `run/configs/modules/`
- the most commonly tweaked files are:
  - `run/configs/worldserver.conf`
  - `run/configs/authserver.conf`
  - `run/configs/modules/playerbots.conf`
  - `run/configs/modules/random_enchants.conf`
  - `run/configs/modules/individualProgression.conf`
  - `run/configs/modules/mod_weather_vibe.conf`

Known rebuilt-baseline limitations right now:

- Individual Progression is not trustworthy yet; the DB still expects `npc_ipp_*` / `gobject_ipp_*` script code that the current rebuilt source tree does not provide
- some old service NPCs and custom spawns may be missing or only partially functional because older module SQL/update streams do not line up cleanly with the current source set
- WeatherVibe currently loads, but it is not yet meaningfully configured in-world
- the rebuilt realm should be treated as WM development infrastructure first, not as a parity-certified gameplay replacement

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
