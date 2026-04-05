# Journal Layer V1

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
- `src/wm/journal/demo.py`
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

## What it does not do yet

- query MySQL directly
- load subject definitions from `wm_subject_definition`
- load enrichment rows from `wm_subject_enrichment`
- load counters from `wm_player_subject_journal`
- load raw events from `wm_player_subject_event`

That is the next slice.

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

### Run the journal demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.journal.demo
```

## Expected result

You should see two printed summaries:
- Stieve example
- Grey Wolf example

## Next implementation target

Journal Layer V2 should add:
- DB read helpers
- loading real subject definitions
- loading real journal rows
- loading event rows
- combining resolver output + journal output
