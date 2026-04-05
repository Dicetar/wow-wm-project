# Deployment Guide — Windows

## Architecture choice

For the first slice, deploy the project as a **local Python utility/service** on the same Windows machine that can already access your AzerothCore files and database.

This keeps the deployment simple:
- no Docker required
- no web UI required yet
- no service manager required for the first run

## What this guide sets up

- local Python environment
- project install in editable mode
- sample resolver run
- WM bootstrap SQL import
- conventions for placing your lookup exports

## Prerequisites

Install these on Windows:
- Python 3.11 or newer
- Git
- access to your AzerothCore MySQL instance

You do **not** need:
- Node.js
- Docker
- Visual Studio
- Eluna

## Recommended folder layout

```text
D:\\wow-wm-project\\
D:\\wow-wm-project\\data\\lookup\\
D:\\wow-wm-project\\.venv\\
```

## Step 1 — get the repo onto the machine

```powershell
cd D:\
git clone https://github.com/Dicetar/wow-wm-project.git
cd .\\wow-wm-project
```

## Step 2 — create virtual environment

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

## Step 3 — create `.env`

```powershell
Copy-Item .env.example .env
```

Then edit the values.

Example:

```env
WM_ENV=dev
WM_LOG_LEVEL=INFO

WM_WORLD_DB_HOST=127.0.0.1
WM_WORLD_DB_PORT=3306
WM_WORLD_DB_NAME=acore_world
WM_WORLD_DB_USER=root
WM_WORLD_DB_PASSWORD=CHANGE_ME

WM_CHAR_DB_HOST=127.0.0.1
WM_CHAR_DB_PORT=3306
WM_CHAR_DB_NAME=acore_characters
WM_CHAR_DB_USER=root
WM_CHAR_DB_PASSWORD=CHANGE_ME
```

## Step 4 — place lookup files

For the first run, place your normalized creature export in:

```text
D:\\wow-wm-project\\data\\lookup\\creature_template_full.json
```

Accepted initial format for this bootstrap is a JSON array of rows with fields like:
- `entry`
- `name`
- `subname`
- `minlevel`
- `maxlevel`
- `faction`
- `npcflag`
- `type`
- `family`
- `rank`
- `unit_class`
- `gossip_menu_id`

If you do not have the real export in place yet, the project ships with a small sample file.

## Step 5 — run tests

```powershell
python -m unittest discover -s tests -v
```

## Step 6 — run the resolver manually

### Using sample lookup

```powershell
python -m wm.main resolve-target --entry 1498 --lookup data\\lookup\\sample_creature_template_full.json
```

### Using your real export

```powershell
python -m wm.main resolve-target --entry 1498 --lookup data\\lookup\\creature_template_full.json
```

## Step 7 — create WM-owned tables

Recommended: keep WM tables in the **world DB** at first.

Example using MySQL client:

```powershell
mysql -u root -p acore_world < sql\\bootstrap\\wm_bootstrap.sql
```

If your MySQL binary is inside the repack folder, point to that exact executable.

## Step 8 — verify bootstrap tables

Check that these tables now exist:
- `wm_subject_definition`
- `wm_subject_enrichment`
- `wm_player_subject_journal`
- `wm_player_subject_event`
- `wm_publish_log`
- `wm_rollback_snapshot`

## Operational recommendation

For now, run the project manually from a PowerShell session.

Do **not** turn it into a background Windows service yet.

The next safe operational target is:
- resolver works
- bootstrap tables exist
- one journal write helper exists
- then consider a long-running process

## Troubleshooting

### `ModuleNotFoundError: No module named 'wm'`
You likely forgot editable install.

```powershell
pip install -e .
```

### PowerShell blocks activation

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\\.venv\\Scripts\\Activate.ps1
```

### JSON decode error on lookup file
Your lookup file is not valid JSON or not in array form.
Start with the sample file and replace it only after validation.

### MySQL import fails
Double-check:
- database name
- mysql executable path
- username/password
- the DB is running

## Recommended next machine-level milestones

1. real creature export loaded
2. resolver tested against 10–20 real entries
3. WM bootstrap SQL imported
4. journal helper added
5. prompt-builder layer added after resolver is trusted
