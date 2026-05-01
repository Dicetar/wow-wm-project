Status: PARTIAL
Last verified: 2026-05-01
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
6. use the debug/native lane for behavior tuning until the client shell is installed and validated in-game

Current supported iteration lane:

- `mod-wm-spells` plus `wm_spell_debug_request`
- `python -m wm.content.workbench invoke-shell-behavior`

Current fast release lane for the Bonebound Alpha behavior:

- `python -m wm.spells.summon_release --player-guid 5406 --summary`
- `.\summon-bridge-lab-bonebound-alpha.bat -PlayerGuid 5406`
- `.\summon-bridge-lab-bonebound-twins.bat -PlayerGuid 5406`

The `twins` wrapper name is now a compatibility alias only. Shell `940001` runs single-Alpha behavior `summon_bonebound_alpha_v3`, not the retired Omega companion path.

The release lane assumes the shell, behavior row, scoped player, lab config, and worldserver are already proven. It skips shell-bank lookup, player lookup, schema preflight, and default wait/poll verification. Use the debug lane first when changing schema, behavior config, player scope, or native code.

Visible stock-carrier testing is not supported.

## Working now

### Shell-bank and patch workspace

- shell-bank contract exists
- client patch workspace exists
- generic V2 bank uses ten 100-slot cast-shape families under `946000-946999`; the former reserve gaps are now allocated to missing cast shapes
- named shell entries exist for `940000`, `940001`, `944000`, `945000`, `946099`, `946600`, `946601`, and `946602`
- `WORKING`: server-side Spell.dbc materialization now exists for named compatibility shells through `python -m wm.spells.server_dbc materialize` and `scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1`; the current BridgeLab proof stages `940000`, `940001`, `944000`, `945000`, and `946600` into `D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc`
- `WORKING`: named shell `940001` is now proven as a server-known learnable identity on BridgeLab after the DBC stage: `grant-shell` writes `character_spell(5406, 940001)` plus active `wm_spell_grant`, and `ungrant-shell` removes the row and revokes the grant after `.saveall` and retry-backed verification
- `WORKING`: client patch packaging is repo-owned through `python -m wm.spells.client_patch`. On 2026-04-17, Codex downloaded official Ladik MPQ Editor into `.wm-bootstrap\tools\mpqeditor`, built and verified `.wm-bootstrap\state\client-patches\wm_spell_shell_bank\patch-z.mpq`, and the builder now emits `DBFilesClient\Spell.dbc`, `DBFilesClient\SkillLineAbility.dbc`, and `DBFilesClient\SkillRaceClassInfo.dbc`.
- `WORKING`: shell `946602` (`WM Watcher Beacon`) is the current watcher discovery marker. On 2026-04-30, BridgeLab worldserver pid `30756` loaded the staged server row, client `patch-z.mpq` was rebuilt/installed after the client closed, server and extracted client DBC rows both verified `dispel=0`, `duration=0`, dummy aura, no visuals, and icon `135`, native ping request `581` returned `pong`, and live marker event `39872` found/scoped Broug `5405` during a short wildcard observation window before wildcard was cleared.
- `WORKING`: shell presentation metadata is explicit for `940001`: Animate Dead icon `221`, 3 second cast time through `SpellCastTimes` index `14`, 180 mana cost, Summon Voidwalker visual `4054`, and a Warlock/Demonology spellbook mapping cloned from Summon Voidwalker skill-line ability row `697 -> 354`.
- `WORKING`: server DBC materialization now has separate profiles. `learnable` keeps the neutral grant/revoke proof seed. `castable` uses the client cast-shape seed for visible-shell tests; repo tests now verify `940001` carries visual field `SpellVisualID_2 = 4054`, and the previous 2026-04-17 BridgeLab stage verified the server row has effect `(28,0,0)`, target `(32,0,0)`, range `1`, cast time `14`, icon `221`, and mana cost `180`.
- `WORKING`: the refreshed client MPQ package is installed at `D:\WOW\world of warcraft 3.3.5a hd\Data\patch-z.mpq`, and BridgeLab worldserver was restarted on pid `8580` so the staged server DBC is loaded. In-game proof on 2026-04-17 showed `940001` in the Warlock/Demonology spellbook with the intended icon, 180 mana cost, and 3 second cast time.
- `PARTIAL`: caster animation/visual polish is still open. The shell contract now pins `940001` to Summon Voidwalker visual `4054` instead of Raise Ghoul visual `749`, but the refreshed client/server DBC artifacts still need to be rebuilt, restaged, and proven in-game.

### Native spell runtime

- `mod-wm-spells` builds in `WM_BridgeLab`
- `WORKING` repo/build/deploy on 2026-04-29 for Restorer movement/cast ownership, Destroyer speed retune, and Lens Command: Echo seek target selection uses the active WM player as the search center, Restorers can leave the close support ring in seek mode, and passive-caster chase now establishes a non-melee victim with `Attack(victim, false)` before `MoveChase`. User live proof confirmed Restorers no longer stand stuck after this movement fix. The current x3 DPS range, Destroyer speed, and Lens Command retunes are `PARTIAL` until live retest: Restorer filler DPS now uses fresh WM-owned spell `946099`, cloned from stock Mind Blast `8092` with the same cast/effect/visual/icon fields but `RangeIndex=157` (`90yd`, 3x stock `30yd`); stock `8092` remains default `RangeIndex=4`; Echo Destroyers now scale movement from Alpha at `1.75x` through `alpha_echo_movement_speed_multiplier`; Lens-marked targets are preferred in Echo seek mode; Restorers remain `1.5x`. Runtime name changes force object-visibility refresh so active Echoes can update to `Echo Destroyer` / `Echo Restorer`. Bonebound Echo Stasis adds active Echo Destroyer/Echo Restorer counts into the saved pool instead of replacing it, restores only when no Echoes are active, and preserves any over-cap remainder in the pool. Echo follow positioning uses deterministic formation rings with a 1.6 yard minimum spacing target. BridgeLab worldserver is running pid `30124`, and native ping request `575` returned `pong`.
- shell, behavior, grant, and debug tables exist
- debug invoke resolves shell-bound config from `wm_spell_behavior`
- `WORKING`: Bonebound Alpha debug/native lane uses WM shell `940001`, not stock `697` or `49126`
- `WORKING`: lab DB proof on 2026-04-15 retired `49126`, disabled its behavior row, removed stock WM spell-script bindings, and left only `940001 -> spell_wm_shell_dispatch`
- `WORKING`: repo/runtime separation now moves Bonebound off stock creature truth. Alpha uses WM creature template `920100`, stock Voidwalker remains `1860`, and `IsBoneboundPet()` no longer falls back to stock entry/display heuristics.
- `PARTIAL`: stock Summon Voidwalker separation is deployed but not yet re-proven in-game after the structural fix. BridgeLab DB proof on 2026-04-17 now shows `character_spell(5406,697)` and `character_spell(5406,940001)` present, `49126` absent, Jecia's saved Alpha row migrated to `character_pet.entry=920100`, `wm_spell_behavior(940001)` repointed to `creature_entry=920100`, and only `940001 -> spell_wm_shell_dispatch` in `spell_script_names`. The prior cleanup-only state was still broken because Alpha shared stock creature entry `1860`.
- `WORKING`: historical lab invoke request `7` for player `5406` executed the old twin behavior and persisted `Bonebound Alpha` with `CreatedBySpell=940001`
- `WORKING`: Bonebound Alpha behavior config transfers the summoner's total intellect to all Alpha stats and shadow spell power to Alpha attack power; BridgeLab live proof passed after the 2026-04-24 `WmSpells.PlayerGuidAllowList` fix
- `WORKING`: Bonebound visible bleed is BridgeLab-proven after the 2026-04-25 attack-power retune: shell `940001` maps to `summon_bonebound_alpha_v3`, `spawn_omega=false`, Alpha config keeps Gorehowl visual item `28773`, and Alpha/Echo melee hooks apply visible client aura spell `772` (`Rend`) as the target status/duration marker while WM owns the physical tick damage. Bleed state is keyed by caster GUID plus target GUID, so each Echo maintains an independent DoT stack. Tick damage scales primarily from the attacker's melee attack power with `bleed_damage_per_attack_power_pct=20`; shadow spell power still contributes indirectly through the owner-shadow-power-to-attack-power transfer. Legacy `shadow_dot_*` config keys still parse, but current drafts and SQL use `bleed_*`.
- `WORKING`: Alpha echoes use WM creature template `920101` (`Echo Destroyer`) instead of spawning from the Voidwalker template; runtime stat recalculation runs before Alpha health/power/damage is copied, Echo follow slots are assigned from deterministic formation rings with a 1.6 yard spacing target, and the active Echo cap is configured to `40`; native bridge event `27941` recorded an owned-unit kill from object entry `920101`
- `PARTIAL`: rare support Echo variant is repo-tested, SQL-applied, native-built, and deployed to BridgeLab worldserver pid `30124`: Alpha melee has a separate `5%` support-role proc chance that spawns creature `920103` (`Echo Restorer`) with Skeletal Magelord display `11397` from stock NPC `15121` and one random configured level-appropriate rare/epic staff model, copies Alpha health/stats through the same owner-intellect stat transfer path, matches Echo Destroyer template walk/run speed and runtime movement rates after stat recalculation, heals the lowest hurt owner/Alpha/Echo/group target with visible Flash Heal `2061`, applies visible Renew `139`, applies visible Power Word: Shield `17` only to support targets under active attack/cast threat, and never uses the melee attack path. Restorers use a separate active cap of `10`, repeated Echo Destroyer spawns without a successful Restorer force a support spawn attempt after `6` Destroyer spawns, and spell output adds owner shadow spell power through `priest_echo_spell_power_to_healing_pct=35`, `priest_echo_spell_power_to_shield_pct=30`, and `priest_echo_spell_power_to_damage_pct=45`. User live proof on 2026-04-29 confirmed the movement/casting ownership fix works. Filler DPS now uses WM spell `946099` (`Echo Mind Blast`) as both effect and damage spell, with `priest_echo_dps_cast_time_ms=1500`, `priest_echo_dps_damage_pct=19`, `priest_echo_dps_cooldown_ms=2500`, and `priest_echo_dps_max_range=100.0`; the staged DBC row clones stock Mind Blast `8092` but changes range to `90yd`, while stock `8092` remains `30yd`. The refreshed client patch containing the named `946099` row was installed after the client closed, and extracted payload verification found `range=157`, `visual2=3057`, `icon=95`, and name `Echo Mind Blast`. In seek mode, Restorers keep sticky targets for roughly 30 seconds, run at `1.5x` Alpha speed, use `MoveChase` rather than enemy `MoveFollow`, and prefer the Lens wearer's own visible mark when one is active. Single disease/curse dispel is available through visible spells `528`/`475`; Mass Dispel `32375` is gated by severity/affected-target thresholds and a `180000 ms` cooldown. Live in-game proof of the new x3-range clone and Lens Command remains pending.
- `PARTIAL`: Alpha Echo attack/reacquire, Destroyer speed, Lens Command, and seek-mode control are repo-tested, native-built, and deployed to BridgeLab worldserver pid `30124`: maintenance now explicitly adds threat, sets combat on Echo and target, calls `AttackStart`, falls back to direct `Attack`, and forces `MoveChase` when Echo Destroyers have Alpha's victim but follow motion has stuck. Echo Destroyers now scale movement from Alpha at `1.75x`, while Restorers remain `1.5x`, so melee should close and engage faster than before. Player-facing chat control now exists for the active WM player: type `wm echo seek` to make Echo Destroyers attack and ranged Echo Restorers select the nearest eligible hostile in range when Alpha has no current victim, `wm echo seek 60` to enable seek at a specific radius, `wm echo range 60` to retune seek radius without changing mode, `wm echo follow` to return them to close guard behavior, and `wm echo teleport` / `wm echo tp` / `wm echo recall` to teleport all active Echoes back to the player. Runtime seek radius is per-player, scoped to the active WM player, and clamped to `5-100` yards. Lens Command makes Echoes prefer the Lens wearer's own visible mark (`770`) before ordinary nearest-target selection, so the item mark becomes a companion focus signal. `wm echo status` / `wm echo state` reports seek mode, radius, tracked/live Echo counts, Restorer target/ready/casting/pending/cooldown/range/LOS/marked counts, DPS spell-info availability, and first-Restorer target/range/mark/cast details. In-game proof of the new `946099` x3-range cast should confirm `dps_spell=1` and range-ready casts at distances above stock Mind Blast range; in-game proof of the Destroyer retune and Lens Command should confirm faster melee engagement and marked-target preference without jitter.
- `PARTIAL`: Bonebound Echo Stasis shell `946600` is repo-implemented for count-only echo storage/restore. It is a 5 second self-cast shell with Soul Shard reagent presentation, bound to `bonebound_echo_stasis_v1`; casting with active Echoes adds Destroyer/Restorer counts into the existing `wm_bonebound_echo_stasis` pool and despawns them, while casting with no active Echoes, stored counts, and an active Bonebound Alpha restores role counts with full HP/mana and max timers. Restore respects active caps and keeps any remaining stored counts for a later no-active restore. BridgeLab SQL/DBC/build/grant/live proof is still pending.
- `PARTIAL`: Lana'thel stance shell `946601` is repo-implemented and BridgeLab-deployed as `lanathel_blood_queen_stance_v1`. It toggles a persisted native stance for the active WM player, uses Blood-Queen Lana'thel display `31165` at reduced scale, dismounts stock mounts, survives combat because no dispellable aura owns the state, applies land speed from Riding skill everywhere the shell can cast, and enables flight speed only when the player has expert+ Riding and the current area can fly. On 2026-04-27, SQL applied, server Spell.dbc was staged with named castable shells, `patch-z.mpq` was rebuilt/installed with `946601`, BridgeLab worldserver was rebuilt/restarted to pid `36276`, and `character_spell(5406,946601)` plus `wm_spell_grant` were verified via SOAP fallback. Live in-game cast/form/flight proof is still pending.
- `PARTIAL`: Alpha echo mount/dismount restore is implemented, repo/static-tested, native-built, and deployed to BridgeLab worldserver pid `31208`. The runtime now preserves missing Echo state while the owner pet is temporarily unsummoned by mounting, prevents player maintenance from erasing that state while the main pet is absent, then respawns the Echo from the saved template/follow slot with its remaining lifetime after the Bonebound pet returns. Live in-game BridgeLab proof is still pending.
- `WORKING`: Bonebound Alpha release submitter exists at `python -m wm.spells.summon_release`; it now defaults to behavior `summon_bonebound_alpha_v3` and shell `940001`
- `WORKING`: live post-restart Alpha v3 smoke was accepted on 2026-04-16 after request `11` completed for online player `5406`; repo evidence proves the active pet row is `Bonebound Alpha` on shell `940001`, and user validation reported the bleed/echo behavior acceptable
- `PARTIAL`: Demonology passive compatibility is not globally proven. Alpha now uses WM creature entry `920100`, cloned from the Voidwalker template so family/type truth stays demon-like, but anything hardcoded to stock spell `697`, stock creature entry `1860`, or stock CreatedBySpell semantics is unverified because Alpha is created by WM shell `940001`.
- `BROKEN`: Bonebound Omega TempSummon parity is retired for the release lane. Live evidence showed Alpha melee around `120`, Omega melee around `9`, and Omega mana around `20`; copying Alpha-visible fields onto a Creature/TempSummon did not affect the actual combat path reliably.
- `WORKING`: persistent combat proficiency repo path exists through DBC override SQL plus explicit GUID grant:
  - `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_15_02_wm_spell_shield_proficiency.sql` seeds high-ID `skillraceclassinfo_dbc` and `skilllineability_dbc` rows for Shield skill `433`
  - `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_15_03_wm_spell_leather_dual_wield_proficiency.sql` seeds high-ID `skillraceclassinfo_dbc` and `skilllineability_dbc` rows for Leather skill `414`
  - `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_15_04_wm_spell_dual_wield_skill_validity.sql` seeds high-ID `skillraceclassinfo_dbc` for Dual Wield skill `118`, which AzerothCore validates before keeping spell `674`
  - `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_30_00_wm_spell_two_hand_weapon_proficiency.sql` seeds high-ID DBC override rows for Mail skill `413` / spell `8737`, Two-Handed Swords `55` / spell `202`, Two-Handed Axes `172` / spell `197`, Polearms `229` / spell `200`, and Plate skill `293` / spell `750` with Plate DBC `MinLevel=40`
  - `python -m wm.spells.shield_proficiency --player-guid <guid> --mode apply --summary` upserts only explicit character rows and a `wm_spell_grant` marker for shell `944000`; for characters below level `40`, it does not write Plate skill/spell rows
  - `mod-wm-spells` materializes explicit active `combat_proficiency` grants for allowlisted players only: it learns the stock proficiency passives in-memory if missing, sets the matching skill rows with level-scaled weapon caps, and still materializes AzerothCore's volatile Dual Wield flag from spell `674`
  - bridge-lab live proof on 2026-04-15 confirmed player `5406` can equip Shield, Leather, and a one-handed sword in offhand; Dual Wield is also visible in the spellbook
  - BridgeLab DB/client proof on 2026-04-30 applied the Mail/Plate/two-handed weapon SQL with Rogue-compatible `SkillRaceClassInfo` masks, rebuilt/installed `patch-z.mpq` with matching client `SkillRaceClassInfo.dbc` plus `SkillLineAbility.dbc` rows, restarted worldserver to pid `10360` with `WmSpells.PlayerGuidAllowList = "5405,5406"`, and granted Broug `5405` Shield, Leather, Mail, Dual Wield, Two-Handed Swords, Two-Handed Axes, and Polearms. Broug is level `4`, so weapon caps are `20`; Plate remains locked in metadata and absent from `character_skills` / `character_spell` until level `40`. Native ping request `589` returned `pong`, and Broug watcher restarted as pid `8876`.
  - focused repo tests verify the SQL does not insert or update `playercreateinfo_skills`, `playercreateinfo_spell_custom`, or `mod_learnspells`
- `WORKING`: `passive_intellect_block_v1` is rating-only; it reads an active `wm_spell_grant` and applies block rating from intellect plus spell power, but it no longer calls `SetSkill`, `SetCanBlock`, or overrides shield equip class checks. BridgeLab live proof passed after the 2026-04-24 `WmSpells.PlayerGuidAllowList` fix.
- `WORKING`: Broug guard progression is repo/build/deploy/gameplay `WORKING` for player `5405` in the current scope: shell `946800` (`broug_universal_parry_v1`) rolls a grant-gated custom parry against hostile melee, direct spell, and periodic-effect damage and increments `wm_broug_guard_counter` key `universal_parry`; old visible shell `946801` (`broug_mobile_marksman_v1`) is retired `BROKEN`, failed self-aura toggle shell `946604` (`broug_skirmisher_mark_v2`) is retired `BROKEN`, and fresh targeted active shell `946098` (`broug_skirmisher_shot_v1`) fires one native ranged/thrown attack at a hostile target using equipped ranged weapon speed and normal ranged auto-attack scaling while moving without globally changing stock ranged movement checks. Latest `946098` DBC correction removes the inherited Throw ranged-slot flag and clears movement interrupt fields (`attrs=0x410010`, interrupt/aura/channel interrupt `0`). Reward shell `946603` (`broug_deflect_v1`) is an active 5-energy/no-GCD server-side Deflect window with dispatch-only/no-aura DBC payload, and reward shell `946802` (`broug_auto_retaliation_v1`) is a passive Riposte strike after counted parries. Latest correction on 2026-04-30 rebuilt/installed client `patch-z.mpq`, staged server `Spell.dbc` for `946098`, restarted BridgeLab worldserver to pid `18080`, and native ping request `601` returned `pong`. User live acceptance on 2026-05-01 reported Broug quests done and abilities working.
- `WORKING`: latest Broug Deflect correction is accepted for the current Broug scope: Deflect now disables Impossible Guard during the iframe, clears any queued forced parry on activation, prevents caught damage immediately, then plays a melee attack animation/sound and applies stun/reflected damage at iframe end. Client payload, extracted MPQ, and server `Spell.dbc` verify `946603` Retaliation icon `278`, `946800` Overpower icon `26`, and zero dispel/duration/effect/aura payload for `946603`, so Deflect should no longer create a visible buff; stale saved `character_aura(guid=5405, spell=946603)` was deleted; focused Broug/DBC tests passed (`38 passed`), full tests passed (`542 passed`), BridgeLab worldserver pid `18080`, and Broug native ping request `601` returned `pong`.
- `WORKING`: Broug Deflect rework and Counterstrike Stance correction on 2026-05-01 adds fresh visible shells `946200` (`Vulnerable`) and `946201` (`Deflected`) with icon `558`, plus fresh stance shell `946605` (`Counterstrike Stance`). Existing active Deflect `946603` stays aura-free and uses the rooted `650ms` guard (`100ms` pre, `450ms` parry animation, `100ms` post). Counterstrike Stance now has a real `SPELL_AURA_MOD_SHAPESHIFT` aura row with form `13` and `StanceBarOrder=1`; native runtime gates Deflect's automatic counterattack on `player->HasAura(946605)` and no longer uses the old DB toggle as gameplay state. Repo tests passed (`43` focused, `551` full), SQL correction applied and verified `counterattack_requires_aura=true`, server DBC staged for `946605`, native build passed with one existing duplicate-loader warning and `0` errors, and user live acceptance closed the current Broug gameplay proof.

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

No longer blocked on MPQ packaging. The repo can now build the client shell-bank patch with `Spell.dbc`, `SkillLineAbility.dbc`, and `SkillRaceClassInfo.dbc`, and BridgeLab has a matching cast-shape server row for `940001`.

Still open:

- action-bar and tooltip proof beyond the spellbook screenshot
- visible-shell cast produces Bonebound Alpha through `spell_wm_shell_dispatch`
- final cast/recast/dismiss/relog lifecycle proof on the visible shell path
- one generic shell from each `946000-946999` V2 family verified in BridgeLab

### Bonebound Alpha v3

Bonebound Alpha v3 is the supported current summon iteration path in `mod-wm-spells`.

Use it as lab/debug work only until the shell-bank patch is installed and validated.

Current classification:

- `WORKING`: repo tests, native build, bridge-lab SQL binding, and worldserver restart for shell `940001`
- `WORKING`: single Alpha true-pet summon model; `spawn_omega=false`
- `WORKING`: Gorehowl visual weapon config for Alpha through `virtual_item_1=28773`; in-game display was confirmed after BridgeLab allowed `mod-wm-spells` for player `5406`
- `WORKING`: native Alpha/Echo bleed implementation is deployed to BridgeLab worldserver pid `32248` with a 6 second cooldown per caster, 4 second duration, 1 second tick, attack-power-primary scaling (`bleed_damage_per_attack_power_pct=20`, level/intellect/shadow direct coefficients zeroed), visible target aura `772`, and melee-hook-only application; user live proof on 2026-04-25 confirmed the retuned damage path
- `WORKING`: Alpha passive echo implementation exists with 7.5% melee proc chance, maximum 40 active echoes, WM creature template `920101`, randomized follow slots around the player, and echo lifetime equal to summoner total intellect in seconds
- `PARTIAL`: Echo Restorer support variant is deployed as creature template `920103` with `priest_echo_proc_chance_pct=5.0`, `priest_echo_max_active=10`, `priest_echo_pity_after_warrior_spawns=6`, display `11397`, configured random staff pool, randomized close support follow distance around `1.8`, runtime movement-rate normalization at `1.5x` Alpha speed, `946099` / `Echo Mind Blast` 90-yard filler range, single disease/curse dispels, thresholded Mass Dispel, and owner shadow-spellpower scaling; it should be proven by seeing `Echo Restorer` spawn and cast visible heal/shield/renew/Mind Blast damage/dispels without entering melee, stacking in one spot, or lagging behind Destroyers.
- `PARTIAL`: Echo target-stare recovery plus player-facing seek/follow/range/teleport control are rebuilt/deployed on BridgeLab pid `30124`; Lens Command is build/deploy proven and still needs live proof. Live proof should show Echo Destroyers reacquire Alpha's current victim after follow/chase motion gets stale, prefer the Lens wearer's marked target in seek mode, move at `1.75x` Alpha speed, and engage faster than before. `wm echo seek [yards]` should make Destroyers attack nearby eligible hostiles and make Restorers target/cast at nearby eligible hostiles when Alpha has no victim, `wm echo range [yards]` should retune the seek radius within `5-100`, `wm echo follow` should return Echoes to close guard, `wm echo teleport` / `wm echo tp` / `wm echo recall` should teleport all active Echoes back to spaced formation slots, and a high Echo count should no longer collapse into model-merged stacks.
- `WORKING`: live in-game smoke for the release lane was accepted after the 2026-04-16 deploy; exact combat-log numbers were not captured, so future tuning should still record tick and melee values before changing damage
- `PARTIAL`: Echo temporary-unsummon restore after player mounting is repo-tested and rebuilt/deployed to BridgeLab, but not yet proven in-game. The intended behavior is that active Echoes keep counting down while mounted and reappear after dismount if lifetime remains. The first live attempt failed because `MaintainBoneboundSummons()` still called `RemoveBoneboundAlphaEchoes()` while the pet was temporarily unsummoned; this cleanup path is now guarded.
- `PARTIAL`: visible client spellbook/action-bar path until the installed client shell-bank patch is validated in-game

What to do:

- Use shell `940001` with behavior `summon_bonebound_alpha_v3`.
- Use `.\summon-bridge-lab-bonebound-alpha.bat -PlayerGuid 5406 -Wait` after the player is online.
- Keep `summon-bridge-lab-bonebound-twins.bat` only as a compatibility alias.
- Keep future tuning measured: record Alpha melee, Echo melee, visible target bleed aura `772` duration, and 1-second physical bleed tick values before changing coefficients again.

What not to do:

- Do not set `spawn_omega=true` for the release lane.
- Do not describe 940001 as a working dual-summon/twins behavior until a true second-pet or hook-backed companion model is designed and proven.
- Do not revive TempSummon field-copy attempts for Omega damage parity.
- Do not spawn Alpha echoes from stock creature entry `1860`; target frame/nameplate text comes from creature template truth, not just `SetName()`.
- Do not remove stock Summon Voidwalker `697` from `character_spell` while cleaning WM summon experiments. Retired prototype carriers are cleanup targets; the real warlock spell is not.
- Do not claim every Demonology passive works on Alpha until the passive is tested. Template/family-based behavior and spell-id-specific behavior are different server truths.
- Do not copy Alpha health/power/damage onto a Creature/TempSummon before `ApplyOwnerTransferBonuses()` / `UpdateAllStats()`.
- Do not erase missing Echo state immediately after mounting; mount is a temporary-unsummon lifecycle event, not proof that the Echo was killed or expired.
- Do not preserve Echo state in only one updater path; player maintenance can still erase it unless the temporary-unsummon branch returns before `RemoveBoneboundAlphaEchoes()`.
- Do not persist stock visual seed/template spells such as `116`, `133`, `403`, `770`, `1459`, or `16827` in `character_spell`; use them as DBC templates, aura visuals, or triggered effects only. Player learns must target WM shell/custom spell identities.

### Retired twin summon experiments

Bonebound Twins are not the current supported release path.

The old Alpha/Omega experiment remains useful as failure evidence.

Current classification:

- `BROKEN`: Omega TempSummon stat/damage parity. Health ordering was improved, but live damage and mana still followed Creature/TempSummon behavior rather than Alpha pet behavior.
- `BROKEN`: `summon_bonebound_twin_v2` as the default release behavior for shell `940001`; keep it retired unless redesigned
- `WORKING`: Shield, Leather, and Dual Wield live proof for player `5406`; all survived the explicit GUID grant path without broad creation or playerbot tables, and Dual Wield is visible in the spellbook
- `BROKEN`: stock-carrier bindings for `697` / `49126`; do not revive them

### Persistent combat proficiency

The supported persistence model is server truth first:

- `skillraceclassinfo_dbc` makes Shield skill `433` valid for all races/classes at login, but does not grant it.
- `skillraceclassinfo_dbc` makes Leather skill `414` valid for all races/classes at login, but does not grant it.
- `skillraceclassinfo_dbc` makes Mail skill `413` valid for the Rogue combat-proficiency proof at login, but does not grant it.
- `skillraceclassinfo_dbc` makes Dual Wield skill `118` valid for all races/classes at login, but does not grant it.
- `skillraceclassinfo_dbc` makes Two-Handed Swords `55`, Two-Handed Axes `172`, and Polearms `229` valid for the Rogue combat-proficiency proof at login, but does not grant them.
- `skillraceclassinfo_dbc` makes Plate skill `293` valid for the Rogue combat-proficiency proof only from level `40`; the grant CLI also skips Plate rows below level `40`.
- the client patch must also include matching `SkillRaceClassInfo.dbc` and `SkillLineAbility.dbc` rows, or the server-side rows can persist while the skill frame still hides the new weapon families.
- `skilllineability_dbc` ties stock client-known passives `9116` and `107` to skill `433` with `AcquireMethod=2`.
- `skilllineability_dbc` ties stock client-known passive `9077` to skill `414` with `AcquireMethod=2`.
- `skilllineability_dbc` ties stock client-known passives `8737`, `202`, `197`, `200`, and `750` to Mail, Two-Handed Swords, Two-Handed Axes, Polearms, and Plate with `AcquireMethod=2`.
- Dual Wield is spell-gated by stock spell `674`, not by a skill line; the explicit grant inserts it into `character_spell`, and `mod-wm-spells` syncs `CanDualWield()` from that persistent spell only for active `combat_proficiency` grants.
- Native runtime sync is scoped to active `wm_spell_grant` shell `944000` rows for allowlisted players. It may materialize missing in-memory stock proficiency spells and `SetSkill` values from the explicit grant, but it must not create broad class/default/playerbot grants.
- `character_skills` and `character_spell` are granted only by explicit player GUID through `python -m wm.spells.shield_proficiency`.
- `wm_spell_grant` shell `944000` enables the separate intellect/spellpower block-rating passive.

Do not use these paths for Shield:

- `playercreateinfo_skills`
- `playercreateinfo_spell_custom`
- `mod_learnspells`
- playerbot factory or maintenance code
- broad runtime `OnPlayerLogin` / `OnPlayerAfterUpdate` `SetSkill(433, 1, 1)` reapply outside an explicit active `combat_proficiency` grant
- `OnPlayerIsClass` equip-shield overrides

What to do:

- Apply the world SQL updates for Shield, Leather, Mail, Dual Wield, Two-Handed Swords, Two-Handed Axes, Polearms, and level-40 Plate skill validity before live use.
- Restart worldserver after `skillraceclassinfo_dbc` or `skilllineability_dbc` changes; those DBC override tables are startup-loaded.
- Grant a real WM player explicitly with `python -m wm.spells.shield_proficiency --player-guid <guid> --mode apply --summary`.
- Verify `character_skills` contains the expected explicit rows and `character_spell` contains the matching stock proficiency passives. Below level `40`, Plate `293` / `750` must be absent and listed only as a locked capability in `wm_spell_grant.MetadataJSON`.
- Restart the WoW client after installing a refreshed client patch, then relog the player before testing persistence and spellbook display.
- Test Dual Wield with a one-handed weapon in offhand; two-handed weapons are Titan Grip, not normal Dual Wield.

What not to do:

- Do not treat DBC validity as a grant; it only prevents login validation from deleting explicit character rows.
- Do not grant these proficiencies through class creation tables, playerbot factories, maintenance commands, or `mod_learnspells`.
- Do not restore Shield, armor skills, or weapon skills with broad runtime `SetSkill` hooks; only the scoped active-grant materializer in `mod-wm-spells` may do this for an explicit `combat_proficiency` row.
- Do not override class equip checks to make shields work; fix server truth through DBC validity and explicit rows.
- Do not assume `character_spell(674)` is sufficient; AzerothCore deletes it unless skill `118` is valid for the race/class.
- Do not call two-handed offhand testing a Dual Wield failure; that requires Titan Grip and is a separate capability.

Current classification:

- `WORKING`: repo/static implementation and tests for DBC rows, explicit grant SQL, rating-only block passive, and explicit-grant runtime materialization for Shield, Leather, Mail, Dual Wield, Two-Handed Swords, Two-Handed Axes, Polearms, and level-gated Plate
- `WORKING`: live Shield, Leather, and Dual Wield proof for player `5406`; Dual Wield appears in the spellbook and one-handed offhand equip works without `.learn 674`
- `WORKING`: Broug `5405` DB/client/build/deploy/live proof for Shield, Leather, Mail, Dual Wield, Two-Handed Swords, Two-Handed Axes, and Polearms is complete after `patch-z.mpq` rebuild/install and worldserver restart to pid `10360`; DB now shows `55=18/20`, `172=1/20`, `229=1/20`, and Plate remains locked until level `40`. User live acceptance on 2026-05-01 closes the current skill-frame/equip proof for Broug's scope.
- `PARTIAL`: playerbot negative proof; current DB had zero non-Jecia warlock rows for Shield `433` or spells `107`/`9116` before the Leather/Dual Wield extension, but a maintenance/level-up cycle has not been observed after the SQL became active

### Bonebound Omega runtime failure rule

Omega is a `TempSummon`, not a saved pet row. Creature stat recalculation and Creature melee damage paths can restore or ignore template-derived runtime values after code writes custom values.

What to do:

- Treat Omega as retired for release behavior.
- If a second combat companion is needed later, design it as a hook-backed companion or a true supported pet/guardian chassis before changing fields again.
- Record live damage and resource proof before marking any second companion `WORKING`.

What not to do:

- Do not set `omega->SetMaxHealth(alphaPet->GetMaxHealth())` before `ApplyOwnerTransferBonuses()` and assume it survives.
- Do not diagnose a `33/40` or similar Omega target frame as a DB config problem before checking stat recalculation order.
- Do not treat visible copied fields as proof of actual melee damage.
- Do not revive Omega as the default 940001 behavior without a new structural design.

## Release Lane Rules

Use release mode only after the matching debug/test path is already green.

What release mode does:

- inserts the known `wm_spell_debug_request` row directly
- defaults to `summon_bonebound_alpha_v3` and shell `940001`
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

1. for any new Alpha tuning, clean the player pet state or resummon through the release wrapper
2. verify `D:\WOW\WM_BridgeLab\run\configs\modules\mod_wm_spells.conf` has `WmSpells.PlayerGuidAllowList = "5406"`; `scripts/bridge_lab/Configure-BridgeLabRuntime.ps1` and `Deploy-BridgeLabWorldServer.ps1` now set this by default
3. run `.\summon-bridge-lab-bonebound-alpha.bat -PlayerGuid 5406 -Wait`
4. record Alpha melee, visible target bleed aura `772` with duration, bleed tick values, and at least one 7.5% Alpha echo proc with `Echo Destroyer` name and non-template health
5. mount after an Echo exists, dismount before its intellect-based lifetime expires, and confirm the Echo reappears without a new proc
6. observe one playerbot maintenance/level-up cycle and confirm bots did not inherit combat proficiencies
7. build and install the local shell-bank client patch with `python -m wm.spells.client_patch build --install --summary`
8. stage a castable server DBC row with `.\scripts\bridge_lab\Stage-BridgeLabServerSpellDbc.ps1 -SeedProfile castable -SpellId 940001`
9. grant `940000` or `940001` through the workbench or native `player_learn_spell`; if native learn succeeds but SOAP `.saveall` is unavailable, persist `character_spell` explicitly before relog testing
10. validate the visible shell path:
   - spellbook entry
   - cast behavior
   - clean failure UX when gated
   - friendly summon
   - recast / dismiss / relog lifecycle
