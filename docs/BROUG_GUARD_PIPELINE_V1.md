# Broug Guard Pipeline V1

Status: `WORKING`

Scope: Broug `5405` first. Do not broaden to playerbots or class defaults.

## Current Release Slice

BridgeLab prep status on 2026-04-30: repo tests `WORKING`, build/deploy `WORKING`.

Gameplay status on 2026-05-01: user live proof accepted the current Broug quest and ability slice as working. Quests `910180` and `910181` are done, and the ability set is accepted as working for Broug's current scope. Future work should treat this as a proven strategy/reference lane unless a concrete regression is reported.

Deflect rework deployed to BridgeLab on 2026-05-01: repo tests, SQL, client patch install, server DBC staging, native build, worldserver deploy, native runtime correction, and live user acceptance are `WORKING` for the current Broug slice.

Counterstrike Stance work on 2026-05-01 adds fresh shell `946605` to make Deflect's automatic window-end counterattack player-toggleable. The latest correction makes it a real shapeshift-style stance aura with stance bar order `1`, not a DB-backed pseudo-toggle. Repo tests, native build, SQL, server DBC staging, client MPQ install, worldserver deploy, and user gameplay acceptance are `WORKING` for Broug's current scope.

- `2026_04_30_02_wm_spell_broug_deflect_rewards.sql`, failed `2026_04_30_03_wm_spell_broug_skirmisher_mark_active.sql`, and replacement `2026_04_30_04_wm_spell_broug_skirmisher_shot.sql` are applied on BridgeLab world DB `127.0.0.1:33307`.
- server `Spell.dbc` staged castable rows for `946603` and `946802`, then refreshed `946800`, `946098`, and `946802` after Broug tooltip/feedback polish and targeted Skirmisher replacement; latest Skirmisher movement correction restaged `946098`.
- client `patch-z.mpq` rebuilt and installed with the refreshed shell rows; extracted client payload verifies `946603` icon `278`, `946800` icon `26`, no aura/effect/duration payload on Deflect, and `946098` with no ranged-slot flag or movement interrupt flags.
- BridgeLab worldserver restarted to pid `18080` with `WmSpells.PlayerGuidAllowList = "5405,5406"`.
- Broug native ping request `601` returned `pong`.
- focused Broug/DBC tests passed: `38 passed`; full tests passed: `542 passed`.
- stale saved Broug aura row `character_aura(guid=5405, spell=946603)` from the previous self-aura shell was deleted after the no-aura DBC patch.
- Broug currently has base `946800` and targeted active `946098` learned; `946801` and failed self-aura toggle `946604` are retired/revoked, and `946603,946802` must be earned through the linked quests, not pre-granted.
- `2026_05_01_00_wm_spell_broug_deflect_rework.sql` adds fresh visible target states `946200` and `946201` and updates `946603` to the animation-timed rooted guard config.
- `2026_05_01_01_wm_spell_broug_deflect_counter_stance.sql` added the first stance-style shell `946605`; `2026_05_01_03_wm_spell_broug_counterstrike_stance_aura.sql` corrects it to a real aura gate and leaves `wm_broug_deflect_counter_stance` as legacy metadata only.
- focused Broug/shell/client/server DBC tests passed: `40 passed`; full tests passed: `544 passed`.
- BridgeLab worldserver rebuilt and redeployed to pid `15772` with `WmSpells.PlayerGuidAllowList = "5405,5406"`; Broug native ping request `603` returned `pong`.
- Counterstrike Stance focused tests passed: `42 passed`; full tests passed: `546 passed`. The `650ms` Deflect window retune SQL applied and verified `window_ms=650`; latest native build passed with one existing duplicate-loader warning and `0` errors. Client `wow.exe` pid `27228` was stopped because it locked `patch-z.mpq`; refreshed client patch installed, server `Spell.dbc` staged `946605=True`, Broug `character_spell(5405, 946605)` inserted, and BridgeLab worldserver redeployed to pid `34520`.
- Counterstrike real-stance correction focused tests passed: `43 passed`; full suite passed: `551 passed`. Root cause was DBC materialization writing `duration_index` to field `37` (`MaxLevel`) instead of real `SpellEntry.DurationIndex` field `40`, leaving `946605` as an Arcane Intellect/Mage-style timed buff. The materializer now writes field `40`; SQL correction applied and verified `counterattack_requires_aura=true`, `stance_aura_spell_id=946605`, `stance_form_id=13`; server and extracted client `Spell.dbc` rows stage `946605` with stance category `47`, permanent `duration_index=21`, `power_type=3`, `effect=6`, `aura=36`, `misc=13`, Rogue family `8`, `damage_class=0`, `prevention_type=0`, `active_icon=132`, and `stance_bar_order=1`. Client `patch-z.mpq` installed, stale saved timed `character_aura(guid=5405, spell=946605)` was deleted, native build passed with one existing duplicate-loader warning and `0` errors, and BridgeLab worldserver redeployed to pid `35284`.
- Deflected stack visibility/stun-release correction on 2026-05-01 is repo/build/deploy/client-patch/gameplay `WORKING` for the current Broug scope: focused Broug/client/server DBC tests passed (`43 passed`), full suite passed (`551 passed`), server `Spell.dbc`, client payload, and extracted MPQ all verify `946200` and `946201` with `duration=3/36`, `stack=255`, `effect=6`, `aura=4`, icon `558`. Native runtime now force-creates the harmless visible marker aura if normal `AddAura` is blocked by immunity, hooks `UNITHOOK_ON_AURA_REMOVE`, releases native forced stun when `Deflected` is removed/expires, and restarts creature attack against its victim after release. Native build passed with one existing duplicate-loader warning and `0` errors, BridgeLab worldserver redeployed to pid `24388`, and client `patch-z.mpq` was installed after the client closed.
- Deflected aura-owned stun correction on 2026-05-01 is server-runtime `WORKING` and gameplay `WORKING` for the current Broug slice after user live acceptance. User live proof first confirmed `Deflected` stack numbers rendered, then native runtime removed the separate forced-stun expiry timer and made `946201` `Deflected` the authority. While a tracked unit has the `Deflected` aura, runtime enforces `UNIT_STATE_STUNNED`, interrupts casts, and stops movement; when the aura is gone, runtime releases the native stun and restarts the creature against its current or selected victim. Focused Broug/shell tests passed (`13 passed`), full suite passed (`551 passed`), native build passed with one existing duplicate-loader warning and `0` errors, and BridgeLab worldserver redeployed to pid `12612`.

Fresh shell IDs:

- `946800` / `broug_universal_parry_v1` / `Impossible Guard`
- `946098` / `broug_skirmisher_shot_v1` / targeted active `Skirmisher's Mark`
- `946200` / `broug_vulnerable_v1` / `Vulnerable`
- `946201` / `broug_deflected_v1` / `Deflected`
- `946604` / `broug_skirmisher_mark_v2` / retired self-aura toggle `Skirmisher's Mark` / `BROKEN`, replaced by `946098`
- `946605` / `broug_deflect_counter_stance_v1` / `Counterstrike Stance`
- `946801` / `broug_mobile_marksman_v1` / retired passive `Skirmisher's Mark` / `BROKEN`, replaced by `946098`
- `946603` / `broug_deflect_v1` / `Deflect`
- `946802` / `broug_auto_retaliation_v1` / `Riposte Instinct`

Fresh quest/objective IDs:

- `910180` / `Broug: One Thousand Impossible Guards`
- `910181` / `Broug: One Thousand Deflections`
- `920104` / hidden parry kill-credit marker
- `920105` / hidden Deflect kill-credit marker

Server truth:

- `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_30_01_wm_spell_broug_guard_passives.sql`
- `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_30_02_wm_spell_broug_deflect_rewards.sql`
- `native_modules/mod-wm-spells/data/sql/world/updates/2026_05_01_00_wm_spell_broug_deflect_rework.sql`
- `native_modules/mod-wm-spells/data/sql/world/updates/2026_05_01_01_wm_spell_broug_deflect_counter_stance.sql`
- `native_modules/mod-wm-spells/data/sql/world/updates/2026_05_01_03_wm_spell_broug_counterstrike_stance_aura.sql`
- `wm_spell_shell`
- `wm_spell_behavior`
- `wm_spell_grant`
- `wm_broug_guard_counter`
- `wm_broug_deflect_counter_stance`
- `character_spell`
- `quest_template`, `quest_template_addon`, `quest_request_items`, `quest_offer_reward`
- `creature_template` hidden credit entries

Client truth:

- `control/runtime/spell_shell_bank.json`
- `client_patches/wm_spell_shell_bank/manifest.json`
- rebuilt `patch-z.mpq`
- staged server `Spell.dbc` rows for `946800`, `946098`, `946200`, `946201`, `946603`, `946605`, and `946802`

Grant command:

```powershell
$env:PYTHONPATH='src'
$env:WM_WORLD_DB_PORT='33307'
$env:WM_CHAR_DB_PORT='33307'
$env:WM_CHAR_DB_HOST='127.0.0.1'
$env:WM_WORLD_DB_HOST='127.0.0.1'
python -m wm.spells.broug_guard --player-guid 5405 --mode apply --summary
```

## Mechanics

`Impossible Guard` is a passive native guard, not stock Parry. If Broug has an active grant and a hostile attacker would deal melee, direct spell, or hostile periodic damage, native rolls:

```text
chance = base_chance_pct
       + strength * strength_to_chance_pct
       + agility * agility_to_chance_pct
       + expertise_pct * expertise_to_chance_pct
       + weapon_mastery_pct * weapon_mastery_to_chance_pct
       + attack_power * attack_power_to_chance_pct
chance = min(chance, max_chance_pct)
```

Current config is intentionally bloated for proof: base `30%`, strength `0.45%` per point, agility `0.45%` per point, expertise `2.5%` per 1% dodge/parry reduction, weapon mastery `0.25%` per current weapon-skill mastery percent, attack power `0.0%` per point, max `90%`. Weapon mastery is computed from the best equipped main/offhand weapon skill divided by Broug's current level cap, clamped to `125%`; it is not the Cataclysm-style Mastery stat.

On melee success, native queues a forced core parry outcome in `OnBeforeRollMeleeOutcomeAgainst` so the client should see `Parry` instead of the old damage-zero `Miss` path, then increments `wm_broug_guard_counter(5405, 'universal_parry')` when the parry outcome can be emitted. Direct spell and hostile periodic successes still mitigate through damage hooks; direct spell mitigation also sends `SPELL_MISS_PARRY`. This is the counter the 1000-parry quest must consume later.

Presentation polish deployed on 2026-04-30 clears the stock Block seed fields from Broug passive shell rows `946800` and `946802`: no shield requirement fields, no stock block effect, no stale dynamic block-chance tooltip line. The visible tooltip now states the custom chance formula. Old passive Skirmisher shell `946801` and failed self-aura toggle `946604` are retired and must not be reused.

Deflect rework deployed on 2026-05-01 makes the active iframe an animation-timed guard. Current defaults are `parry_pre_ms=100`, `parry_animation_ms=450`, `parry_post_ms=100`, for a `650ms` root/invulnerability window. Deflect suppresses Impossible Guard while active, clears queued forced parry, roots Broug, blocks hostile melee, direct spell damage, direct AoE spell damage, hostile periodic damage, and hostile debuff/DoT aura application. Each blocked hostile event applies one `946200` `Vulnerable` stack to that attacker/caster and increments `deflect_success` plus quest credit. If Broug has the live `946605` Counterstrike Stance aura when the window resolves, native counterattacks the first valid caught attacker with the existing Deflect weapon/AP damage formula and plays the melee attack animation when damage lands. Without that aura, Deflect skips its own counterattack so the `Vulnerable` stack remains available for Broug's next chosen damage source. The latest DBC correction keeps `946603` dispatch-only: dispel type, duration, effect, aura, base-point, and misc fields are all `0`, so casting Deflect must not leave a client buff.

`Counterstrike Stance` `946605` is a fresh self-cast stance shell, not a reused failed toggle. Client/server DBC apply a real `SPELL_AURA_MOD_SHAPESHIFT` aura using form `13`, stance category `47`, permanent `DurationIndex=21`, Rogue family `8`, `StanceBarOrder=1`, `DamageClass=0`, and `PreventionType=0`; the shell dispatcher explicitly allows the stock apply-aura effect for this spell. Native runtime no longer reads or writes `wm_broug_deflect_counter_stance.CounterattackEnabled` as gameplay state. The automatic Deflect counterattack is gated only by `player->HasAura(946605)` at window-end resolve time. Recasting while the stance aura is active suppresses default aura reapply, removes `946605`, and reports the stance inactive.

`Vulnerable` `946200` is a fresh visible debuff shell, not a stock reused carrier. It is undispellable, stackable (`StackAmount=255`), 60 seconds by default, and uses icon `558` from stock Forceful Deflection. Any next nonzero melee, spell, direct AoE, periodic, or Broug native direct damage consumes all stacks. Damage is multiplied by `1 + stack_count`, so each stack adds `+100%` damage taken. Consumption applies native forced stun for `1000ms * consumed_stack_count`.

`Deflected` `946201` is a fresh visible status shell with the same icon `558` and `StackAmount=255`, so the client can show stack numbers like Sunder Armor. Native forced stun remains the real control path. Runtime applies `Deflected` stacks equal to consumed `Vulnerable` stacks and extends the visible duration to the longer active forced-stun window. Stack count is preserved for future mechanics. `Deflected` aura removal/expiry releases the native forced stun and nudges creatures back into attacking their current victim so the stun cannot leave mobs inert.

Latest live correction makes `Deflected` aura presence the control contract: if `Deflected` is present, native enforces stun/cast stop/movement stop; if it is absent, native releases the stun. Do not reintroduce a separate wall-clock stun timer for this mechanic.

`Skirmisher's Mark` does not globally patch Auto Shot or Throw. Stock movement checks remain stock. Fresh targeted active shell `946098` is a unit-target projectile-shaped button, not a self-buff and not a toggle. The latest DBC row removes the inherited Throw ranged-slot flag and clears interrupt/aura/channel interrupt flags (`attrs=0x410010`, `interrupt=0`, `aura_interrupt=0`, `channel_interrupt=0`) so the client/server cast shape should not fail because Broug is moving. Casting it on a hostile target fires one native ranged/thrown attack immediately. It requires an equipped thrown/bow/gun/crossbow weapon and a target in `0-35yd`, works while Broug is moving, and uses the equipped ranged weapon speed as the readiness gate before the next shot.

```text
damage = normal ranged auto-attack damage
       * damage_pct
```

Damage is built through the core ranged auto-attack damage path, including ranged weapon damage and normal ranged attack-power scaling, then native applies ranged auto proc flags. Counter key is `skirmisher_shot_hit`. The runtime plays the matching thrown/bow/gun emote and a ranged feedback sound before dealing the native hit. The shell dispatch script prevents stock seed projectile damage so only the WM native shot lands.

## Quest Chain

Repo/build/deploy status is `WORKING`; gameplay status is `WORKING` for Broug's current scope after user live acceptance on 2026-05-01.

Quest 1: parry 1000 hostile damage events.

- quest ID: `910180`
- starter/ender: Marshal McBride `197`
- visible objective source: hidden kill-credit creature `920104`
- validation/counter source: `wm_broug_guard_counter.CounterKey = 'universal_parry'`
- reward: fresh active self spell `946603` / `Deflect`, plus fresh stance shell `946605` / `Counterstrike Stance`
- reward grant path: native `OnPlayerCompleteQuest` learns the shell and inserts active `wm_spell_grant`

Deflect reward:

- active instant ability
- no global cooldown
- `0.5s` cooldown target unless user calibrates differently
- costs `5` energy
- opens a short invulnerability window
- roots Broug for the configured guard window and plays parry feedback during the animation span
- if hostile damage or hostile aura application lands during the window, prevent/remove it, increment `deflect_success`, suppress Impossible Guard for that iframe, and apply one `Vulnerable` stack to the attacker/caster
- at the iframe end, counterattack the first valid caught attacker only when Broug has the live `946605` Counterstrike Stance aura; that damage consumes `Vulnerable`, applies `Deflected`, and applies native forced stun
- without the stance aura, the window ends without Broug's automatic hit, preserving `Vulnerable` for the next chosen damage source
- stun uses native `SetControlled(true, UNIT_STATE_STUNNED)` plus `946201` aura presence as the live release contract

Quest 2: deflect 1000 hostile damage events.

- quest ID: `910181`
- starter/ender: Marshal McBride `197`
- visible objective source: hidden kill-credit creature `920105`
- validation/counter source: `wm_broug_guard_counter.CounterKey = 'deflect_success'`
- reward: fresh passive shell `946802` / `Riposte Instinct`
- reward behavior: native strike-back damage after counted Impossible Guard parries, with a short native cooldown

## Preservation Criteria

`Impossible Guard` stays `WORKING` when live proof continues to show:

- Broug has `946800` in `character_spell`.
- Broug sees the passive in the spellbook after client patch restart.
- The tooltip does not show `Requires Shield` or stock block chance text.
- Hostile melee, direct spell, and hostile periodic effects can be reduced to `0`.
- Hostile melee successes show `Parry` and a parry animation/sound in normal front-facing melee.
- `wm_broug_guard_counter` increments for successful custom parries.
- The behavior remains scoped to Broug and active `wm_spell_grant`.

`Skirmisher's Mark` stays `WORKING` when live proof continues to show:

- Broug has `946098` in `character_spell`, and old `946801` plus failed `946604` are absent or revoked.
- Broug sees the active targeted skill in the spellbook after client patch restart.
- The tooltip does not show `Requires Shield`, stock block chance text, or any self-buff/toggle wording.
- With a thrown/bow/gun/crossbow equipped, casting the skill on a hostile target fires one ranged/thrown hit while moving.
- Recasting before the ranged weapon-speed readiness gate fails cleanly as not ready.
- The native ranged/thrown shot has visible thrown/bow/gun feedback.
- Stationary stock ranged behavior remains untouched.
- The behavior remains scoped to Broug and active `wm_spell_grant`.

If any of those regress, move only the affected ability back to `PARTIAL` or `BROKEN` and keep failed visible IDs retired.

`Deflect` stays `WORKING` when live proof continues to show:

- Broug has `946603` in `character_spell` after completing `910180`.
- The button is visible after client patch restart and costs `5` energy.
- Casting opens a short window without triggering global cooldown.
- Casting does not add a visible Deflect aura/buff.
- Broug is rooted for the configured guard window and plays parry feedback during it.
- Hostile melee, direct spell, direct AoE spell, and hostile periodic damage landing during the window are reduced to `0`.
- Hostile debuff/DoT aura applications during the window are removed from Broug.
- Impossible Guard does not steal the caught hit while the Deflect window is active.
- Each blocked attacker/caster receives one visible `Vulnerable` stack.
- The first valid caught attacker takes counter damage at window end.
- Removing/canceling the `946605` stance aura makes Deflect skip its own counter damage while still applying `Vulnerable`.
- Re-entering Counterstrike Stance restores the automatic window-end counterattack.
- Counter damage consumes all `Vulnerable` stacks, applies visible `Deflected` stacks, and applies forced stun for `1000ms` per consumed stack.
- Broug plays a melee attack animation/sound at the same moment as the reflected damage.
- `wm_broug_guard_counter(5405, 'deflect_success')` and quest credit `920105` increment.

`Riposte Instinct` stays `WORKING` when live proof continues to show:

- Broug has `946802` in `character_spell` after completing `910181`.
- Counted Impossible Guard parries automatically strike back.
- The auto-retaliation remains scoped to Broug and active `wm_spell_grant`.
