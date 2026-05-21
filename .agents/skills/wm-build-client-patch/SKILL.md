---
name: wm-build-client-patch
description: Build (and optionally install) the client MPQ patch so custom WM spells show the correct icon, name, and description in the game client. Use this WHENEVER a managed/shell spell has been added server-side and the in-client tooltip is wrong or placeholder (e.g. "Caster Centered AOE 0001"). Triggers: "build the client patch", "make the MPQ patch", "the spell icon/tooltip is wrong", "ship spell icons to the client", "patch the client DBC". Server-side spells work without this, but players see broken art until it's applied.
---

# Build the client MPQ patch for shell spells

A server spell shell (see **wm-create-spell-shell**) makes a spell *work*, but the
client renders its icon/name/description from its **own** `Spell.dbc` inside an
MPQ. Custom spells therefore look broken in-client (placeholder icon, wrong
tooltip) until you ship a client patch. This wraps `wm.spells.client_patch`,
which materializes the client DBCs and packages `patch-z.mpq` via MPQEditor.

> **Honesty note:** I verified this CLI exists and runs (`--help`), and read its
> arguments, but I have **not executed the MPQ build** myself. Confirm MPQEditor
> is present and run with `--summary` before installing into the client.

## Prerequisites
- The shell exists in `control/runtime/spell_shell_bank.json` and server-side
  (wm-create-spell-shell).
- **MPQEditor.exe** present at `.wm-bootstrap/tools/mpqeditor/x64/MPQEditor.exe`
  (override with `--mpq-editor`).
- Source client DBCs available (the CLI defaults point at them; override with
  `--source-*` if needed).

## Build it
```bash
# Full build: materialize client Spell.dbc + SkillLineAbility.dbc +
# SkillRaceClassInfo.dbc and package patch-z.mpq
python -m wm.spells.client_patch build --spell-id <id> --summary

# Build AND install into the client Data dir in one go:
python -m wm.spells.client_patch build --spell-id <id> --install \
  --install-path "<WoW client>\Data" --summary
```
`build` packages the `.mpq` (default `--package-out`); `--install` copies it to
the client `Data` folder. There's also a `materialize` subcommand if you only
want to regenerate the client `Spell.dbc` payload without packaging.

Useful flags: `--include all|named` (which shells to include), repeatable
`--spell-id N`, `--mpq-editor <path>`.

## Verify
- The packaged `.mpq` exists at the `--package-out` path.
- **Restart the game client** (MPQ patches load at client launch), then check the
  spell's tooltip/icon in-game — it should now show the authored name, icon, and
  description instead of the placeholder.

## Gotchas
- **The running client locks `patch-z.mpq`.** You must fully close `wow.exe`
  before `--install` (proven repeatedly in the Broug pipeline: "wow.exe ... was
  stopped because it locked patch-z.mpq"). Install fails or silently no-ops
  otherwise.
- `MPQEditor.exe not found` → install it to the expected path or pass `--mpq-editor`.
- Client not restarted after install → it still reads the old MPQs; the patch
  won't show.
- Server says the spell works but tooltip is still wrong → that's exactly what
  this skill fixes; the server shell and the client patch are independent.
- Built artifacts are **not committed** (ADR 0003); until installed, behavior
  iteration stays on the debug/native lane.
- This covers **spells**. Custom **item** icons need an analogous item client
  patch which may not exist yet — flag that as a gap rather than assuming parity.
