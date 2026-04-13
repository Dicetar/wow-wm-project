Status: PARTIAL
Last verified: 2026-04-13
Verified by: Codex
Doc type: reference

# mod-wm-spells

Stable native spell-shell / behavior lane for WM-authored abilities.

This module replaces the old "reuse stock spell carriers" approach with two explicit lanes:

- player-facing shell lane: WM-only shell spell IDs from `control/runtime/spell_shell_bank.json`
- lab debug lane: DB-backed behavior invocation through `wm_spell_debug_request`

## Current scope

- `summon_bonebound_servant_v1`
  - one real persistent pet on a generic demon-style backend
  - skeleton visuals layered on top
  - corpse-required cast check
  - lab debug invocation path

## Runtime data

This module owns the stable spell-platform tables in `acore_world`:

- `wm_spell_shell`
- `wm_spell_behavior`
- `wm_spell_grant`
- `wm_spell_debug_request`

## Operator path

Repo-side work goes through the workbench:

```powershell
python -m wm.content.workbench new-summon-shell --shell-key bonebound_servant_v1 --player-guid 5406
python -m wm.content.workbench publish-shell --draft-json .wm-bootstrap\state\content-drafts\shell-bonebound_servant_v1.json --mode apply
python -m wm.content.workbench grant-shell --player-guid 5406 --shell-key bonebound_servant_v1 --reload-via-soap --mode apply
```

Lab-only behavior invocation without teaching the shell:

```powershell
python -m wm.content.workbench invoke-shell-behavior --player-guid 5406 --shell-key bonebound_servant_v1 --mode apply
```

The debug lane now resolves the shell-bound behavior config from `wm_spell_behavior` for the requested shell spell ID, so debug invocation and visible shell casts hit the same native behavior contract instead of two separate summon paths.

## Important boundary

This module is the stable spell behavior runtime. Experimental carrier hacks remain in `mod-wm-prototypes` and should not be extended.

Current path status, including successful and failed summon experiments, is documented in:

- [D:/WOW/wm-project/docs/SUMMON_SPELL_PLATFORM_STATUS.md](D:/WOW/wm-project/docs/SUMMON_SPELL_PLATFORM_STATUS.md)
- [D:/WOW/wm-project/docs/SUMMON_FAILURE_POSTMORTEM.md](D:/WOW/wm-project/docs/SUMMON_FAILURE_POSTMORTEM.md)

Current truth:

- `mod-wm-spells` is the supported native runtime
- the visible player-facing shell path is still blocked on the client shell-bank patch being installed
- debug/native invoke is the supported iteration lane until that patch exists
