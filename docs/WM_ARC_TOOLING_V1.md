Status: WORKING
Last verified: 2026-05-03
Verified by: Codex
Doc type: reference

# WM Arc Tooling V1

This document records the repo-owned tools added after Broug Lightness V1 and Empty Court V2 exposed repeatable failure modes in quest, shell, DBC, and BridgeLab release work.

## Why This Exists

The Broug arc failures were mostly not idea failures. They were release-gate failures:

- a kill quest target was chosen before proving hostility and live spawn count
- quest objective directions were too vague in `LogDescription`
- custom gameobjects and creatures existed in SQL but lacked visible/clickable/model fields needed by this core
- visible self-cast shells inherited range or stock aura identity from their seed spell
- client truth and server truth drifted after shell presentation changes
- reward-grant truth and learned-spell truth diverged
- Energy Surge `910014` / `946606` was affected by unrelated aura stacking and scope assumptions
- Silent Meridian cooldown reduction had to update the core cooldown table, not only custom WM state

The tools below are not a replacement for live proof. They are the static and operator gates that should catch these problems before the player sees them.

## Tools

### Content Preflight

Command:

```powershell
python -m wm.content.preflight --arc broug_lightness_assassin_v1 --summary
python -m wm.content.preflight --arc broug_empty_court_v2 --summary
```

Module: `src/wm/content/preflight.py`

Current Broug profiles check registry claims, shell-bank rows, source SQL tokens, forbidden ID reuse, concrete quest directions, model rows, gameobject template fields, target hostility proof, and optional live DB checks.

Status meanings:

- `WORKING`: no blocking static issues found
- `PARTIAL`: warnings exist
- `BROKEN`: a required field, claim, source token, or forbidden reuse check failed
- `UNKNOWN`: no preflight profile exists for the arc

### Shell Audit

Command:

```powershell
python -m wm.spells.shell_audit --spell-id 946621 --spell-id 946803 --summary
```

Module: `src/wm/spells/shell_audit.py`

Checks named shell-bank rows and, when DBC paths are provided, compares shell-bank presentation fields against client and server `Spell.dbc` rows.

Current checks include:

- label, tooltip, and icon exist
- learned self-cast buttons use `range_index=1`
- learned passives with spellbook rows have a seed spell
- harmless marker auras clear inherited stock spell-family identity
- client and server DBC presentation fields match when both are supplied

### BridgeLab Release Gate

Command:

```powershell
python -m wm.bridge_lab.release_gate --arc broug_all_current --summary
```

Module: `src/wm/bridge_lab/release_gate.py`

Prints the ordered release plan for focused tests, content preflights, world SQL apply, server DBC staging, client patch install, native build/deploy, and native ping. By default it only prints the plan. `--apply` executes it and stops on the first required failure.

For `broug_all_current`, the plan preflights both `broug_lightness_assassin_v1` and `broug_empty_court_v2` before mutating BridgeLab.

### Live Proof Packet

Command:

```powershell
python -m wm.live.proof_packet --arc broug_empty_court_v2 --summary
```

Module: `src/wm/live/proof_packet.py`

Prints the concrete in-client proof steps, expected outcomes, counters, and operator checks. This exists to keep final proof tied to normal player actions: accept quest, complete objective, turn in, learn reward, use ability, verify counters, and relog/restart behavior.

### Arc Scaffold

Command:

```powershell
python -m wm.arcs.scaffold --arc broug_future_arc_v3 --summary
```

Module: `src/wm/arcs/scaffold.py`

Prints the standard file set and required gates for future arcs: journey seed, Python helper module, world SQL, status doc, focused tests, preflight, shell audit, proof packet, and release gate.

## Required Broug Gate

Before handing another Broug arc or fix to the player, run:

```powershell
python -m pytest tests/test_broug_arc_tooling.py tests/test_broug_lightness.py tests/test_broug_empty_court.py tests/test_spell_shell_bank.py tests/test_client_spell_patch.py tests/test_server_spell_dbc.py
python -m wm.content.preflight --arc broug_lightness_assassin_v1 --summary
python -m wm.content.preflight --arc broug_empty_court_v2 --summary
python -m wm.spells.shell_audit --spell-id 946202 --spell-id 946203 --spell-id 946620 --spell-id 946621 --spell-id 946622 --spell-id 946803 --spell-id 946804 --spell-id 946805 --spell-id 946806 --summary
python -m wm.bridge_lab.release_gate --arc broug_all_current --summary
python -m wm.live.proof_packet --arc broug_empty_court_v2 --summary
```

For fresh arcs, add a new `wm.content.preflight` profile before deployment instead of relying only on freeform tests.
