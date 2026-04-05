# Character Exclusivity Layer V1

## Architecture choice

Use **per-character state tables** as the source of truth, while actual rewards can still be granted through GM commands.

This layer exists so the World Master knows:
- which character it is speaking to
- which arc that character is on
- which private rewards the character has already received
- which follow-up prompt or branch choice should be presented next

## Why this layer exists

The same account may have multiple characters, but each character should feel like a different WM-driven journey.

That requires state keyed by **CharacterGUID**, not by account and not globally.

## Current implementation in repo

- `src/wm/character/models.py`
- `src/wm/character/demo.py`
- `tests/test_character_models.py`
- `sql/bootstrap/wm_character_state.sql`

## Tables introduced

- `wm_character_profile`
- `wm_character_arc_state`
- `wm_character_unlock`
- `wm_character_reward_instance`
- `wm_character_prompt_queue`

## Important design decision

### Grant path
Rewards and abilities may be **applied** using GM commands such as:
- `.character learn [spell_id]`
- `.additem [item_id] [count]`

### Tracking path
But the WM still needs its own tables to remember:
- who was granted what
- from which arc or quest
- whether the unlock is bot-eligible
- whether an item is meant to gate an alternate ability while equipped

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

### Run demo

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.character.demo
```

### Import SQL into `acore_characters`

```powershell
cd D:\WOW\wm-project
Get-Content .\sql\bootstrap\wm_character_state.sql | & "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore acore_characters
```

### Verify created tables

```powershell
& "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore -D acore_characters -e "SHOW TABLES LIKE 'wm_character_%';"
```

## Expected result

You should now have per-character WM state tables in `acore_characters`.

## Next implementation target

Character Exclusivity Layer V2 should add:
- DB read/write helpers
- prompt queue consumption
- unlock recording after GM-command grant
- arc-state updates after branch choices
