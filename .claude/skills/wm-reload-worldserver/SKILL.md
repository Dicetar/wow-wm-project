---
name: wm-reload-worldserver
description: Make the running worldserver pick up DB/DBC changes — hot-reload the tables that support it, or restart for the ones that don't. Use this WHENEVER you've published a quest/item/spell or edited game data and it isn't showing up in-game yet. Triggers: "reload the worldserver", "the new quest/item isn't showing", "apply my DB changes live", "reload quest_template", "restart the worldserver". Knowing reload-vs-restart per data type is the whole point.
---

# Reload / restart the worldserver

The worldserver caches game data. After a DB/DBC write you must tell it to pick
the change up — and **the mechanism depends on the data type**:

| Changed | Mechanism | Why |
|---|---|---|
| `quest_template` (+addon/offer/request) | **SOAP `.reload all quest`** (hot) | quests hot-reload |
| `creature_queststarter` / `questender` | **SOAP** `.reload creature_quest*` | hot |
| `item_template` | **SOAP** `.reload item_template` (hot) | items hot-reload |
| `spell_proc`, `spell_linked_spell`, other `spell_*` behavior | **SOAP** `.reload spell_*` (hot) | behavior tables hot-reload |
| **`Spell.dbc` shell rows** (new spells) | **RESTART** | DBCs load at startup only — NOT hot-reloadable |
| module config (allowlists, etc.) | **RESTART** | configs read at startup |

## Hot reload (SOAP)
```python
import dataclasses
from wm.config import Settings
from wm.runtime_sync import SoapRuntimeClient
s = dataclasses.replace(Settings.from_env(), soap_port=7879)   # BridgeLab SOAP
client = SoapRuntimeClient(settings=s)
client.execute_command(".reload all quest")
```
`wm.runtime_sync.build_default_quest_reload_commands()` returns the standard quest
set (`.reload creature_queststarter`, `.reload creature_questender`,
`.reload all quest`). Most publish CLIs do this for you when run with
`--runtime-sync soap`.

## Restart (for spells / DBC / config)
```powershell
powershell -File scripts/bridge_lab/Restart-BridgeLabWorldServer.ps1
```
(`-GracefulWaitSeconds 20 -ForceAfterSeconds 5` defaults.) Required after staging
a server `Spell.dbc` (wm-create-spell-shell) or changing a `PlayerGuidAllowList`.

## Gotchas
- Tried `.reload` for a new spell → no effect; DBC needs a **restart**.
- Allowlist edit not taking → restart (config is startup-only).
- SOAP on the wrong port → BridgeLab SOAP is **7879** (Settings defaults to 7878).
