Status: PARTIAL
Last verified: 2026-04-14
Verified by: Codex
Doc type: status

# Journal Layer V1 / V2

## Architecture choice

Use an **append-only event log** plus a **counter summary view**.

That gives the WM two useful things at once:
- compact prompt-ready summaries
- raw history that can be reinterpreted later

## Goal

Represent subject memory in a form like:

### Example A

Stieve  
Miner living in Goldshire  
Player completed quest: "A Miner's Burden"  
Player learned Mining from Stieve

### Example B

Grey Wolf  
Shabby looking wild beast  
Player killed 18  
Player skinned 10  
Player fed Grey Wolf and unlocked quest: "A Cautious Truce"

## Current implementation in repo

- `src/wm/journal/models.py`
- `src/wm/journal/summarizer.py`
- `src/wm/journal/reader.py`
- `src/wm/journal/inspect.py`
- `src/wm/journal/demo.py`
- `tests/test_journal_inspect.py`
- `tests/test_journal_reader.py`
- `tests/test_journal_summarizer.py`

## What it does now

- builds compact subject summaries from:
  - subject card data
  - journal counters
  - special events
- formats the result as plain markdown-like text
- supports your two core early examples:
  - trainer / quest memory for NPCs
  - kill / skin / feed-triggered quest memory for beasts
- `SubjectJournalReader` can load real DB-backed rows from:
  - `wm_subject_definition`
  - `wm_subject_enrichment`
  - `wm_player_subject_journal`
  - `wm_player_subject_event`
- the reader checks table existence before touching optional WM journal tables
- the reader merges subject-definition rows, enrichment rows, journal counters, raw journal events, and an optional resolver-built subject card
- prompt demo callers pass their resolved target profile into the reader so missing WM subject rows degrade to a resolver-backed subject summary instead of `null`
- `python -m wm.journal.inspect` can inspect one player and one creature subject from static lookup JSON or the live runtime resolver
- if the world DB is unavailable during table probing, the reader now degrades to resolver-backed output instead of throwing; this is `PARTIAL`, not `WORKING`, because DB journal rows were not loaded

## What it does not do yet

- auto-create `wm_subject_definition` rows for newly resolved targets
- auto-create or edit `wm_subject_enrichment` rows
- summarize freeform notes with an LLM
- prove the Stieve / Grey Wolf examples from the live lab DB in this session
- automatically seed or mutate journal tables from the inspect command

## Local commands

### Pull the latest repo changes

```powershell
cd D:\WOW\wm-project
git pull origin main
```

### Reinstall the editable package

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Run all tests

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

### Run focused journal tests

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m unittest tests.test_journal_reader tests.test_journal_summarizer tests.test_subject_resolver tests.test_prompt_package tests.test_event_rules
```

### Run the journal demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.journal.demo
```

### Inspect one player and subject

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.journal.inspect --player-guid 5406 --target-entry 46 --summary
```

### Seed the deterministic lab fixture

Use this only against a disposable/lab world DB. It upserts one known creature subject for entry `46`, resets only player `5406`'s seeded journal rows for that subject, and inserts one deterministic `wm_event_log` row for context-pack smoke testing.

```powershell
cd D:\WOW\wm-project
$sql = Get-Content .\sql\dev\seed_journal_context_5406_world.sql -Raw
& $env:WM_MYSQL_BIN_PATH --host=$env:WM_WORLD_DB_HOST --port=$env:WM_WORLD_DB_PORT --user=$env:WM_WORLD_DB_USER --password=$env:WM_WORLD_DB_PASSWORD --database=$env:WM_WORLD_DB_NAME --execute="$sql"
python -m wm.journal.inspect --player-guid 5406 --target-entry 46 --summary
```

If the seed is applied successfully, the expected status is `WORKING` with these source flags present:

- `subject_definition`
- `subject_enrichment`
- `subject_resolver`
- `player_subject_journal`
- `player_subject_event`

## Expected result

You should see two printed summaries:
- Stieve example
- Grey Wolf example

For the player `5406` fixture, the inspect command should show `Murloc Forager` and seeded counters/events after the lab seed is applied.

## Current proof status

- `WORKING`: repo tests for summary generation, DB-row loading, table-missing fallback, DB-unavailable fallback, and `wm.journal.inspect` rendering.
- `PARTIAL`: live lab proof. On 2026-04-14, bounded local smoke against default `127.0.0.1:3306` could not connect, so the command returned resolver-backed `PARTIAL` output with no journal rows loaded.
- `UNKNOWN`: any target entry that cannot be resolved by static lookup or runtime resolver.

## Next implementation target

Journal Layer V2 should next add:
- optional subject-definition materialization from resolver output
- integration into the deterministic context-pack builder
- live-lab verification against seeded `wm_subject_definition`, `wm_subject_enrichment`, `wm_player_subject_journal`, and `wm_player_subject_event` rows
