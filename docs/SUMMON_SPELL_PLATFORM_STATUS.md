Status: PARTIAL
Last verified: 2026-04-17
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
- generic V2 bank uses five 100-slot cast-shape families under `946000-946999`, with 100-id reserve gaps between families
- named shell entries exist for `940000`, `940001`, `944000`, and `945000`
- `WORKING`: server-side Spell.dbc materialization now exists for named compatibility shells through `python -m wm.spells.server_dbc materialize` and `scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1`; the current BridgeLab proof stages `940000`, `940001`, `944000`, and `945000` into `D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc`
- `WORKING`: named shell `940001` is now proven as a server-known learnable identity on BridgeLab after the DBC stage: `grant-shell` writes `character_spell(5406, 940001)` plus active `wm_spell_grant`, and `ungrant-shell` removes the row and revokes the grant after `.saveall` and retry-backed verification
- `WORKING`: client patch packaging is repo-owned through `python -m wm.spells.client_patch`. On 2026-04-17, Codex downloaded official Ladik MPQ Editor into `.wm-bootstrap\tools\mpqeditor`, built and verified `.wm-bootstrap\state\client-patches\wm_spell_shell_bank\patch-z.mpq`, and the builder now emits both `DBFilesClient\Spell.dbc` and `DBFilesClient\SkillLineAbility.dbc`.
- `WORKING`: shell presentation metadata is explicit for `940001`: Animate Dead icon `221`, 3 second cast time through `SpellCastTimes` index `14`, 180 mana cost, Summon Voidwalker visual `4054`, and a Warlock/Demonology spellbook mapping cloned from Summon Voidwalker skill-line ability row `697 -> 354`.
- `WORKING`: server DBC materialization now has separate profiles. `learnable` keeps the neutral grant/revoke proof seed. `castable` uses the client cast-shape seed for visible-shell tests; repo tests now verify `940001` carries visual field `SpellVisualID_2 = 4054`, and the previous 2026-04-17 BridgeLab stage verified the server row has effect `(28,0,0)`, target `(32,0,0)`, range `1`, cast time `14`, icon `221`, and mana cost `180`.
- `WORKING`: the refreshed client MPQ package is installed at `D:\WOW\world of warcraft 3.3.5a hd\Data\patch-z.mpq`, and BridgeLab worldserver was restarted on pid `8580` so the staged server DBC is loaded. In-game proof on 2026-04-17 showed `940001` in the Warlock/Demonology spellbook with the intended icon, 180 mana cost, and 3 second cast time.
- `PARTIAL`: caster animation/visual polish is still open. The shell contract now pins `940001` to Summon Voidwalker visual `4054` instead of Raise Ghoul visual `749`, but the refreshed client/server DBC artifacts still need to be rebuilt, restaged, and proven in-game.

### Native spell runtime

- `mod-wm-spells` builds in `WM_BridgeLab`
- shell, behavior, grant, and debug tables exist
- debug invoke resolves shell-bound config from `wm_spell_behavior`
- `WORKING`: Bonebound Alpha debug/native lane uses WM shell `940001`, not stock `697` or `49126`
- `WORKING`: lab DB proof on 2026-04-15 retired `49126`, disabled its behavior row, removed stock WM spell-script bindings, and left only `940001 -> spell_wm_shell_dispatch`
- `WORKING`: repo/runtime separation now moves Bonebound off stock creature truth. Alpha uses WM creature template `920100`, stock Voidwalker remains `1860`, and `IsBoneboundPet()` no longer falls back to stock entry/display heuristics.
- `PARTIAL`: stock Summon Voidwalker separation is deployed but not yet re-proven in-game after the structural fix. BridgeLab DB proof on 2026-04-17 now shows `character_spell(5406,697)` and `character_spell(5406,940001)` present, `49126` absent, Jecia's saved Alpha row migrated to `character_pet.entry=920100`, `wm_spell_behavior(940001)` repointed to `creature_entry=920100`, and only `940001 -> spell_wm_shell_dispatch` in `spell_script_names`. The prior cleanup-only state was still broken because Alpha shared stock creature entry `1860`.
- `WORKING`: historical lab invoke request `7` for player `5406` executed the old twin behavior and persisted `Bonebound Alpha` with `CreatedBySpell=940001`
- `WORKING`: Bonebound Alpha behavior config transfers the summoner's total intellect to all Alpha stats and shadow spell power to Alpha attack power; BridgeLab live proof passed after the 2026-04-24 `WmSpells.PlayerGuidAllowList` fix
- `PARTIAL`: Bonebound Alpha visible bleed fix is in repo/native code and BridgeLab compile passed on 2026-04-24 with `Build-BridgeLabIncremental.ps1 -NoStageRuntime`: shell `940001` maps to `summon_bonebound_alpha_v3`, `spawn_omega=false`, Alpha config keeps Gorehowl visual item `28773`, and Alpha bleed is now intended to apply only from the Alpha melee hook with visible client aura spell `772` (`Rend`) as the target status/duration marker while WM owns the physical tick damage. Legacy `shadow_dot_*` config keys still parse, but current drafts and SQL use `bleed_*`. Live status stays `PARTIAL` until runtime staging/restart, SQL migration, and in-game proof.
- `WORKING`: Alpha echoes use WM creature template `920101` (`Bonebound Alpha Echo`) instead of spawning from the Voidwalker template; runtime stat recalculation runs before Alpha health/power/damage is copied, each echo gets a randomized follow distance/angle around the player, and the active Echo cap is configured to `40`; native bridge event `27941` recorded an owned-unit kill from object entry `920101`
- `PARTIAL`: Alpha echo mount/dismount restore is implemented, repo/static-tested, native-built, and deployed to BridgeLab worldserver pid `31208`. The runtime now preserves missing Echo state while the owner pet is temporarily unsummoned by mounting, prevents player maintenance from erasing that state while the main pet is absent, then respawns the Echo from the saved template/follow slot with its remaining lifetime after the Bonebound pet returns. Live in-game BridgeLab proof is still pending.
- `WORKING`: Bonebound Alpha release submitter exists at `python -m wm.spells.summon_release`; it now defaults to behavior `summon_bonebound_alpha_v3` and shell `940001`
- `WORKING`: live post-restart Alpha v3 smoke was accepted on 2026-04-16 after request `11` completed for online player `5406`; repo evidence proves the active pet row is `Bonebound Alpha` on shell `940001`, and user validation reported the bleed/echo behavior acceptable
- `PARTIAL`: Demonology passive compatibility is not globally proven. Alpha now uses WM creature entry `920100`, cloned from the Voidwalker template so family/type truth stays demon-like, but anything hardcoded to stock spell `697`, stock creature entry `1860`, or stock CreatedBySpell semantics is unverified because Alpha is created by WM shell `940001`.
- `BROKEN`: Bonebound Omega TempSummon parity is retired for the release lane. Live evidence showed Alpha melee around `120`, Omega melee around `9`, and Omega mana around `20`; copying Alpha-visible fields onto a Creature/TempSummon did not affect the actual combat path reliably.
- `WORKING`: persistent combat proficiency repo path exists through DBC override SQL plus explicit GUID grant:
  - `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_15_02_wm_spell_shield_proficiency.sql` seeds high-ID `skillraceclassinfo_dbc` and `skilllineability_dbc` rows for Shield skill `433`
  - `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_15_03_wm_spell_leather_dual_wield_proficiency.sql` seeds high-ID `skillraceclassinfo_dbc` and `skilllineability_dbc` rows for Leather skill `414`
  - `native_modules/mod-wm-spells/data/sql/world/updates/2026_04_15_04_wm_spell_dual_wield_skill_validity.sql` seeds high-ID `skillraceclassinfo_dbc` for Dual Wield skill `118`, which AzerothCore validates before keeping spell `674`
  - `python -m wm.spells.shield_proficiency --player-guid 5406 --mode apply --summary` upserts only `character_skills(118,433,414)`, `character_spell(107,9116,9077,674)`, and a `wm_spell_grant` marker for shell `944000`
  - `mod-wm-spells` materializes AzerothCore's volatile Dual Wield runtime flag only when the player is allowlisted, has an active `combat_proficiency` grant for shell `944000`, and already has persistent spell `674`
  - bridge-lab live proof on 2026-04-15 confirmed player `5406` can equip Shield, Leather, and a one-handed sword in offhand; Dual Wield is also visible in the spellbook
  - focused repo tests verify the SQL does not insert or update `playercreateinfo_skills`, `playercreateinfo_spell_custom`, or `mod_learnspells`
- `WORKING`: `passive_intellect_block_v1` is rating-only; it reads an active `wm_spell_grant` and applies block rating from intellect plus spell power, but it no longer calls `SetSkill`, `SetCanBlock`, or overrides shield equip class checks. BridgeLab live proof passed after the 2026-04-24 `WmSpells.PlayerGuidAllowList` fix.

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

No longer blocked on MPQ packaging. The repo can now build the client shell-bank patch with `Spell.dbc` plus `SkillLineAbility.dbc`, and BridgeLab has a matching cast-shape server row for `940001`.

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
- `PARTIAL`: native Alpha bleed implementation compiles with default 6 second cooldown, 4 second duration, 1 second tick, low level/intellect scaling, no shadow spell-power scaling, visible target aura `772`, and melee-hook-only application; live proof is pending after runtime staging/restart
- `WORKING`: Alpha passive echo implementation exists with 7.5% melee proc chance, maximum 40 active echoes, WM creature template `920101`, randomized follow slots around the player, and echo lifetime equal to summoner total intellect in seconds
- `WORKING`: live in-game smoke for the release lane was accepted after the 2026-04-16 deploy; exact combat-log numbers were not captured, so future tuning should still record tick and melee values before changing damage
- `PARTIAL`: Echo temporary-unsummon restore after player mounting is repo-tested and rebuilt/deployed to BridgeLab, but not yet proven in-game. The intended behavior is that active Echoes keep counting down while mounted and reappear after dismount if lifetime remains. The first live attempt failed because `MaintainBoneboundSummons()` still called `RemoveBoneboundAlphaEchoes()` while the pet was temporarily unsummoned; this cleanup path is now guarded.
- `PARTIAL`: visible client spellbook/action-bar path until the installed client shell-bank patch is validated in-game

What to do:

- Use shell `940001` with behavior `summon_bonebound_alpha_v3`.
- Use `.\summon-bridge-lab-bonebound-alpha.bat -PlayerGuid 5406 -Wait` after the player is online.
- Keep `summon-bridge-lab-bonebound-twins.bat` only as a compatibility alias.
- Validate Alpha melee, visible target bleed aura `772` with duration, 1-second physical bleed ticks, `Bonebound Alpha Echo` name/health, one echo proc in combat, and mount/dismount Echo restoration before calling the live ability proof `WORKING`.

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
- `skillraceclassinfo_dbc` makes Dual Wield skill `118` valid for all races/classes at login, but does not grant it.
- `skilllineability_dbc` ties stock client-known passives `9116` and `107` to skill `433` with `AcquireMethod=2`.
- `skilllineability_dbc` ties stock client-known passive `9077` to skill `414` with `AcquireMethod=2`.
- Dual Wield is spell-gated by stock spell `674`, not by a skill line; the explicit grant inserts it into `character_spell`, and `mod-wm-spells` syncs `CanDualWield()` from that persistent spell only for active `combat_proficiency` grants.
- `character_skills` and `character_spell` are granted only by explicit player GUID through `python -m wm.spells.shield_proficiency`.
- `wm_spell_grant` shell `944000` enables the separate intellect/spellpower block-rating passive.

Do not use these paths for Shield:

- `playercreateinfo_skills`
- `playercreateinfo_spell_custom`
- `mod_learnspells`
- playerbot factory or maintenance code
- runtime `OnPlayerLogin` / `OnPlayerAfterUpdate` `SetSkill(433, 1, 1)` reapply
- `OnPlayerIsClass` equip-shield overrides

What to do:

- Apply the world SQL updates for Shield, Leather, and Dual Wield skill validity before live use.
- Restart worldserver after `skillraceclassinfo_dbc` or `skilllineability_dbc` changes; those DBC override tables are startup-loaded.
- Grant a real WM player explicitly with `python -m wm.spells.shield_proficiency --player-guid <guid> --mode apply --summary`.
- Verify `character_skills` contains `118`, `414`, and `433`, and `character_spell` contains `107`, `674`, `9077`, and `9116`.
- Relog the player before testing persistence and spellbook display.
- Test Dual Wield with a one-handed weapon in offhand; two-handed weapons are Titan Grip, not normal Dual Wield.

What not to do:

- Do not treat DBC validity as a grant; it only prevents login validation from deleting explicit character rows.
- Do not grant these proficiencies through class creation tables, playerbot factories, maintenance commands, or `mod_learnspells`.
- Do not restore Shield or Leather with runtime `SetSkill` hooks.
- Do not override class equip checks to make shields work; fix server truth through DBC validity and explicit rows.
- Do not assume `character_spell(674)` is sufficient; AzerothCore deletes it unless skill `118` is valid for the race/class.
- Do not call two-handed offhand testing a Dual Wield failure; that requires Titan Grip and is a separate capability.

Current classification:

- `WORKING`: repo/static implementation and tests for DBC rows, explicit grant SQL, rating-only block passive, and explicit-grant Dual Wield runtime sync
- `WORKING`: live Shield, Leather, and Dual Wield proof for player `5406`; Dual Wield appears in the spellbook and one-handed offhand equip works without `.learn 674`
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
4. record Alpha melee, visible target bleed aura `772` with duration, bleed tick values, and at least one 7.5% Alpha echo proc with `Bonebound Alpha Echo` name and non-template health
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
