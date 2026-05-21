---
name: wm-create-spell-shell
description: Create a new server-known spell "shell" so the WM can apply it as an aura or teach it as a spell (the backing for a wm.ability.v1). Use this WHENEVER an ability/aura/marker needs a real spell ID the server recognizes — before granting any custom power. Triggers: "create a spell", "make a shell spell", "I need a new aura/spell id for an ability", "add a spell to the shell bank". This makes the spell exist server-side; client icon/tooltip is a separate step (wm-build-client-patch).
---

# Create a server spell shell

A WM "shell" is a real spell row the worldserver knows about, used as the
visible aura / learnable spell that abilities bind to. The proper path edits the
server's `Spell.dbc` via the shell-bank tooling — **not** by hand-cloning a row
into the `acore_world.spell_dbc` table (that table-clone is the deprecated hack
the marker spell 946500 used; prefer the file materialization below).

> **Honesty note:** I've verified these CLIs exist and run (`--help` works), and
> read their argument surface, but I have **not executed the full
> materialize→restart flow** end-to-end. Run with `--summary` / `inspect` first
> and confirm paths before applying.

## The pieces
- **Shell bank** — `control/runtime/spell_shell_bank.json` (`wm.spells.shell_bank`)
  is the catalog of shells: each has a spell id (in a managed range) and a
  `seed_template`. A new shell starts as an entry here.
- **Server DBC** — `wm.spells.server_dbc materialize` clones the shell seed rows
  into a server `Spell.dbc` so the ids become server-known.
- **Behavior (optional)** — `wm.spells.publish` writes `spell_proc` /
  `spell_linked_spell` rows for proc/link behavior. It does NOT create the dbc
  shell itself.
- **Client patch** — `wm.spells.client_patch` (see **wm-build-client-patch**)
  delivers icon/name/description to the client. Separate, required for polish.

## Steps

### 1. Add the shell to the bank
Edit `control/runtime/spell_shell_bank.json` — add an entry with the new spell id
(managed range) and an appropriate `patch_seed_template`. (Inspect the existing
entries for the shape.)

### 2. Inspect / materialize the server Spell.dbc
```bash
# look first
python -m wm.spells.server_dbc inspect \
  --spell-dbc "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc" --spell-id <id> --summary

# materialize the shell row(s) into a server Spell.dbc copy
python -m wm.spells.server_dbc materialize \
  --source-dbc "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc" \
  --out "<staging>\Spell.dbc" \
  --spell-id <id> --seed-profile learnable --summary
```
`--seed-profile learnable` = neutral seed for grant/revoke validation;
`castable` = cast-shape seed for visible client tests. **Back up the source
Spell.dbc** before overwriting the live one; materialize to a staging path, then
copy into the server data dir.

### 3. RESTART the worldserver
`Spell.dbc` is read at **startup** — it is NOT hot-reloadable (this is why the
marker spell needed a restart). `.reload` does nothing for spells.

### 4. (Optional) behavior rules
If the spell needs procs/linked spells:
```bash
WM_WORLD_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.spells.publish --draft-json <spell-behavior>.json --mode apply --summary
```
(`ManagedSpellDraft`: `spell_entry`, `slot_kind`, `name`, `base_visible_spell_id`,
`proc_rules`, `linked_spells`, …)

### 5. Client patch
Run **wm-build-client-patch** so the spell shows the right icon/name/tooltip.

## Then what
Reference the shell's spell id as `shell_binding.visible_aura_spell_id` in a
`wm.ability.v1` spec (see **wm-create-ability**), then grant via **wm-grant-ability**.

## Gotchas
- Skipped restart → the server doesn't know the spell; `player_apply_aura` /
  `player_learn_spell` apply nothing real.
- Overwrote the live Spell.dbc without a backup → keep a copy.
- Expecting `.reload` to pick up a new spell → it won't; spells need a restart.
