# Reserved Slot Manager V2

## Architecture choice

Keep the slot lifecycle in the database, not only in Python memory.

That means the allocator should be able to:
- read the next free slot from `acore_world`
- mark it as `staged`
- transition it to `active`
- release it to `retired` or `archived`
- summarize live pool state

## Why this matters

At this point the project already has:
- reserved ranges
- a seeded `wm_reserved_slot` pool
- an in-memory allocator demo

V2 makes the pool operational for real WM workflows.

## Current implementation in repo

- `src/wm/reserved/db_allocator.py`
- `src/wm/reserved/commands.py`
- `src/wm/reserved/demo_db.py`
- `src/wm/reserved/cli.py`
- `sql/dev/reset_demo_reserved_slot.sql`
- `tests/test_reserved_db_allocator_sql.py`
- `tests/test_reserved_cli.py`

## Available commands

### Summary

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.commands summary
```

### Allocate next free slot

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.commands allocate --entity-type spell_dbc_or_spell_slots --arc-key wm_demo --character-guid 42 --source-quest-id 910123 --note "Allocated from CLI"
```

### Get a specific slot

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.commands get --entity-type spell_dbc_or_spell_slots --reserved-id 900000
```

### Transition a slot

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.commands transition --entity-type spell_dbc_or_spell_slots --reserved-id 900000 --status active
```

### Release a slot

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.commands release --entity-type spell_dbc_or_spell_slots --reserved-id 900000
```

### Release a slot as archived

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.commands release --entity-type spell_dbc_or_spell_slots --reserved-id 900000 --archive
```

## Live DB demo

### Reset the scratch demo slot

```powershell
cd D:\WOW\wm-project
Get-Content .\sql\dev\reset_demo_reserved_slot.sql | & "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore acore_world
```

### Run the live DB demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.reserved.demo_db
```

## Expected result

The live DB demo should show one slot going through:
- `staged`
- `active`
- `retired`

and then print a summary of the live DB state.

## Current limitations

- no row locking or transaction isolation yet
- no exhaustion-expansion workflow yet
- no safety policy yet for reusing `retired` or `archived` slots

## Next implementation target

Reserved Slot Manager V3 should add:
- safer allocation under concurrent use
- exhaustion detection
- automatic range expansion proposal
- linking live allocated slots to published quest/item/spell rows
