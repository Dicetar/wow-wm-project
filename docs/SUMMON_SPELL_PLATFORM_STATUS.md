Status: PARTIAL
Last verified: 2026-04-13
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

There are ongoing twin-summon experiments in the native spell runtime, but they are not yet the supported player-facing path.

Use them as lab/debug work only until the shell-bank patch is installed and validated.

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

1. build and install the local shell-bank client patch
2. grant `940000` or `940001` through the workbench
3. validate the visible shell path:
   - spellbook entry
   - cast behavior
   - clean failure UX when gated
   - friendly summon
   - recast / dismiss / relog lifecycle
