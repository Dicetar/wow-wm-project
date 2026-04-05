# Setup Guide — `D:\WOW\wm-project`

## Architecture choice

This setup keeps the project as a **local Python-first utility/service** on the same Windows machine that already hosts or can access your AzerothCore data.

## Step 1 — create or enter the local project directory

If the repo is not cloned yet:

```powershell
cd D:\WOW
git clone https://github.com/Dicetar/wow-wm-project.git wm-project
cd D:\WOW\wm-project
```

If it is already cloned:

```powershell
cd D:\WOW\wm-project
```

## Verify

```powershell
Get-Location
Get-ChildItem
```

---

## Step 2 — create and activate the virtual environment

```powershell
cd D:\WOW\wm-project
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

## Verify

```powershell
python --version
pip --version
python -c "import wm; print('wm package import OK')"
```

---

## Step 3 — create the environment file

```powershell
cd D:\WOW\wm-project
Copy-Item .env.example .env
notepad .env
```

Suggested values to paste into `.env`:

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

## Verify

```powershell
cd D:\WOW\wm-project
Get-Content .env
```

---

## Step 4 — place lookup files

### Option A — use the bundled sample file

No extra action needed.

### Option B — use your real export

Put your real creature export here:

```text
D:\WOW\wm-project\data\lookup\creature_template_full.json
```

Example copy command if your export is already somewhere on disk:

```powershell
cd D:\WOW\wm-project
Copy-Item "D:\WOW\db_export_bundles\creature_template_full.json" ".\data\lookup\creature_template_full.json"
```

Adjust the source path if your real file is elsewhere.

## Verify

```powershell
cd D:\WOW\wm-project
Get-ChildItem .\data\lookup
```

---

## Step 5 — run tests

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

## Verify

Expected result: test output ending in `OK`.

---

## Step 6 — run the resolver with the sample lookup

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.main resolve-target --entry 1498 --lookup data\lookup\sample_creature_template_full.json
```

## Verify

Expected result: JSON output for `Bethor Iceshard`.

---

## Step 7 — run the resolver with your real export

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.main resolve-target --entry 1498 --lookup data\lookup\creature_template_full.json
```

## Verify

Expected result: JSON output using your real export.

---

## Step 8 — import WM bootstrap SQL into `acore_world`

### If `mysql.exe` is on PATH

```powershell
cd D:\WOW\wm-project
mysql -u root -p acore_world < .\sql\bootstrap\wm_bootstrap.sql
```

### If you need to call the embedded MySQL client directly

Replace the path below with your real repack path if needed:

```powershell
cd D:\WOW\wm-project
& "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u root -p acore_world < .\sql\bootstrap\wm_bootstrap.sql
```

## Verify

### If `mysql.exe` is on PATH

```powershell
mysql -u root -p -D acore_world -e "SHOW TABLES LIKE 'wm_%';"
```

### If using embedded MySQL client

```powershell
& "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u root -p -D acore_world -e "SHOW TABLES LIKE 'wm_%';"
```

Expected tables:
- `wm_subject_definition`
- `wm_subject_enrichment`
- `wm_player_subject_journal`
- `wm_player_subject_event`
- `wm_publish_log`
- `wm_rollback_snapshot`

---

## Step 9 — inspect one real resolver case manually

Use a few known entries from your export:

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.main resolve-target --entry 68 --lookup data\lookup\creature_template_full.json
python -m wm.main resolve-target --entry 69 --lookup data\lookup\creature_template_full.json
python -m wm.main resolve-target --entry 46 --lookup data\lookup\creature_template_full.json
```

## Verify

Expected rough behavior:
- `68` → Stormwind guard / gossip-capable humanoid
- `69` → wolf beast
- `46` → murloc-type creature mechanically represented as humanoid

---

## Step 10 — pull future repo updates

```powershell
cd D:\WOW\wm-project
git pull origin main
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Verify

```powershell
git status
```

Expected result: `working tree clean` if you have no local edits.
