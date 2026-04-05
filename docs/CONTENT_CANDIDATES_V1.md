# Content Candidates V1

## Architecture choice

Use a **candidate layer** between raw exports and the local model.

Instead of asking the model to invent quest, item, or spell options from nothing, code should prepare small structured candidate lists derived from your local exports.

## Why this layer exists

Your local model is small.

That means it should not be asked to:
- infer all valid quest structures from memory
- imagine item templates from scratch
- guess spell shapes from vague descriptions

Instead, code should hand it:
- a prompt package with current character and target context
- a small set of plausible quest candidates
- a small set of plausible item candidates
- a small set of plausible spell candidates

## Current implementation in repo

- `src/wm/candidates/models.py`
- `src/wm/candidates/providers.py`
- `src/wm/candidates/demo.py`
- `src/wm/prompt/candidate_package.py`
- `src/wm/prompt/demo_candidates.py`
- `tests/test_candidates.py`

## Supported sources

### Sample bundle exports
These are supported directly, including the wrapper shape:
- `position_offset`
- `row`

### Full row-list exports
These are also supported directly.

## Current candidate types

- quest candidates from `quest_template.json`
- item candidates from `item_template.json`
- spell candidates from `spell_dbc.json`

## Current limitations

- candidate selection is generic and schema-light
- it currently prefers a small set of likely label/id/summary fields
- it does not yet use advanced filtering by class, theme, faction, target type, or arc stage

That is the next version.

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

### Run candidate-only demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.candidates.demo
```

### Run prompt package + candidates demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.prompt.demo_candidates
```

## Expected result

The candidate-only demo should print quest/item/spell option lists.

The prompt+candidates demo should print:
- your seeded prompt package
- plus appended `candidates.quests`
- plus appended `candidates.items`
- plus appended `candidates.spells`

## Next implementation target

Content Candidates V2 should add:
- filtering by class and role
- filtering by target type and faction
- filtering by arc stage and narrative tone
- reward safety rules
- better quest reward compatibility checks
