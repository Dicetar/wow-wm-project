---
name: wm-create-ability
description: Author a new WM ability (wm.ability.v1) backed by a server spell shell, so it can be granted to characters. Use this WHENEVER you need a new passive/active power the WM can bestow — a stat aura, periodic damage, on-hit proc, or summon. Triggers: "create an ability", "make a new power/spell the WM can grant", "add an ability to the catalog", "author a passive aura". This authors the ability spec; granting it is a separate step (wm-grant-ability).
---

# Create a WM ability

A WM ability is a small declarative spec (`wm.ability.v1`) bound to a **server
spell shell** (a real `spell_dbc` row in the shell bank). The ability spec is
catalog data; granting compiles it into native bus actions.

## The dependency chain (do these in order)
1. **Server spell shell** — a real spell the worldserver knows, that the ability's
   `shell_binding.visible_aura_spell_id` points at. Created via the shell bank +
   `wm.spells.server_dbc materialize` (edits the server `Spell.dbc`, **needs a
   worldserver restart** — spells aren't hot-reloadable). **Use the
   `wm-create-spell-shell` skill.** Note: `wm.spells.publish` is NOT what creates
   the shell — it only writes proc/linked-spell *behavior* rows.
2. **Client MPQ patch** — so the spell's **icon / name / description** render
   correctly in-client (server shell alone = working effect but broken/placeholder
   tooltip like "Caster Centered AOE 0001"). **Use the `wm-build-client-patch`
   skill** (`wm.spells.client_patch build`). Required for player-facing polish.
3. **Ability spec** — this skill's output.

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
