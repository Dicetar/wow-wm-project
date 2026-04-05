# Export Formats

## Why this exists

Your local project currently has **two different JSON export shapes**:

1. **Full row-list exports**
   - Example: `D:\WOW\wm-project\data\lookup\creature_template_full.json`
   - Shape: a JSON array of row objects
   - Best for: runtime lookup and exact resolution

2. **Sample bundle exports**
   - Example: `D:\WOW\db_export\acore_world\creature_template.json`
   - Shape: a JSON object with metadata + `schema` + `samples`
   - Best for: schema discovery, join discovery, model reference, and prompt-safe examples

## Important rule

Sample bundle exports are **not** full runtime data.

They are useful because they tell the WM:
- what columns exist
- how many total rows the table has
- what sample rows look like
- which primary keys and order columns exist

But they are **not enough** for exact target resolution or exhaustive lookup.

## Current implementation in repo

- `src/wm/export/models.py`
- `src/wm/export/loader.py`
- `src/wm/export/demo.py`
- `tests/test_export_loader.py`

## What the loader does

- loads row-list exports into `RowListExport`
- loads sample-bundle exports into `ExportBundle`
- normalizes literal string `"NULL"` values into real `None`

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

### Run export demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.export.demo
```

## Expected result

The demo should show:
- sample bundle metadata for `D:\WOW\db_export\acore_world\creature_template.json`
- full row-list metadata for `D:\WOW\wm-project\data\lookup\creature_template_full.json`

## How WM should use these two formats

### Row-list exports
Use for:
- target resolver
- exact creature/item/quest lookup
- joining current known IDs to concrete rows

### Sample bundle exports
Use for:
- schema-aware prompt building
- table and join planning
- model-side reference examples
- code generation hints

## Next implementation target

The next layer should unify:
- target resolver output
- sample-bundle schema metadata
- per-character journal and exclusivity state

That will let the WM build prompts from both:
- exact runtime facts
- broader table awareness
