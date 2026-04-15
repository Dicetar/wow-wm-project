Status: PARTIAL
Last verified: 2026-04-15
Verified by: Codex
Doc type: status

# Summon and Spell Platform Status

This is the current truth source for the WM summon and custom-spell lane.

For the failure history, read:

- [Summon Failure Postmortem](SUMMON_FAILURE_POSTMORTEM.md)

## Supported path

The supported path is:

1. define a WM shell in `control/runtime/spell_shell_bank.json`
2. create or update the matching client shell-bank patch row
3. bind shell spell ID to WM-owned behavior in `mod-wm-spells`
4. publish shell metadata into:
   - `wm_spell_shell`
   - `wm_spell_behavior`
   - `wm_spell_grant`
5. grant or revoke the shell through the workbench
6. use the debug/native lane for behavior tuning until the client shell is installed

Current supported iteration lane:

- `mod-wm-spells` plus `wm_spell_debug_request`
- `python -m wm.content.workbench invoke-shell-behavior`

Current fast release lane for the proven Bonebound Twins behavior:

- `python -m wm.spells.summon_release --player-guid 5406 --summary`
- `.\summon-bridge-lab-bonebound-twins.bat -PlayerGuid 5406`

The release lane assumes the shell, behavior row, scoped player, lab config, and worldserver are already proven. It skips shell-bank lookup, player lookup, schema preflight, and default wait/poll verification. Use the debug lane first when changing schema, behavior config, player scope, or native code.

Visible stock-carrier testing is not supported.

## Working now

### Shell-bank and patch workspace

- shell-bank contract exists
- client patch workspace exists
- default bank size is 1000 slots per family across 6 families
- named shell entries exist for `940000` and `940001`

### Native spell runtime

- `mod-wm-spells` builds in `WM_BridgeLab`
- shell, behavior, grant, and debug tables exist
- debug invoke resolves shell-bound config from `wm_spell_behavior`
- `WORKING`: Bonebound Twins debug/native lane uses WM shell `940001`, not stock `697` or `49126`
- `WORKING`: lab DB proof on 2026-04-15 retired `49126`, disabled its behavior row, removed stock WM spell-script bindings, and left only `940001 -> spell_wm_shell_dispatch`
- `WORKING`: lab invoke request `7` for player `5406` executed `summon_bonebound_twin_v2` and persisted `Bonebound Alpha` with `CreatedBySpell=940001`
- `WORKING`: Bonebound Twins behavior config transfers the summoner's total intellect to all summon stats and shadow spell power to summon attack power
- `WORKING`: Bonebound Twins release submitter exists at `python -m wm.spells.summon_release`; bridge-lab request `8` for player `5406` returned immediately, reached `done` in the same second, and persisted `Bonebound Alpha` with `CreatedBySpell=940001`

### Operator lane

- workbench commands exist for shell draft, publish, grant, ungrant, and debug invoke
- native bridge spell learn and unlearn actions exist
- repo-root Python invocation works through `pytest.ini` and the `wm` package shim

### Cleanup and lab defaults

- Jecia-only cleanup tooling exists for poisoned summon state
- lab runtime defaults point to `mod-wm-spells`
- `mod-wm-prototypes` is disabled by default in the lab flow

## Partial or blocked

### Visible player-facing shell proof

Still blocked on the client patch being built and installed from repo instructions:

- `940000` visible in spellbook
- `940001` visible in spellbook
- real action-bar and tooltip proof
- final cast/recast/dismiss/relog lifecycle proof on the visible shell path

### Twin summon experiments

Bonebound Twins are now the supported debug/native twin-summon iteration path in `mod-wm-spells`.

Use them as lab/debug work only until the shell-bank patch is installed and validated.

Current classification:

- `WORKING`: repo tests, native build, bridge-lab SQL binding, and debug invoke for shell `940001`
- `WORKING`: fast release submit path for already-proven shell `940001`, including live bridge-lab request `8`
- `PARTIAL`: visible client spellbook/action-bar path until the client shell-bank patch is installed and validated
- `PARTIAL`: mount/dismount lifecycle until the current bridge-lab visual test confirms both Alpha and Omega return after temporary unsummon
- `BROKEN`: stock-carrier bindings for `697` / `49126`; do not revive them

## Release Lane Rules

Use release mode only after the matching debug/test path is already green.

What release mode does:

- inserts the known `wm_spell_debug_request` row directly
- defaults to `summon_bonebound_twin_v2` and shell `940001`
- returns after submit unless `--wait` is explicitly passed
- relies on `WmSpells.DebugPollIntervalMs = 50` in the lab config for fast native pickup

What release mode must not do:

- it must not run schema discovery or publish preflight
- it must not resolve player names or wait for login by default
- it must not mutate shell bindings or stock spell carriers
- it must not be used to validate a new behavior shape

## Retired paths

Retired carrier IDs:

- `697`
- `8853`
- `57913`
- `49126`
- `7302`

Retired implementation patterns:

- stock spell carriers as WM ability shells
- carrier-cancellation hacks as the main summon strategy
- `mod-wm-prototypes` as the main summon and custom-ability lane

## Next verification step

1. finish the current bridge-lab mount/dismount test for `940001`
2. confirm both `Bonebound Alpha` and `Bonebound Omega` return after temporary unsummon
3. build and install the local shell-bank client patch
4. grant `940000` or `940001` through the workbench
5. validate the visible shell path:
   - spellbook entry
   - cast behavior
   - clean failure UX when gated
   - friendly summon
   - recast / dismiss / relog lifecycle
