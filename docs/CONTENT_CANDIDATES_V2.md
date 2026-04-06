# Content Candidates V2

## What changed from V1

V1 proved that the project could extract candidate lists from your export files.

However, your real demo exposed two weak points:
- spell candidates could come back empty because the export schema used different spell-name fields than the provider expected
- item and quest lists could contain obviously bad candidates such as deprecated or unused content

V2 addresses both issues.

## Current implementation in repo

- `src/wm/candidates/filters.py`
- `src/wm/candidates/providers_v2.py`
- `src/wm/candidates/demo_v2.py`
- `src/wm/prompt/demo_candidates_v2.py`
- `tests/test_candidate_filters.py`
- `tests/test_candidates_v2.py`

## What V2 improves

### Better spell label inference
The provider now inspects the export schema and tries likely spell name fields such as:
- `Name_Lang_enUS`
- `SpellName1`
- `SpellName`
- `Name`
- `Name_lang`
- fallback description fields if needed

This should prevent the empty spell candidate problem when the sample bundle uses a different naming convention than V1 expected.

### Basic junk filtering
The provider now filters out labels that are clearly bad candidates, such as:
- `Deprecated ...`
- `[UNUSED] ...`
- `zzOLD...`
- `Dummy ...` for items
- `Test ...` for items

This is intentionally simple, but it immediately improves the quality of candidate lists fed into the small local model.

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

### Run candidate demo V2

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.candidates.demo_v2
```

### Run prompt package + candidates demo V2

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.prompt.demo_candidates_v2
```

## Expected result

Compared to V1:
- the item list should contain fewer obviously bad candidates
- the spell list should no longer be empty if the export contains usable name-like fields in schema/sample rows

## Why this matters

Your small local model should not waste attention on junk candidates.

The better the filtered option list, the more likely the WM is to:
- propose sane rewards
- propose plausible quest references
- pick real spell structures instead of inventing them

## Next implementation target

Content Candidates V3 should add:
- class-aware filtering
- faction / target-type filtering
- reward safety rules
- stronger item and spell compatibility checks
- candidate ranking for specific narrative arcs
