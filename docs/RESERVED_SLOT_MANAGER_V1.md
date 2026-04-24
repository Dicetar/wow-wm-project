# Reserved Slot Manager V1

## Architecture choice

Use a **pool + allocator** model, not a one-shot fixed-range model.

Reserved ID ranges are only the first layer.
The real management layer is a tracked slot pool with statuses like:
- `free`
- `staged`
- `active`
- `retired`
- `archived`

## Why this exists

A fixed set of ranges is useful, but not sufficient by itself.

The project eventually needs to:
- stage dummy slots
- activate them for private WM content
- retire or archive them later
- detect exhaustion
- expand ranges cleanly when needed

## Current implementation in repo

- `src/wm/reserved/models.py`
- `src/wm/reserved/allocator.py`
- `src/wm/reserved/seed_sql.py`
- `src/wm/reserved/demo.py`
- `sql/bootstrap/wm_reserved_slots.sql`
- `tests/test_reserved_allocator.py`

## Current DB tables involved

- `wm_reserved_id_range` — high-level configured ranges
- `wm_reserved_slot` — actual managed slots for each reserved ID

## Slot lifecycle

### `free`
Unused slot available for allocation.

### `staged`
Reserved for a specific arc/character but not yet considered fully live.

### `active`
Currently in use by live WM-authored content.

### `retired`
No longer in active use, but held out of the free pool.

### `archived`
Released from active use and marked as archived history.

## Important design rule

The character's story history should live in WM tables.
The implementation slot should be recyclable later when safe.

That means ID slots are **infrastructure**, not the permanent memory of the narrative.

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

### Run the local allocator demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.demo
```

### Create `wm_reserved_slot` table in `acore_world`

```powershell
cd D:\WOW\wm-project
Get-Content .\sql\bootstrap\wm_reserved_slots.sql | & "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore acore_world
```

### Generate slot seed SQL from the reserved ranges

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.seed_sql
```

### Verify generated SQL exists

```powershell
cd D:\WOW\wm-project
Get-Item .\sql\dev\generated_seed_reserved_slots.sql
```

### Import generated slot seed SQL into `acore_world`

```powershell
cd D:\WOW\wm-project
Get-Content .\sql\dev\generated_seed_reserved_slots.sql | & "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore acore_world
```

### Verify seeded slot counts

```powershell
& "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore -D acore_world -e "SELECT EntityType, SlotStatus, COUNT(*) AS CountRows FROM wm_reserved_slot GROUP BY EntityType, SlotStatus ORDER BY EntityType, SlotStatus;"
```

## Expected result

You should see free slot counts for:
- `quest`
- `item`
- `spell`
- `gossip_menu`
- `npc_text`

## Next implementation target

Reserved Slot Manager V2 should add:
- DB-backed allocator writes
- a free-slot query helper
- exhaustion detection
- range expansion workflow
- safety checks before reusing retired/archived slots
