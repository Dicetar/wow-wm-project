# SPELL_RUNTIME_SPLIT_MAP — Phase 0E.2

Dependency map of every anonymous-namespace state container in
`native_modules/mod-wm-spells/src/wm_spell_runtime.cpp` (8,381 ln) →
its owning spell family, derived from the enclosing function of every
read/write site (verified by precise nearest-definition attribution,
not name heuristics).

**Verdict: 0E.2 STOP GATE TRIGGERED.** The Broug subsystem shares
mutable per-player state across what the plan treated as four separate
split targets. The proposed file boundary is invalid as written and
needs a human decision before any family is moved.

## Containers (28)

### Clean single-family — separable as the plan proposed

| Container | Owner family |
|-----------|--------------|
| gBoneboundOmegaByPlayer | Bonebound |
| gBoneboundEchoHuntModeByPlayer | Bonebound |
| gBoneboundEchoHuntRadiusByPlayer | Bonebound |
| gBoneboundEchoCountAuraByPlayer | Bonebound |
| gBoneboundBleeds | Bonebound |
| gBoneboundAlphaEchoes | Bonebound |
| gBoneboundBleedCooldownByCaster | Bonebound |
| gBoneboundCleaveCooldownByCaster | Bonebound |
| gBoneboundPriestHealCooldownByCaster | Bonebound |
| gBoneboundPriestRenewCooldownByCaster | Bonebound |
| gBoneboundPriestShieldCooldownByCaster | Bonebound |
| gBoneboundPriestDpsCooldownByCaster | Bonebound |
| gBoneboundPriestDispelCooldownByCaster | Bonebound |
| gBoneboundPriestMassDispelCooldownByCaster | Bonebound |
| gBoneboundPriestDpsCastByCaster | Bonebound |
| gBoneboundEchoSeekTargetByCaster | Bonebound |
| gBoneboundWarriorEchoesSincePriestByPlayer | Bonebound |
| gIntellectBlockRatingByPlayer | Proficiency |
| gNightWatchersLensAuraAppliedByPlayer | NightWatchersLens |
| gNightWatchersLensMarksByTarget | NightWatchersLens |
| gLanathelStanceByPlayer | Lanathel |

> The Bonebound "multi-family" hits from the raw scan were generic
> numeric helpers (`ResolvePercentOfMaxHealth`, `ClampSpellBasePoint`)
> that are Bonebound-internal — not a second family. Bonebound /
> Alpha Echo / Priest Echo are one cohesive family (as the plan
> already groups them into one file).

### Cross-family — STOP-GATE containers (the Broug cluster)

Every Broug per-player/parry/stun map is read AND written by the
"Broug abilities" functions (Deflect, Skirmisher, CloudStep,
SilentMeridian, KillingIntentDomain, Predator, MarkedMeridian,
UniversalParry, CounterStance) **and** by the Guard/Lightness/
EmptyCourt Tick/Maintain/Handle functions **and** read by the Core
dispatcher (`CheckShellCast`, `ShouldAllowShellDefaultEffect`):

| Container | Families touching it (verified) |
|-----------|-------------------------------|
| gBrougGuardByPlayer | BrougGuard · Broug-abilities (UniversalParryRoll, VulnerableCaster, TryBrougDeflect, SkirmisherMark, DeflectCounterStance, Deflect) · Core (CheckShellCast) |
| gBrougCounterStanceToggleOffByPlayer | BrougGuard · Broug-abilities (DeflectCounterStance) · Core (ShouldAllowShellDefaultEffect, CheckShellCast) |
| gBrougDeflectedStunUnits | BrougGuard (AuraRemove) · Broug-abilities (EnsureBrougDeflectedStun, UpdateBrougForcedStuns) |
| gBrougPendingForcedParryByVictim | BrougGuard (MeleeOutcome) · Broug-abilities (ExecuteBrougDeflect, TryQueueBrougUniversalMeleeParry) |
| gBrougLightnessByPlayer | BrougLightness · Broug-abilities (CloudStep, SilentMeridianKillWindow, TryConsumeBrougMarkedMeridian) · Core (CheckShellCast) |
| gBrougLightnessPreserveVulnerableByVictim | BrougLightness · Broug-abilities (TryConsumeBrougMarkedMeridian) |
| gBrougEmptyCourtByPlayer | BrougEmptyCourt · Broug-abilities (ResolveBrougKillingIntentDurationMs, ApplyBrougPredatorHeal, ApplyBrougSuppressedIncomingPressure) |

## Why this changes the split boundary

The plan (0E target list) proposed four separate Broug TUs:
`wm_spell_broug_guard.cpp`, `wm_spell_broug_lightness.cpp`,
`wm_spell_broug_empty_court.cpp`, `wm_spell_broug_abilities.cpp`.

But the "abilities" (CloudStep, SilentMeridian, KillingIntentDomain,
Predator, Deflect, Skirmisher, UniversalParry, CounterStance) are not
an independent family — they are the *verbs* of the Guard / Lightness /
EmptyCourt *stances*, mutating those stances' per-player runtime state
directly. Splitting them into a separate TU would require either
exposing all seven Broug state maps across TUs (breaks the
internal-linkage encapsulation that motivated the split) or moving
each map's owner arbitrarily (the maps don't have a single owner).

Bonebound, Proficiency, NightWatchersLens, Lanathel remain cleanly
separable exactly as the plan describes.

## Recommended boundary revision (for user decision)

Collapse the four Broug TUs into **one** `wm_spell_broug.cpp` owning
the whole Broug subsystem + its seven shared maps. Resulting 0E target
set:

- `wm_spell_runtime.cpp` → config, IsPlayerAllowed, CheckShellCast,
  ExecuteShellBehavior dispatcher, PollDebugRequests, LoadBehaviorRecord
- `wm_spell_internal.{h,cpp}` → SHARED generic helpers only
  (ResolvePercentOfMaxHealth, ClampSpellBasePoint, counter/JSON, math)
- `wm_spell_bonebound.cpp` → Bonebound / Alpha Echo / Priest Echo
- `wm_spell_proficiency.cpp` → IntellectBlock / CombatProficiencies
- `wm_spell_broug.cpp` → **entire** Broug system (Guard + Lightness +
  EmptyCourt + all Broug abilities + the 7 shared Broug maps)
- `wm_spell_night_watchers_lens.cpp` → NightWatchersLens
- `wm_spell_lanathel_stance.cpp` → LanathelStance

This keeps every shared map inside a single TU (internal linkage
preserved), still removes ~6,000 lines from the monolith, and is the
minimal change to the plan that the dependency data supports.

Generated 2026-05-19 by the 0E.2 mapper
(`artifacts/phase0d/spellmap.py` + precise enclosing-fn verification).
