Status: PARTIAL
Last verified: 2026-04-14
Verified by: Codex
Doc type: reference

# Context Pack V1

This is the first deterministic context-pack slice.

It is not an LLM path and not a planner. It packages existing deterministic WM facts so operator review and future LLM proposal generation can consume one stable shape.

## Current Implementation

- `src/wm/context/models.py`
- `src/wm/context/builder.py`
- `tests/test_context_pack.py`

The builder composes existing systems:

- target profile resolution
- WM subject-card construction
- DB-backed journal reader output
- optional source `WMEvent`
- character-state reader output
- recent canonical events from `wm_event_log`
- related subject events
- reactive quest rule/runtime state
- control registry recipe and policy metadata
- latest native bridge context snapshot row when present

## What Is Working

- `ContextPackBuilder` builds a deterministic `wm.context_pack.v1` payload from:
  - player GUID
  - target creature entry
  - optional source event
  - character state
  - resolved target profile
  - resolver-built subject card
  - journal summary and journal source flags
  - recent canonical events
  - related subject events
  - reactive quest runtime state
  - eligible control recipes and default policy metadata
  - latest native context snapshot, when available
  - compact `generation_input` for deterministic downstream proposal building
- `python -m wm.context.builder --help` works.
- Unit tests prove:
  - fully wired event-backed pack assembly
  - character state, recent events, related events, quest runtime, recipes, policy, and native snapshot sections
  - resolver-fallback journal packs are marked `PARTIAL`
  - missing optional builder dependencies mark packs `PARTIAL`
  - unresolved target entries return `UNKNOWN` from the CLI instead of emitting vague empty packs or raw tracebacks

## What Is Partial

- the CLI path still depends on live DB access for journal loading
- native context snapshot inclusion loads only an existing latest snapshot row during pack assembly
- `python -m wm.context.snapshot` can request one native snapshot and wait with a bounded timeout; tracked `mod-wm-bridge` now writes one `wm_bridge_context_snapshot` from the action queue when the scoped player is online
- live bridge-lab proof against a real event row has not been completed in this session
- zone/local mood and broader scene context are not included yet
- recipe/policy sections are context only; they do not execute proposals

## Example

```powershell
cd D:\WOW\wm-project
python -m wm.context.builder --target-entry 46 --player-guid 5406 --summary
```

Use `--runtime` when the target profile should come from the live world DB instead of the static lookup JSON.
Use `--event-id` to build from an existing `wm_event_log` row.
Use `--no-native-snapshot` when the native snapshot table is not bootstrapped or not relevant.

Seeded event-backed smoke path:

```powershell
cd D:\WOW\wm-project
.\start-bridge-lab-mysql.bat
$env:WM_WORLD_DB_HOST = "127.0.0.1"
$env:WM_WORLD_DB_PORT = "33307"
$env:WM_WORLD_DB_USER = "acore"
$env:WM_WORLD_DB_PASSWORD = "acore"
$env:WM_WORLD_DB_NAME = "acore_world"
$env:WM_CHAR_DB_HOST = "127.0.0.1"
$env:WM_CHAR_DB_PORT = "33307"
$env:WM_CHAR_DB_USER = "acore"
$env:WM_CHAR_DB_PASSWORD = "acore"
$env:WM_CHAR_DB_NAME = "acore_characters"
& "D:\WOW\WM_BridgeLab\deps\mysql\bin\mysql.exe" --host=$env:WM_WORLD_DB_HOST --port=$env:WM_WORLD_DB_PORT --user=$env:WM_WORLD_DB_USER --password=$env:WM_WORLD_DB_PASSWORD --database=$env:WM_WORLD_DB_NAME --execute="source D:/WOW/wm-project/sql/dev/seed_journal_context_5406_world.sql"
$eventId = (& "D:\WOW\WM_BridgeLab\deps\mysql\bin\mysql.exe" --host=$env:WM_WORLD_DB_HOST --port=$env:WM_WORLD_DB_PORT --user=$env:WM_WORLD_DB_USER --password=$env:WM_WORLD_DB_PASSWORD --database=$env:WM_WORLD_DB_NAME --batch --raw --skip-column-names --execute="SELECT EventID FROM wm_event_log WHERE Source = 'dev_seed' AND SourceEventKey = 'journal-context-5406-46-kill-1' LIMIT 1").Trim()
python -m wm.context.builder --event-id $eventId --summary --no-native-snapshot
```

One-shot native snapshot request/wait path:

```powershell
cd D:\WOW\wm-project
python -m wm.context.snapshot --player-guid 5406 --timeout-seconds 10 --summary
.\scripts\bridge_lab\Request-BridgeLabContextSnapshot.ps1 -PlayerGuid 5406 -TimeoutSeconds 10 -Summary
```

Current expected result for the snapshot command is `PARTIAL` unless a native snapshot writer exists and writes `wm_bridge_context_snapshot`.

## Status Behavior

- `WORKING`: all configured pack sections load successfully, including DB-backed journal rows and any configured native snapshot row.
- `PARTIAL`: optional live sections are unavailable, the journal falls back to resolver-only data, or a snapshot request is queued but no snapshot row appears before timeout.
- `UNKNOWN`: target or event resolution fails, for example an unknown creature entry or missing `wm_event_log` id.

## Current Proof Status

- `WORKING`: repo tests for deterministic event-backed pack assembly, optional-section status behavior, native snapshot row consumption, and CLI `UNKNOWN` behavior for unresolved targets.
- `WORKING`: bridge-lab proof on 2026-04-14 against `127.0.0.1:33307` after `sql/dev/seed_journal_context_5406_world.sql`; `python -m wm.context.builder --event-id 603 --summary --no-native-snapshot` produced `status: WORKING`, `trigger_event_type: kill`, `journal_status: WORKING`, and `eligible_recipes: kill_burst_bounty`.
- `PARTIAL`: native snapshot inclusion. The same event-backed pack without `--no-native-snapshot` produced `status: PARTIAL` until a fresh online-player snapshot row exists for player `5406`.
- `PARTIAL`: bridge-lab native snapshot proof on 2026-04-14 consumed action request `28` with the rebuilt worldserver, but it failed with `player_not_online`; rerun after logging player `5406` into the lab.
- `BROKEN`: no current repo evidence.
- `UNKNOWN`: target or event resolution failure.

## Next Step

Integrate:

- fresh `context_snapshot_request` issuance before pack assembly once the online-player lab proof is green
- quest runtime state from non-reactive quest sources
- zone/local mood summaries
- eligible action-policy gates suitable for proposal validation previews
