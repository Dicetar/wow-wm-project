# Spell Shell Bank V1

This note fixes the exact gap between:

- "custom behavior on a reused stock spell"
- and "a truly new player-facing WM ability"

## Short truth

For a **truly new** WM ability on a 3.3.5 client, we need both:

1. a **client-visible shell bank**
2. a **native server behavior registry**

Without the shell bank, WM can only hijack an existing client-known spell.

That is why the first twin-skeleton prototype missed the mark:

- it reused `Summon Voidwalker`
- it changed behavior, but it was not a new visible spell

That path is retired. The current Bonebound Alpha debug/native lane binds behavior to WM-owned shell `940001` and explicitly removes WM script bindings from stock carriers such as `697` and `49126`.

## Hard pet constraint

Stock AzerothCore exposes a **single real pet slot** for the player.

You can see the singular pet model in core code:

- [Player.h](D:/WOW/WM_BridgeLab/src/azerothcore/src/server/game/Entities/Player/Player.h)
- [Player.cpp](D:/WOW/WM_BridgeLab/src/azerothcore/src/server/game/Entities/Player/Player.cpp)

Important signals:

- `GetPetGUID()`
- `m_temporaryUnsummonedPetNumber`
- resummon logic built around one stored pet

So WM should target one of these two designs:

### Recommended

- **one true permanent skeleton pet**
- plus **one linked guardian / companion skeleton** if we still want a pair fantasy

This preserves the actual pet bar and normal warlock summon behavior.

### Expensive alternate

- deep multi-pet core rewrite

This is not a small spell feature. It changes engine assumptions and pet control behavior.

## Final WM spell architecture

### 1. Client shell bank

Repo contract:

- [spell_shell_bank.json](D:/WOW/wm-project/control/runtime/spell_shell_bank.json)

This defines reserved visible shell families like:

- `summon_pet`
- `summon_companion`
- `self_buff`
- `offensive_bolt`
- `passive_aura`
- `pet_active`

Current bank sizing default:

- 1000 slots per family
- 6 families
- 6000 pre-seeded shell ids in one client patch generation pass

That means we do not patch the client once per spell. We patch the client with a large shell bank once, then spend those ids server-side for a long time.

These are not live client assets yet.
They are the repo-owned contract that the future client patch must match.

The repo now also provides a range-driven patch-plan export:

- `python -m wm.spells.export_patch_plan --summary`

That export expands all 6000 shell ids from the family ranges and then overlays named shells like `940000` and `945000` with their WM-specific metadata.

### 2. Native behavior kinds

The native side should own fixed behavior kinds, for example:

- `warlock_pet_skeleton`
- `guardian_skeleton_pair`
- `scaled_aura`
- `scaled_projectile`

WM fills typed parameters.
C++ executes.

### 3. WM publish / grant path

For a real new WM ability:

1. claim a shell from the shell bank
2. bind that shell to a native behavior kind
3. teach the shell directly or grant it after a quest reward
4. audit and retire it later through WM control

## What "do it right" means for the requested summon

Your requested summon is best modeled as:

- visible shell family: `summon_pet`
- behavior kind: `warlock_pet_skeleton`
- runtime shape:
  - one true permanent skeleton pet
  - optional second skeleton as guardian/companion if we keep the pair idea
  - stats scale from intellect + spell power

That is the correct next implementation lane.

Current status:

- `WORKING`: shell `940001` is bound to `summon_bonebound_alpha_v3` in the bridge-lab DB
- `WORKING`: Alpha is the one true persisted pet; Omega is retired from the release lane
- `WORKING`: total intellect is added to Alpha stats and shadow spell power is added to Alpha attack power
- `PARTIAL`: Alpha low physical bleed and echo proc are implemented and built, but live combat proof is pending
- `PARTIAL`: the visible player-facing spell remains blocked on installing and validating the shell-bank client patch

Do not replace or reuse `Summon Voidwalker`, `Raise Ghoul`, or any other stock spell as the permanent WM carrier for this behavior.
