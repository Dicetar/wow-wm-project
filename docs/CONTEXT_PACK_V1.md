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
- `python -m wm.context.snapshot` can request one native snapshot and wait with a bounded timeout, but tracked `mod-wm-bridge` code currently only queues `wm_bridge_context_request`; no tracked native writer for `wm_bridge_context_snapshot` was found in this pass
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
$sql = Get-Content .\sql\dev\seed_journal_context_5406_world.sql -Raw
& $env:WM_MYSQL_BIN_PATH --host=$env:WM_WORLD_DB_HOST --port=$env:WM_WORLD_DB_PORT --user=$env:WM_WORLD_DB_USER --password=$env:WM_WORLD_DB_PASSWORD --database=$env:WM_WORLD_DB_NAME --execute="$sql"
$eventId = (& $env:WM_MYSQL_BIN_PATH --host=$env:WM_WORLD_DB_HOST --port=$env:WM_WORLD_DB_PORT --user=$env:WM_WORLD_DB_USER --password=$env:WM_WORLD_DB_PASSWORD --database=$env:WM_WORLD_DB_NAME --batch --raw --skip-column-names --execute="SELECT EventID FROM wm_event_log WHERE Source = 'dev_seed' AND SourceEventKey = 'journal-context-5406-46-kill-1' LIMIT 1").Trim()
python -m wm.context.builder --event-id $eventId --summary
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
- `PARTIAL`: live smoke on 2026-04-14 against default `127.0.0.1:3306` could not connect, so builder output used resolver fallback and missing optional sections; snapshot request proof also returned `PARTIAL`.
- `BROKEN`: no current repo evidence.
- `UNKNOWN`: live bridge-lab event-backed pack from a real native event id has not been rerun after this checkpoint.

## Next Step

Integrate:

- native writer/processor for queued `wm_bridge_context_request` rows, then fresh `context_snapshot_request` issuance before pack assembly
- quest runtime state from non-reactive quest sources
- zone/local mood summaries
- eligible action-policy gates suitable for proposal validation previews
