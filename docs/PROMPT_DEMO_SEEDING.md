# Prompt Demo Seeding

## Why this exists

The prompt package demo is working when it returns:
- target profile
- empty character state
- empty journal state

That means the integration pipeline is fine, but there is no WM-owned data yet for the fixed demo inputs.

This guide seeds the demo inputs used by `wm.prompt.demo`:
- `character_guid = 42`
- `target_entry = 46`

## What gets seeded

### `acore_characters`
- one `wm_character_profile` row
- one `wm_character_arc_state` row
- one `wm_character_unlock` row
- one `wm_character_reward_instance` row
- one `wm_character_prompt_queue` row

### `acore_world`
- one `wm_subject_definition` row for creature entry `46`
- one `wm_player_subject_journal` row for player `42`
- two `wm_player_subject_event` rows

## Local commands

### Pull latest changes

```powershell
cd D:\WOW\wm-project
git pull origin main
```

### Seed `acore_characters`

```powershell
cd D:\WOW\wm-project
Get-Content .\sql\dev\seed_prompt_demo_characters.sql | & "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore acore_characters
```

### Verify `acore_characters`

```powershell
& "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore -D acore_characters -e "SELECT * FROM wm_character_profile WHERE CharacterGUID = 42; SELECT * FROM wm_character_arc_state WHERE CharacterGUID = 42; SELECT * FROM wm_character_unlock WHERE CharacterGUID = 42; SELECT * FROM wm_character_reward_instance WHERE CharacterGUID = 42; SELECT * FROM wm_character_prompt_queue WHERE CharacterGUID = 42;"
```

### Seed `acore_world`

```powershell
cd D:\WOW\wm-project
Get-Content .\sql\dev\seed_prompt_demo_world.sql | & "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore acore_world
```

### Verify `acore_world`

```powershell
& "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore -D acore_world -e "SELECT * FROM wm_subject_definition WHERE SubjectType = 'creature' AND CreatureEntry = 46; SELECT * FROM wm_player_subject_journal WHERE PlayerGUID = 42; SELECT * FROM wm_player_subject_event WHERE PlayerGUID = 42;"
```

### Run the prompt package demo again

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.prompt.demo
```

## Expected result

The demo JSON should no longer contain:
- `character_profile: null`
- empty `arc_states`
- empty `unlocks`
- empty `rewards`
- empty `prompt_queue`
- `journal_summary: null`

Instead, it should show a fully populated example package.
