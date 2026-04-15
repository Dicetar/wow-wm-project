Status: BROKEN
Last verified: 2026-04-16
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

## Later failure: Omega TempSummon parity

Status: `BROKEN`

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

Later live evidence on 2026-04-16 showed this did not solve true combat parity:

- Alpha melee was around `120`.
- Omega melee remained around `9`.
- Omega mana remained around `20`.
- Copying Alpha final visible fields and powers onto Omega did not reliably affect the Creature/TempSummon combat path.

Structural conclusion:

- Omega was a `TempSummon`/Creature, not a real pet.
- Creature stat/resource/damage calculation is not the same as the Alpha `Pet` path.
- Visible target-frame fields are not sufficient proof of actual swing damage or resource parity.

Decision:

- Retire Omega from the shell `940001` release lane.
- Move current behavior to single Alpha on `summon_bonebound_alpha_v3`.
- If a second combat companion returns later, design it as a true supported pet/guardian model or an explicit hook-backed companion, then prove health, mana, and damage output in the lab.

Do not repeat:

- Do not treat base-template Omega health as a SQL/config issue before checking native stat recalculation order.
- Do not set final Omega max health before `ApplyOwnerTransferBonuses()`.
- Do not keep separate create/sync stat code paths for Omega.
- Do not claim TempSummon parity from copied fields without live damage/resource proof.

## Later failure: Alpha echo inherited Voidwalker template truth

Status: `BROKEN`

On 2026-04-16, Alpha echo procs appeared in-game as `Voidwalker` with roughly `60` health, even though the live runtime renamed and visually reskinned the summon after spawn.

Root cause:

- The echo was spawned from stock creature template `1860`.
- Client target frames and nameplates use creature-template truth; `SetName()` after spawn is not a reliable replacement for a real template row.
- The runtime copied Alpha health before `ApplyOwnerTransferBonuses()`.
- `ApplyOwnerTransferBonuses()` calls `UpdateAllStats()`, which restored creature-template health for the temporary summon.

Fix:

- Add WM creature template `920101` named `Bonebound Alpha Echo`.
- Spawn echo procs from `alpha_echo_creature_entry=920101`, falling back to the Alpha creature only if the explicit echo entry is missing from config.
- Apply owner-transfer/stat recalculation first.
- Copy Alpha final health, power, stats, resistances, attack power, weapon damage, and visible melee fields after recalculation.
- Randomize echo follow angle and distance per proc so multiple echoes do not merge into one follow point.

Do not repeat:

- Do not spawn WM-named temporary companions from stock creature entries and assume runtime rename is enough.
- Do not write final health or damage fields before a code path that calls `UpdateAllStats()`.
- Do not mark echo behavior `WORKING` from visual model alone; validate target-frame name, health, and melee output in live combat.

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
