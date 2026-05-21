---
name: wm-grant-ability
description: Grant a WM ability to a specific character — compile the ability spec into native bus actions and enqueue them so the player gains the aura/spell. Use this WHENEVER the WM should bestow a power on a player — an arc grant-point reward, a passive aura, an active ability. Triggers: "grant ability X to character Y", "give the player this power/aura", "push ability to character", "apply the shadow pulse aura to them". The ability spec must exist (see wm-create-ability first).
---

# Grant an ability to a character

Compiles a `wm.ability.v1` spec into a **grant plan** (one or more native bus
actions — typically `player_apply_aura`, and `player_learn_spell` for active
abilities) and enqueues them on `wm_bridge_action_request`.

## Prerequisites
- **The target GUID is on BOTH allowlists.** Aura/spell grants go through the
  spells module, so the GUID must be on `WmBridge.PlayerGuidAllowList`
  (`mod_wm_bridge.conf`) **and** `WmSpells.PlayerGuidAllowList`
  (`mod_wm_spells.conf`). Add via `Configure-BridgeLabRuntime.ps1
  -WmBridgePlayerGuidAllowList "...,<guid>" -WmSpellsPlayerGuidAllowList "...,<guid>"`
  and **restart the worldserver**.
- Its **shell spell exists in `spell_dbc`** (the `visible_aura_spell_id`). New
  `spell_dbc` rows require a worldserver **restart** — spells are loaded at
  startup and are NOT hot-reloadable like quests. (See **wm-create-ability**.)
- The **player is online** (else `player_not_online`).
- For correct in-client icon/tooltip, the **MPQ client patch** for that spell
  should be shipped (server-side works without it, but the tooltip is wrong).
- To let the WM *sense* the applied aura on the spine, the spell ID should be in
  `WmBridge.Emit.AuraSpellAllowList` (that's what makes the `applied` event fire,
  e.g. the marker spell 946500). Not required for the grant itself.

## Canonical operator path (preferred)
For granting a managed visible spell to a player, the project has a wrapper that
sets the BridgeLab ports and **waits for the player to come online** — use it
instead of hand-rolling the bus insert:
```powershell
powershell -File scripts/bridge_lab/Grant-BridgeLabManagedSpell.ps1 `
  -SpellEntry <visible_aura_spell_id> -PlayerGuid 5408 -Mode apply -WaitForPlayerOnline
```
(`-DraftPath <spell-draft>` resolves the entry from a `visible_spell_slot` draft;
`-AllRanks` for multi-rank; `-LabMySqlPort 33307 -SoapPort 7879` are the defaults.)
This still requires the GUID on both allowlists (above).

## Do it programmatically (the in-slice path — compile + apply)
```python
import json
from wm.db.mysql_cli import MysqlCliClient
from wm.abilities.schema import parse_ability
from wm.abilities.grant_compiler import compile_grant_plan
from wm.cli.native_applier import NativeApplier

spec = parse_ability(json.load(open("control/examples/abilities/shadow_pulse_aura_v1.json")))
plan = compile_grant_plan(spec, character_guid=5408)   # -> GrantPlan of GrantSteps

applier = NativeApplier(client=MysqlCliClient(), host="127.0.0.1", port=33307,
                        user="acore", password="acore", database="acore_world")
result = applier.apply_grant_plan(plan)   # enqueues one bus action per step
print(result)
```
`apply_grant_plan` derives idempotency keys from the plan, so re-running is
collision-safe per character+ability+step.

## What gets enqueued
- `stat_aura` / passive → `player_apply_aura` with the shell `visible_aura_spell_id`.
- active abilities → also `player_learn_spell` so the spell appears on the bar.

## Verify
```sql
SELECT IdempotencyKey, ActionKind, Status, ResultJSON
FROM wm_bridge_action_request
WHERE PlayerGUID = 5408 AND CreatedBy='wm-slice' AND ActionKind IN ('player_apply_aura','player_learn_spell')
ORDER BY RequestID DESC LIMIT 5;
```
`Status='done'` → the aura is on the character / spell learned. The player sees
the buff icon in-game (with the correct art only if the MPQ patch is shipped).

## Gotchas
- Row stuck `pending` / guid mismatch → GUID missing from `WmBridge` *or*
  `WmSpells` allowlist (add to both + restart worldserver).
- Aura "applies" but nothing happens → the `visible_aura_spell_id` isn't a real
  `spell_dbc` row, or the worldserver wasn't restarted after adding it.
- `player_not_online` → log in, re-run.
- Aura applies but icon/tooltip is wrong → the spell's MPQ client patch is missing.
- `unknown ability_id` from the compiler → the spec file/id is wrong or unparsed.
