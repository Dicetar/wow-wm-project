Status: PARTIAL
Last verified: 2026-05-01
Verified by: Codex
Doc type: handoff

# WM Project Handoff For Next Chat

Repo: `D:\WOW\wm-project`
Branch: `main`, tracking `origin/main`
State: dirty as hell. Do not stage broadly. Do not "clean up" unrelated files.

## Read First

Read these before touching code:

1. `AGENTS.md`
2. `docs/README_OPERATIONS_INDEX.md`
3. `docs/CODEX_WORKING_RULES.md`
4. `docs/WM_PLATFORM_HANDOFF.md`
5. `docs/WORK_SUMMARY.md`
6. `docs/ROADMAP.md`
7. `docs/SUMMON_SPELL_PLATFORM_STATUS.md`
8. `docs/SUMMON_FAILURE_POSTMORTEM.md`
9. `docs/CUSTOM_ID_LEDGER.md`
10. `docs/native-bridge-action-bus.md`
11. `docs/NEXT_CHAT_HANDOFF.md`
12. `docs/ARC_REWARD_FACTORY_V1.md` if present

Trust current-state docs and postmortems over old phase docs. Transcript files are history, not operating instructions.

## Non-Negotiables

- Never reuse failed visible IDs. Fresh ID + retire/cleanup old ID.
- Python owns decisions, validation, audit, publishing, arcs, state.
- Native owns sensing, typed actions, runtime effects.
- No freeform SQL/GM/LLM mutation lane as architecture.
- BridgeLab player is `5406` / Jecia.
- BridgeLab MySQL is `127.0.0.1:33307`, not `3306`.
- Preserve dirty worktree. Many files were already changed before the last chat.

## Current Priority

Immediate priority is to move back to roadmap feature work using the proven strategies documented in [Working Strategies V1](WORKING_STRATEGIES_V1.md). The user's new-character pipeline test on Broug is accepted as working: watcher scoping, combat proficiencies, linked quests, custom ability rewards, Impossible Guard, Skirmisher's Mark, Deflect, Counterstrike Stance, Vulnerable/Deflected states, and Riposte are no longer the active debugging loop unless a concrete regression is reported.

Bonebound Restorer movement/casting is live-proven by the user as working. The remaining Echo x3-range DPS spell clone and Echo Destroyer movement-speed retune stay `PARTIAL` until live retest, but they are no longer the active request unless the user asks for them.

Latest deployed Echo changes:

- Restorers keep seek target for 30s.
- Restorers move at `1.5x` Alpha speed.
- Destroyers move at `1.75x` Alpha speed through `alpha_echo_movement_speed_multiplier`.
- Restorers use `MoveChase` instead of enemy `MoveFollow`.
- Restorer seek movement is fixed by `Attack(victim, false)` plus no pre-chase `AttackStop()`.
- Restorer DPS moved off stock Mind Blast `8092` onto fresh WM-owned clone `946099`.
- `946099` is cloned from `8092` in server Spell.dbc with the same cast/effect/visual/icon fields and `RangeIndex=157` (`90yd`, 3x stock Mind Blast `30yd`).
- Stock Mind Blast `8092` is verified still default `RangeIndex=4`.
- `wm echo status` / `wm echo state` is now deployed as a scoped diagnostic. It reports seek/follow mode, radius, tracked/live Echo counts, Restorer target/ready/casting/pending/cooldown/range/LOS counts, DPS spell-info availability, and first-Restorer target/range/cast details.
- Client patch package was rebuilt and installed after the client closed. Extracted `patch-z.mpq` verification found `946099:range=157:cast=16:effect0=2:visual2=3057:icon=95:name=Echo Mind Blast`.

This was deployed after the user reported "Good, its working. But Restorers definitely need more range on their damage spell. Make it x3." and then "increase movespeed of Destroyers - they engage slower than casters".

## What To Do Next

AHBot was the latest infrastructure interruption before returning to features:

- Official `azerothcore/mod-ah-bot` was already current at `a680cc1`, but the long config the user pointed at is from `NathanHandley/mod-ah-bot` / Auction Bot Plus.
- BridgeLab active module is now swapped to `NathanHandley/mod-ah-bot` commit `1822d96072a5168a775551fa5017ec947c9fbf7b`, with `src/wm_loader_compat.cpp` preserved for the generated `mod-ahbot` loader name.
- `Configure-BridgeLabRuntime.ps1` now rebases legacy short AHBot configs from the fork's long dist file and writes the Auction Bot Plus profile: shared neutral AH, `40000` Neutral lots, Alliance/Horde `0`, seller and buyer enabled on GUID `1`, half AH deposit/cut in `worldserver.conf`, buyout `-30%/+20%`, bid `70-100%` of buyout, custom WM IDs disabled, and poor/generic/quest/key/misc/quiver weights zeroed.
- `scripts/repack/Apply-LatestBaselineConfigDefaults.ps1` carries the same profile for the non-BridgeLab run tree.
- `sql/bootstrap/bridge_lab_ahbot_market.sql` remains as legacy fallback and now disables poor, quest/key/misc, custom, deprecated/test/NPC-equip rows.
- Build/deploy proof on 2026-05-01: forced CMake reconfigure after stale old AHBot source list, native build succeeded with the existing duplicate-loader warning only, old 40,000 AHBot auctions were purged while worldserver was stopped, BridgeLab worldserver restarted to pid `36324`, and DB proof showed neutral AH repopulating from `6000` to `16000` lots owned by GUID `1` with zero bad class/poor/custom rows and zero zero-price rows. Full tests passed: `554 passed`.
- Gameplay-browser proof is still `PARTIAL` until the user opens the AH and confirms the market feels useful.

The previous user direction to log into another character and run the full WM pipeline produced the Broug proof below. Do not restart that pipeline from scratch unless the user asks for a new character.

New marker workflow is repo/build/deploy `WORKING`; live marker proof is still `PENDING` until the user applies the marker on the new character:

- `mod-wm-bridge` now has an opt-in aura sensor for player marker spells, gated by `WmBridge.Emit.Aura` and `WmBridge.Emit.AuraSpellAllowList = "946602,132,687,770"`.
- Default marker is WM-owned shell `946602` (`WM Watcher Beacon`), an undispellable no-duration dummy aura with no gameplay effect. Stock `132` is only a compatibility fallback.
- Follow-up requested by user: change the `946602` icon away from the current eye icon to a cleaner Dalaran/arcane/logo-like icon in the next presentation-only DBC refresh. Do not change the marker ID or behavior for this cosmetic pass.
- Current deployed marker proof on 2026-04-30: BridgeLab worldserver pid `30756`, client `patch-z.mpq` rebuilt/installed after the client closed, server and extracted client DBC rows both verify `946602:dispel=0:duration=0:effect1=6:basepoints1=0:aura1=4:icon=135:visual1=0:visual2=0`, and native ping request `581` returned `pong`.
- `python -m wm.sources.native_bridge.configure --config-path D:\WOW\WM_BridgeLab\run\configs\modules\mod_wm_bridge.conf --allow-all --reload-via-soap --summary` enables temporary wildcard observation when the new character GUID is unknown.
- `python -m wm.sources.native_bridge.player_marker scan --spell-id 946602 --since-seconds 300 --summary` lists recent marker aura applications.
- `python -m wm.sources.native_bridge.player_marker scope-latest --spell-id 946602 --since-seconds 300 --summary` scopes the latest marked player in `wm_bridge_player_scope`.
- `python -m wm.sources.native_bridge.configure --config-path D:\WOW\WM_BridgeLab\run\configs\modules\mod_wm_bridge.conf --clear --reload-via-soap --summary` turns wildcard config observation back off; DB-backed scope remains in `wm_bridge_player_scope`.
- For unknown-character discovery only, wildcard bridge observation may be used briefly, then must be turned off. Do not leave `WmBridge.PlayerGuidAllowList = "*"` running.

After marker discovery identifies a future new character, start the normal native watcher for that GUID and proceed with watcher, bounty, custom item reward, ability, and passive testing. Broug's current slice is already accepted.

Current Broug status:

- Marker discovery found `5405` / `Broug` through aura `946602`; wildcard observation was cleared immediately after scoping.
- Broug is a level `4` human rogue in Elwynn/Northshire. Latest snapshot showed nearby Kobold Vermin `6` and Kobold Worker `257`.
- Scoped watcher is running for Broug as pid `8876` with `--arm-from-end` and `--mark-existing-evaluated-on-arm`.
- User redirected first feature work to combat proficiency: copy Jecia's shield pipeline and grant Broug two-handed swords, two-handed axes, polearms, Mail, and level-40 Plate.
- Repo changes extend `python -m wm.spells.shield_proficiency` and SQL `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_30_00_wm_spell_two_hand_weapon_proficiency.sql`.
- BridgeLab SQL was reapplied with Rogue-compatible DBC masks, client `patch-z.mpq` was rebuilt/installed with `SkillRaceClassInfo.dbc` and `SkillLineAbility.dbc` combat rows, worldserver restarted to pid `10360`, `WmSpells.PlayerGuidAllowList = "5405,5406"`, and `python -m wm.spells.shield_proficiency --player-guid 5405 --mode apply --summary --player-level-override 4` returned `ok=true`.
- Broug DB rows now include skills `55`, `118`, `172`, `229`, `413`, `414`, and `433`, and spells `107`, `197`, `200`, `202`, `674`, `8737`, `9077`, and `9116`. Weapon skill caps are level-scaled and preserved on reapply: `55=18/20`, `172=1/20`, `229=1/20`. Plate skill `293` and spell `750` are absent because Broug is below level `40`; the active `wm_spell_grant` metadata records Plate as locked until level `40`.
- Fix applied after the user screenshot showed no two-handed rows: `src/wm/spells/shield_proficiency.py` now uses `level * 5` weapon caps, preserves existing skill progress on reapply, and `native_modules/mod-wm-spells/src/wm_spell_runtime.cpp` materializes only active explicit `combat_proficiency` grants in-memory by learning missing proficiency passives and setting scoped skill values. Do not revive broad class/default/playerbot grant paths.
- Focused Broug/DBC tests passed: `38 passed`. Full tests passed: `python -m pytest -q` -> `542 passed`. Client `patch-z.mpq` was rebuilt/installed, server `Spell.dbc` was staged for `946098`, `946603`, and `946800`; latest no-aura restage refreshed `946603`, latest Skirmisher movement restage refreshed `946098`, BridgeLab worldserver restarted to pid `18080`, and native ping request `601` returned `pong`.
- Broug in-game proof is accepted as working for the current feature slice. Combat proficiencies, linked quests, and custom abilities should be treated as proven for Broug unless the user reports a specific regression. Plate still remains intentionally locked until level `40`.
- Broug guard progression is `WORKING` for the current scope. Fresh base shell `946800` (`Impossible Guard`) is reserved and learned by Broug. Old visible shell `946801` (`broug_mobile_marksman_v1`) is `BROKEN`/retired after live proof that the passive moving pulse felt strange; never reuse it. Failed shell `946604` (`broug_skirmisher_mark_v2`) is also `BROKEN`/retired because it presented as a self-buff/toggle instead of a Throw/Shoot-like active attack; never reuse it. Fresh targeted active replacement `946098` (`broug_skirmisher_shot_v1`) fires one Broug-scoped native ranged/thrown attack at the selected hostile target, using equipped ranged weapon speed and normal ranged auto-attack scaling while moving, without globally patching stock Throw or Auto Shot. Latest `946098` DBC row removes the inherited Throw ranged-slot flag and clears movement interrupt fields (`attrs=0x410010`, interrupt/aura/channel interrupt `0`). Broug DB proof has only `946098` and `946800` active in `character_spell`; `946801` and `946604` are revoked with `replaced_by=946098`. Fresh reward shells `946603` (`Deflect`) and `946802` (`Riposte Instinct`) plus linked quests `910180` -> `910181` and hidden credit entries `920104` / `920105` are implemented through SQL `2026_04_30_02_wm_spell_broug_deflect_rewards.sql` and native quest-complete hooks. User reported quests done and abilities working on 2026-05-01.
- Latest Deflect correction: `946603` now disables Impossible Guard during the iframe, clears queued forced parries on activation, blocks caught damage immediately, and delays the stun/reflected hit until iframe end while playing a melee attack animation/sound. Icons changed to Retaliation `278` for Deflect and Overpower `26` for Impossible Guard, verified in client payload, extracted MPQ, and server `Spell.dbc`. The latest `946603` DBC row has zero dispel, duration, effect, aura, base-point, and misc payload, so casting Deflect should not create a visible buff; stale saved `character_aura(guid=5405, spell=946603)` was deleted. Gameplay is accepted for the current Broug scope.
- Current Deflect rework state: fresh visible shells `946200` (`Vulnerable`) and `946201` (`Deflected`) are deployed, both icon `558`. Existing active `946603` remains the Deflect button and stays aura-free. Runtime is a rooted `650ms` guard (`100ms` pre, `450ms` parry animation, `100ms` post), hostile melee/direct spell/direct AoE/periodic/aura blocking, and one Vulnerable stack per blocked attacker/caster. Fresh stance shell `946605` (`Counterstrike Stance`) is now a real stance aura (`SPELL_AURA_MOD_SHAPESHIFT`, form `13`, `StanceBarOrder=1`), not a DB-backed pseudo-toggle; Deflect auto-counterattacks only if Broug has the live `946605` aura when the window resolves. Root cause of the old timed-buff display was the DBC materializer writing `duration_index` to field `37` (`MaxLevel`) instead of real field `40`; this is fixed. Focused tests passed (`43`), full tests passed (`551`), SQL correction applied and verified `counterattack_requires_aura=true`, server and extracted client DBC staged `946605` with stance category `47`, permanent `duration_index=21`, Rogue family `8`, `damage_class=0`, `prevention_type=0`, and `stance_bar_order=1`; client `patch-z.mpq` installed, stale saved timed `character_aura(guid=5405, spell=946605)` was deleted, native build passed with one existing duplicate-loader warning and `0` errors, BridgeLab worldserver pid `35284`. User live acceptance on 2026-05-01 makes this `WORKING` for Broug's current scope.
- Latest Deflected stack/stun correction: `946200` and `946201` now have DBC `StackAmount=255` so stack counts can render visibly; server `Spell.dbc`, client payload, and extracted MPQ verify `duration=3/36`, `stack=255`, `effect=6`, `aura=4`, icon `558`. Native now force-creates the harmless visible marker aura if normal `AddAura` is blocked by immunity, hooks `UNITHOOK_ON_AURA_REMOVE`, releases native forced stun when `Deflected` is removed/expires, and restarts creature attack against its current victim after release. Focused tests passed (`43`), full suite passed (`551`), native build passed with one existing duplicate-loader warning and `0` errors, BridgeLab worldserver pid `24388`, and client `patch-z.mpq` installed after the client closed. User live proof accepted the result.
- Latest Deflected aura-owned stun correction: user live proof confirmed `Deflected` stack numbers were visible, but mobs could sometimes stay half-disabled. Native no longer uses a separate forced-stun expiry timer; `946201` aura presence is now the stun contract. While present, runtime enforces `UNIT_STATE_STUNNED`, cast stop, and movement stop; when absent, runtime releases native stun and restarts creature combat. Focused Broug/shell tests passed (`13`), full suite passed (`551`), native build passed with one existing duplicate-loader warning and `0` errors, BridgeLab worldserver pid `12612`. User then reported quests done and abilities working, so this correction is accepted as `WORKING` for the current scope. No client patch was needed for this server-only correction.

Restorer/Destroyer retests are lower priority now unless the user asks for them again. If they do:

During the retest, have Jecia run `wm echo status` after enabling seek mode and while enemies are active. Expected: `dps_spell=1`, first Restorer `range1` at distances up to roughly `90yd`, fewer parking/range failures, and visibly faster Echo Destroyer engagement due to `1.75x` Alpha movement.

If they still stand still or `dps_spell=0`, do not blindly tweak speed/range again. Check whether server/client DBC and behavior config are loaded for `946099`.

Confirmed structural issue from 2026-04-29 live status:

- Live status showed `restorer_targeted=10`, `no_los=0`, `dps_spell=1`, `out_range=10`, `ready=0`, and `cooldown=10`.
- Target selection, LOS, spell data, and cast-state were not the blocker.
- AzerothCore chase movement stops itself when `owner->GetVictim() != chaseTarget`.
- Restorers were only setting target GUID/combat flags, so passive caster `MoveChase` immediately lost its target and stopped.
- Current fix establishes a non-melee victim with `Attack(victim, false)` and avoids clearing it before `MoveChase`.
- New range retune deliberately does not mutate stock `8092`; `946099` owns the custom Restorer DPS range.

Inspect these symbols first:

- `MoveBoneboundPriestEchoToSafePosition`
- `SelectBoneboundEchoSeekTarget`
- `SelectBoneboundPriestEnemyTarget`
- `TryStartBoneboundPriestDpsCast`
- `UpdateBoneboundPriestDpsCast`
- `CommandBoneboundPriestEchoSeek`
- `ApplyBoneboundAlphaEchoRuntime`

Main file:

- `native_modules/mod-wm-spells/src/wm_spell_runtime.cpp`

Tests:

- `tests/test_bonebound_runtime.py`

## Debug Plan If Restorers Still Fail

Answer these in order:

1. Does each Restorer have an enemy target GUID?
2. Is `TryStartBoneboundPriestDpsCast` called?
3. Does `wm echo status` show `dps_spell=1` and first Restorer `range1` at distances where old `8092` would be out of range?
4. Does `UpdateBoneboundPriestDpsCast` fire damage after cast time?
5. Is `MoveIdle()` cancelling/interrupting the visible cast loop?
6. Is `AttackStop()` or passive react state suppressing a core spellcast path?

If needed, add temporary scoped runtime logging for player `5406` only. Remove or gate it before finalizing.

Do not add more random tuning until the failed condition is known.

## Acceptance Criteria

Restorers are `WORKING` only when live proves:

- In seek mode, Restorers acquire a target and keep it for roughly 30s while alive.
- They move into practical range instead of parking far behind Jecia.
- They visibly cast their DPS spell or support spells.
- They do not jitter.
- They do not stand idle while valid enemies are fighting Alpha/Echoes/Jecia.
- They catch up better than before due to `1.5x` speed.
- They do not steal XP/loot credit from Jecia's pet-kill flow.

If any of those are not observed, status stays `PARTIAL`.

## Build And Verify

Use these commands:

```powershell
git status --short --branch

$env:PYTHONPATH='src'
$env:WM_WORLD_DB_PORT='33307'
$env:WM_CHAR_DB_PORT='33307'
$env:WM_CHAR_DB_HOST='127.0.0.1'
$env:WM_WORLD_DB_HOST='127.0.0.1'

python -m pytest -q tests/test_bonebound_runtime.py
python -m pytest -q

.\scripts\bridge_lab\Build-BridgeLabIncremental.ps1 -WorkspaceRoot D:\WOW\WM_BridgeLab -Target worldserver -NoStageRuntime
.\scripts\bridge_lab\Stage-BridgeLabServerSpellDbc.ps1 -SeedProfile castable -SpellId 946099
.\scripts\bridge_lab\Deploy-BridgeLabWorldServer.ps1 -WorkspaceRoot D:\WOW\WM_BridgeLab -WmSpellsPlayerGuidAllowList "5406"
```

Native ping:

```powershell
python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind debug_ping --payload-json '{}' --idempotency-key "manual:debug_ping:$(Get-Date -Format yyyyMMddHHmmss)" --wait --summary
```

Last known live runtime:

- `authserver` pid `31316`
- `worldserver` pid `12612`
- Broug quest/ability slice is accepted by user as working after the latest Deflected stun sync fix; no additional Broug client MPQ install is needed for that server-only correction
- `mod-aoe-loot` is installed in BridgeLab and pinned in `bootstrap/sources.lock.json` at commit `2ddf6ff75bdbfee3c81f2c149a07126f1d0bf200`: cloned under `D:\WOW\WM_BridgeLab\src\modules\mod-aoe-loot`, junctioned into `src\azerothcore\modules`, CMake-reconfigured into the static module loader, rebuilt with `0 Warning(s), 0 Error(s)`, config `mod_aoe_loot.conf` installed/enabled with range `55`, and 8 `module_string` rows applied. Gameplay proof of `.aoeloot on/off` and actual nearby corpse loot merge is pending.

## Recent Landmines

Quest publishing:

- User is furious about reused IDs, correctly.
- Never reuse visible failed quest/item/spell IDs.
- If a quest reward is wrong or absent, do not keep mutating the same visible ID.
- Use fresh reserved IDs and retire old rows cleanly.

Playerbot/broadcast:

- Keep WM broadcast/events scoped to active WM player.
- Do not globally spam or globally disable playerbot behavior unless explicitly requested.

Restorer work:

- After three failed Restorer attempts, stop and write root cause.
- Current Restorer attempts already include movement and range tuning. If still broken, treat it as a structural cast/AI problem.

## Roadmap After Restorers

Restorers basic seek/cast positioning was live-proven by the user, then the chat moved back to roadmap work. The current x3 Restorer range, Destroyer speed, Lens Focus, and Lens Command slices remain `PARTIAL` until live retest.

Current release-pipeline feature work:

- `python -m wm.content.release <spec> --plan --summary` renders release gates and commands.
- `python -m wm.content.release <spec> --packet --summary` emits validation, plan, compiled artifacts, and live-proof checklist in one packet.
- `python -m wm.content.release <spec> --write-packet-dir <dir> --summary` writes `release_packet.json` and compiled artifact files, refusing overwrite unless `--force` is used.
- `python -m wm.content.release --audit-dir control/examples/content_releases --summary` validates every release template and currently reports 18/18 valid specs.
- `python -m wm.candidates.release_pack --context-pack-json <context-pack.json> --summary` builds a deterministic `wm.release_candidate_pack.v1` from context-pack generation input. It emits validated repeatable-bounty, story-arc, shell-ability, and native-scene specs with `PACKET_READY`, and blocks managed item power until a fresh item entry plus base item are supplied. Use `--reserved-item-entry <fresh-item-entry> --base-item-entry <known-good-base-item-entry>` to make the managed item-power lane packet-ready, `--write-candidates-dir <dir>` to write the pack plus ready `*.release.json` files, `--write-packets` to write each candidate's release packet/artifacts in `<candidate>.packet/`, and `--write-test-manifest` to write `release_test_manifest.json` for the next BridgeLab proof pass.
- Story arc specs can emit `wm.character_journey.seed.v1` and a non-mutating branch-lock contract for first-completed-choice forks.
- Scene specs can emit `control.scene.v1`; `--scene-action-roster` currently reports 13 release-ready scene verbs and 5 blocked future gameobject/weather verbs.
- `--ability-roster` currently reports 16 ready/variant ability lanes and 5 future-blocked lanes.

Roadmap direction:

- WM is a per-character World Master progression engine.
- Prioritize "wild stuff":
  - character arcs
  - exclusive rewards
  - item-granted abilities
  - shell-bank visible powers
  - companion behaviors
  - live scenes/director features
  - random enchant/rune systems
  - conversation steering
- Platform work is a gate, not the product.

Do not do broad coordinator splits or abstract refactors before the current companion runtime is stable.

## Dirty Worktree Areas

Expect dirty changes in:

- docs/roadmap/handoff files
- spell shell bank
- custom ID registry and reserved ranges
- random enchant vellums
- native bridge random enchant code
- native WM spell runtime
- quest/item publishing and rollback
- arc/reward factory files
- BridgeLab launcher scripts
- tests

Do not assume all changes belong to one feature. Group by subsystem before staging or committing.
