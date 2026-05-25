---
name: wm-create-spell-shell
description: Create a new server-known spell "shell" so the WM can apply it as an aura or teach it as a spell (the backing for a wm.ability.v1). Use this WHENEVER an ability/aura/marker needs a real spell ID the server recognizes — before granting any custom power. Triggers: "create a spell", "make a shell spell", "I need a new aura/spell id for an ability", "add a spell to the shell bank". This makes the spell exist server-side; client icon/tooltip is a separate step (wm-build-client-patch).
---

# Create a server spell shell

A WM "shell" is a real spell row the worldserver knows about, used as the
visible aura / learnable spell that abilities bind to. Per **ADR 0003**
(`docs/adr/0003-client-shell-bank-for-visible-wm-spells.md`), player-facing WM
spells use a **pre-seeded shell bank + client patch** — "server-only spell hacks
are testing-only, not production-safe." Per **ADR 0001**, do **not** reuse stock
live spell IDs as carriers — allocate a reserved shell-bank ID. The proper flow
stages the server `Spell.dbc` from the shell bank and ships a client MPQ patch.

(The permanent watcher marker is shell id **946602**, a dummy-aura shell in the
`self_aura` family — leave it alone. `946500` is just the `caster_centered_aoe`
family's slot-range start, not a marker; don't confuse the two.)

> **Status (verified 2026-05-25):** The **create + verify** half is proven
> end-to-end — adding a shell, `shell_audit`, and the unified
> `materialize → audit → dry-run` lane all run green (worked example: shell
> `946607` `wm_field_test_boon_v1`). The **live half** (stage to the DataDir →
> worldserver **restart** → client patch → apply in-client) still requires a
> worldserver restart (disconnects everyone on that realm) and an in-client
> confirmation, so run the dry-run first and treat the restart as a deliberate,
> announced step.

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
Edit `control/runtime/spell_shell_bank.json` — add an entry to `shells[]` with a
new spell id in a family's managed range (find a free id: it must be inside one
`family.slot_range_start..end` and not already in `shells[]`). Copy the shape of
an existing same-family entry. A visible self-buff needs, at minimum, a `label`,
`tooltip`, and a `client_presentation` with `spell_icon_id`, a non-zero
`duration_index` (use **21** for permanent), and `range_index: 1` for self-cast.
If it's a dummy/marker aura (`effect_1: 6`, `effect_apply_aura_name_1: 4`) the
audit requires the stock-identity fields cleared (`spell_family_name`,
`spell_family_flags_1/2/3`, `damage_class`, `prevention_type` all `0`).

### 2. Audit the new shell (fast, offline)
```bash
python -m wm.spells.shell_audit --spell-id <id> --summary   # expect status=WORKING
```
This catches the common breakages (missing icon/label/tooltip, zero-duration
visible buff, self-cast range leak, marker aura inheriting stock identity)
*before* you touch any DBC.

### 3. Materialize + verify + stage (unified lane — canonical)
Prefer `wm.spells.unified_dbc_publish`: it materializes **both** the server and
client `Spell.dbc` from the same shell bank, audits that name/icon/duration
agree across them, and — only with `--apply` — backs up + stages the server DBC
and queues the client patch. Run dry-run first (no `--apply`):
```bash
SRC="D:/WOW/Azerothcore_WoTLK_Rebuild/run/data/dbc/Spell.dbc"   # BridgeLab DataDir
python -m wm.spells.unified_dbc_publish --source-dbc "$SRC" \
  --server-out .wm-bootstrap/state/<run>/server/Spell.dbc \
  --client-out .wm-bootstrap/state/<run>/client/Spell.dbc \
  --target-server-dbc "$SRC" --backup-dir .wm-bootstrap/state/<run>/backups \
  --spell-id <id> --summary            # expect verified=true staged=false
# then add --apply to stage the server DBC (backup first) + queue the client patch
```
(The older `scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1` +
`wm.spells.server_dbc materialize` path still works but stages only the server
side and does not cross-check client/server agreement — prefer the unified lane.)

### 4. RESTART the worldserver
`Spell.dbc` is read at **startup** — it is NOT hot-reloadable. `.reload` does
nothing for spells. Use `scripts/bridge_lab/Restart-BridgeLabWorldServer.ps1` and
confirm the pid stays alive + SOAP comes back (`wm.doctor`). ⚠️ A restart
disconnects every player on the realm — announce it.

> **Test gotcha:** adding a *named* shell bumps the named-override count, which
> several tests assert (`tests/test_spell_shell_bank.py` `named_override_count`,
> `tests/test_server_spell_dbc.py` `appended_count`). Update those counts as part
> of the change and keep `python -m pytest -q` green.

### 5. (Optional) behavior rules — proc / linked spells
If the spell needs procs/linked spells, publish behavior via the canonical
wrapper (it wraps `wm.spells.live_publish`, NOT `wm.spells.publish` directly):
```powershell
powershell -File scripts/bridge_lab/Publish-BridgeLabManagedSpell.ps1 `
  -DraftPath <spell-behavior>.json -Mode apply -RuntimeSync soap
```
(`ManagedSpellDraft`: `spell_entry`, `slot_kind`, `name`, `base_visible_spell_id`,
`proc_rules`, `linked_spells`, …) This writes `spell_proc` / `spell_linked_spell`
— behavior tables that DO hot-reload via SOAP, unlike the dbc shell.

### 6. Client patch
The unified lane (step 3, `--apply`) already queues the client patch; the
close-watcher rebuilds + installs `patch-z.mpq` when the WoW client exits (it
locks the MPQ while open). To force it now, run **wm-build-client-patch**. Until
the patch is installed, the spell works server-side but renders with a
missing/placeholder icon+name client-side.

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
