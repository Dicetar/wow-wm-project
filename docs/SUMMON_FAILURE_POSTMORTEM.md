Status: BROKEN
Last verified: 2026-04-15
Verified by: Codex
Doc type: postmortem

# Summon Failure Postmortem

This postmortem covers the failed attempt to build WM-owned summons by reusing stock live spell carriers.

Current supported state lives in:

- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)
- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)

## Objective

The original goal was to create a real WM-owned summon and, later, a broader spell platform for arbitrary WM abilities.

The specific experiment that failed was the attempt to get there without doing the client-shell work, by hijacking stock spell IDs and layering custom summon behavior under them.

## What happened

### Attempt class 1: stock warlock summon carriers

Carrier used:

- `697`

Result:

- stock warlock summon behavior leaked through
- normal class summons were altered
- WM behavior was never truly isolated from the stock spell

### Attempt class 2: other stock summon carriers

Carriers used:

- `8853`
- `57913`
- `49126`

Observed failures across those attempts:

- visible spell but no reaction on click
- summon path leaked stock default behavior
- recast and dismiss behavior were unstable
- pet control and resource model were inconsistent
- saved pet state polluted retests

Worst-case failure:

- a live path spawned a hostile `Scourge Corpserender`

### Attempt class 3: stock aura carrier as a visible shell

Carrier used:

- `7302`

Result:

- the player cast `Frost Armor`
- WM summon behavior did not happen

Why:

Current dispatch interception in [wm_spell_shell_scripts.cpp](../native_modules/mod-wm-spells/src/wm_spell_shell_scripts.cpp) only blocks dummy and summon effects:

```cpp
OnEffectLaunch += SpellEffectFn(..., EFFECT_0, SPELL_EFFECT_DUMMY);
OnEffectLaunch += SpellEffectFn(..., EFFECT_0, SPELL_EFFECT_SUMMON_PET);
OnEffectLaunch += SpellEffectFn(..., EFFECT_0, SPELL_EFFECT_SUMMON);
OnEffectHit += SpellEffectFn(..., EFFECT_0, SPELL_EFFECT_DUMMY);
OnEffectHit += SpellEffectFn(..., EFFECT_0, SPELL_EFFECT_SUMMON_PET);
OnEffectHit += SpellEffectFn(..., EFFECT_0, SPELL_EFFECT_SUMMON);
AfterCast += SpellCastFn(...);
```

`7302` is a stock aura spell, so its aura behavior still fired. That was a proof that visible stock carriers are not a safe shell strategy.

## Root causes

### 1. Trying to avoid client truth

The core mistake was trying to get true client-visible new abilities without committing to a proper client shell bank or client patch path.

That forced repeated stock-carrier experiments.

### 2. Prototype poisoning from stock spell IDs

Stock spells in AzerothCore/TrinityCore are not neutral IDs. They carry existing server and client behavior. Reusing them as WM carriers created hidden collisions and false positives.

### 3. Dirty summon state polluted retests

Saved pet rows in `character_pet` and related tables made later tests unreliable until cleanup tooling was added.

### 4. Mixed chassis assumptions

Different pet behaviors and overlays were mixed during the experiment, which made recast, dismiss, control, and resource behavior inconsistent.

## Later fixed bug: Omega stat recalculation order

Status: `WORKING`

On 2026-04-15, `Bonebound Omega` showed base Voidwalker-style health (`33/40`) even though the shell `940001` behavior config and Alpha pet state were correct.

Root cause:

- Omega is a `TempSummon`.
- The runtime wrote Alpha-derived health/damage, then called owner-transfer/stat recalculation.
- `UpdateAllStats()` restored creature-template max health for the temporary summon.

Fix:

- Use one shared Omega runtime helper for create and sync.
- Apply owner-transfer/template stat recalculation first.
- Apply final Alpha-derived Omega health afterward.
- Preserve current health percentage during sync and refill only on fresh spawn.
- Apply weapon damage and mirrored attack power after the final health write.

Do not repeat:

- Do not treat base-template Omega health as a SQL/config issue before checking native stat recalculation order.
- Do not set final Omega max health before `ApplyOwnerTransferBonuses()`.
- Do not keep separate create/sync stat code paths for Omega.

## What is retired

Retired as permanent WM spell carriers:

- `697`
- `8853`
- `57913`
- `49126`
- `7302`

Retired as implementation strategy:

- visible stock-carrier testing for WM abilities
- carrier-cancellation hacks as the main path
- using `mod-wm-prototypes` as the main summon lane

## What remains useful

The experiment was not a total loss. These parts are still valid:

- shell-bank contract in `control/runtime/spell_shell_bank.json`
- client patch workspace in `client_patches/wm_spell_shell_bank/`
- stable native spell runtime in `mod-wm-spells`
- shell-bound behavior storage:
  - `wm_spell_shell`
  - `wm_spell_behavior`
  - `wm_spell_grant`
  - `wm_spell_debug_request`
- workbench publish, grant, ungrant, and debug invoke flows
- Jecia-only cleanup tooling for stale summon state

## Hard conclusions

- Do not use stock live spell IDs as permanent WM ability carriers again.
- Do not describe stock-carrier summon tests as "almost working."
- The only supported behavior-iteration path until the client shell patch is installed is the debug/native lane.
- Player-facing WM spells require a real shell-bank/client patch path.

## Next safe path

1. keep spell behavior work inside `mod-wm-spells`
2. use the lab debug invoke path for behavior tuning
3. build and install the WM shell-bank patch for player-facing shells
4. only then validate spellbook, action bar, tooltip, recast, and lifecycle behavior on real WM shell IDs
