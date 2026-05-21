---
name: wm-create-ability
description: Author a new WM ability (wm.ability.v1) backed by a server spell shell, so it can be granted to characters. Use this WHENEVER you need a new passive/active power the WM can bestow — a stat aura, periodic damage, on-hit proc, or summon. Triggers: "create an ability", "make a new power/spell the WM can grant", "add an ability to the catalog", "author a passive aura". This authors the ability spec; granting it is a separate step (wm-grant-ability).
---

# Create a WM ability

A WM ability is a small declarative spec (`wm.ability.v1`) bound to a **server
spell shell** (a real `spell_dbc` row in the shell bank). The ability spec is
catalog data; granting compiles it into native bus actions.

## The dependency chain (do these in order)
1. **Server spell shell** — a `spell_dbc` row that the ability's
   `shell_binding.visible_aura_spell_id` points at. Publish it through
   `wm.spells.publish` from a `ManagedSpellDraft` JSON:
   ```bash
   WM_WORLD_DB_PORT=33307 WM_SOAP_PORT=7879 \
     python -m wm.spells.publish --draft-json <spell>.json --mode dry-run --summary
   # then --mode apply
   ```
   The shell-bank contract lives at `control/runtime/spell_shell_bank.json`
   (`wm.spells.shell_bank`), and low-level dbc writing is in `wm.spells.server_dbc`.
   **Critical:** a new `spell_dbc` row requires a worldserver **RESTART** to take
   effect — spells load at startup and are NOT hot-reloadable like quests (this is
   exactly why the marker spell 946500 needed a restart). Without the shell +
   restart, the grant's `player_apply_aura` / `player_learn_spell` has nothing real
   to apply.
2. **Client MPQ patch** — for the spell's **icon / name / description** to show
   correctly in-client. Server-side shell alone = working effect but
   broken/placeholder tooltip (e.g. "Caster Centered AOE 0001"). Build it with
   `wm.spells.client_patch` + `wm.spells.export_patch_plan` (materializes
   Spell.dbc / SpellIcon.dbc / SkillLineAbility.dbc into the client payload via
   MPQEditor). This is a real, required step for player-facing polish — not
   optional cosmetics to wave away.
3. **Ability spec** — this skill's output.

(A dedicated `wm-create-spell-shell` skill should wrap step 1 + 2 properly; until
it exists, follow the commands above.)

## Author the spec
Put it under `control/examples/abilities/<id>.json`, schema `wm.ability.v1`:
```json
{
  "schema": "wm.ability.v1", "id": "shadow_pulse_aura_v1", "name": "Shadow Pulse",
  "version": 1, "client_tier": "T2", "feasibility_notes": "shell-bank passive visible aura",
  "type": "passive", "target": "self",
  "effect": {"kind": "stat_aura", "stat": "spell_power_shadow", "amount": 24, "duration": "persistent"},
  "shell_binding": {"shell_bank_ref": "shell_demo_passive_1", "visible_aura_spell_id": 946700},
  "grant_policy": {"scope": "active_character", "persistence": "persistent", "revoke_path": "managed.rollback.shadow_pulse_aura_v1"}
}
```
- `effect.kind` is exactly ONE of: `stat_aura`, `periodic_damage`, `on_hit_proc`, `spawn_actor`.
- `shell_binding.visible_aura_spell_id` must be a **real shell spell ID** (step 1).
- Validate against `control/schemas/wm.ability.v1.schema.json`.

## Verify the spec parses
```python
from wm.abilities.schema import parse_ability
import json
parse_ability(json.load(open("control/examples/abilities/shadow_pulse_aura_v1.json")))
```

## Then what
To give the ability to a player, use **wm-grant-ability** (it compiles the spec
into the bus actions that apply the aura / teach the spell).

## Gotchas
- Pointing `visible_aura_spell_id` at a non-existent shell → grant applies
  nothing meaningful.
- Skipping the client patch → effect works, tooltip/icon is wrong. Flag it.
