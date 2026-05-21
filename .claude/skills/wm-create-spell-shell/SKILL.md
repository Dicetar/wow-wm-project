---
name: wm-create-spell-shell
description: Create a new server-known spell "shell" so the WM can apply it as an aura or teach it as a spell (the backing for a wm.ability.v1). Use this WHENEVER an ability/aura/marker needs a real spell ID the server recognizes — before granting any custom power. Triggers: "create a spell", "make a shell spell", "I need a new aura/spell id for an ability", "add a spell to the shell bank". This makes the spell exist server-side; client icon/tooltip is a separate step (wm-build-client-patch).
---

# Create a server spell shell

A WM "shell" is a real spell row the worldserver knows about, used as the
visible aura / learnable spell that abilities bind to. Per **ADR 0003**
(`docs/adr/0003-client-shell-bank-for-visible-wm-spells.md`), player-facing WM
spells use a **pre-seeded shell bank + client patch** — "server-only spell hacks
are testing-only, not production-safe." So the table-clone the marker spell
946500 used is a testing-only marker, **not** the path for a real ability shell.
Per **ADR 0001**, do **not** reuse stock live spell IDs as carriers — allocate a
reserved shell-bank ID. The proper flow stages the server `Spell.dbc` from the
shell bank and ships a client MPQ patch.

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

### 2. Stage the server Spell.dbc (canonical wrapper)
Use the BridgeLab wrapper — it materializes from the shell bank, backs up, and
inspects, against the correct server data dir
(`D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc`, which is BridgeLab's
DataDir):
```powershell
powershell -File scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1 `
  -Include named -SeedProfile learnable -SpellId <id>
```
`-SeedProfile learnable` = neutral seed for grant/revoke validation; `castable` =
cast-shape seed for visible client tests. (Underlying module:
`wm.spells.server_dbc materialize|inspect` — the script wraps it with the right
paths + a backup, so prefer the script.)

### 3. RESTART the worldserver
`Spell.dbc` is read at **startup** — it is NOT hot-reloadable (this is why the
marker spell needed a restart). `.reload` does nothing for spells.

### 4. (Optional) behavior rules — proc / linked spells
If the spell needs procs/linked spells, publish behavior via the canonical
wrapper (it wraps `wm.spells.live_publish`, NOT `wm.spells.publish` directly):
```powershell
powershell -File scripts/bridge_lab/Publish-BridgeLabManagedSpell.ps1 `
  -DraftPath <spell-behavior>.json -Mode apply -RuntimeSync soap
```
(`ManagedSpellDraft`: `spell_entry`, `slot_kind`, `name`, `base_visible_spell_id`,
`proc_rules`, `linked_spells`, …) This writes `spell_proc` / `spell_linked_spell`
— behavior tables that DO hot-reload via SOAP, unlike the dbc shell.

### 5. Client patch
Run **wm-build-client-patch** so the spell shows the right icon/name/tooltip.

## Then what
Reference the shell's spell id as `shell_binding.visible_aura_spell_id` in a
`wm.ability.v1` spec (see **wm-create-ability**), then grant via **wm-grant-ability**.

## Gotchas
- Skipped restart → the server doesn't know the spell; `player_apply_aura` /
  `player_learn_spell` apply nothing real.
- Reused a stock spell ID as the carrier → forbidden by ADR 0001 (stock-behavior
  collisions). Use a reserved shell-bank ID.
- Expecting `.reload` to pick up a new spell → it won't; the dbc shell needs a
  restart (only proc/linked behavior tables hot-reload).
- Built patch/dbc artifacts are **not committed** (ADR 0003) — they're generated
  locally under `.wm-bootstrap/state/...`; until the client patch is installed,
  iterate on the debug/native lane.
