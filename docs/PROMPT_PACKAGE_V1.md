# Prompt Package V1

## Architecture choice

Use a **read-only prompt package builder** that pulls from:
- full lookup exports
- per-character WM tables in `acore_characters`
- per-subject journal tables in `acore_world`

The output should be a compact JSON package that a small local model can consume safely.

## Why this layer exists

The local 8B model should not read raw DB rows directly.

Instead, code should build a structured package containing:
- resolved target facts
- per-character arc state
- per-character unlocks and rewards
- pending WM prompts
- compact journal summary for the target

## Current implementation in repo

- `src/wm/db/mysql_cli.py`
- `src/wm/character/reader.py`
- `src/wm/journal/reader.py`
- `src/wm/prompt/package.py`
- `src/wm/prompt/demo.py`
- `tests/test_mysql_cli.py`
- `tests/test_prompt_package.py`

## Current limitations

- the demo uses fixed values:
  - `character_guid = 42`
  - `target_entry = 46`
- the project currently reads through `mysql.exe`
- no prompt queue consumption yet
- no automatic writes yet

## Important design decision

Actual rewards may still be **applied** using GM commands like:
- `.character learn [spell_id]`
- `.additem [item_id] [count]`

But the WM must still **track** those rewards in its own tables so the character journey remains unique.

## Local commands

### Pull latest changes

```powershell
cd D:\WOW\wm-project
git pull origin main
```

### Reinstall editable package

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Run tests

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

### Run prompt package demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.prompt.demo
```

## Required local config

Your `.env` should include:

```env
WM_WORLD_DB_HOST=127.0.0.1
WM_WORLD_DB_PORT=3306
WM_WORLD_DB_NAME=acore_world
WM_WORLD_DB_USER=acore
WM_WORLD_DB_PASSWORD=acore

WM_CHAR_DB_HOST=127.0.0.1
WM_CHAR_DB_PORT=3306
WM_CHAR_DB_NAME=acore_characters
WM_CHAR_DB_USER=acore
WM_CHAR_DB_PASSWORD=acore

WM_MYSQL_BIN_PATH=D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe
```

## Expected result

The prompt demo should print one JSON package combining:
- resolved creature target data
- WM per-character state
- subject journal summary if a matching subject exists

## Next implementation target

Prompt Package V2 should add:
- configurable CLI arguments for character and target
- write helpers for unlock tracking after GM command grants
- write helpers for prompt queue consumption
- richer world-side joins for quest and gossip context
