Status: PARTIAL
Last verified: 2026-04-26
Verified by: Codex
Doc type: handoff

# WM Platform Handoff

This is the current entrypoint for a new engineer or LLM.

Use this with:

- [Documentation Index](README_OPERATIONS_INDEX.md)
- [Roadmap](ROADMAP.md)
- [Codex Working Rules](CODEX_WORKING_RULES.md)
- [Work Summary](WORK_SUMMARY.md)

## What WM is

WM is an external-first World Master platform for AzerothCore 3.3.5a.

Current architecture:

- Python WM is the reasoning and orchestration layer
- native AzerothCore modules are the sensing and atomic execution layer
- contracts, policies, and manual control live in repo-owned schemas and CLIs

## What is working now

### Platform foundations

- canonical WM event spine
- manual control contract system
- control audit visibility is `WORKING` for repo tests and native debug BridgeLab proof: `python -m wm.control.audit` inspects `wm_control_proposal`, and `wm.control.apply --summary` exposes idempotency, dry-run/apply status, and native request ids/statuses when execution produced them
- control policy validation now rejects stale non-admin source events by default after `max_source_event_age_seconds=600`, while existing idempotency and wrong-player gates remain tested
- initial subject resolver slice maps target profiles into WM subject cards and exposes `python -m wm.subjects.inspect`
- DB-backed journal reader loads WM subject definitions, enrichments, player-subject counters, and raw journal events when those tables exist; prompt demos and inspect paths now fall back to resolver-built subject cards when journal rows or live DB access are missing
- operator journal inspection exists through `python -m wm.journal.inspect`
- Personal Journey Spine V1 is `WORKING` at repo-test level and live `PARTIAL`: `python -m wm.character.journey inspect --player-guid <guid> --summary` reads character profile, arc state, exclusive unlocks, reward instances, conversation steering notes, and prompt queue entries; `python -m wm.character.journey apply --plan-json control/examples/journey/jecia_personal_spine_v1.json --mode dry-run --summary` validates the strict `wm.character_journey.seed.v1` plan without a DB connection and rejects freeform SQL/GM/shell mutation fields plus `gm_command` grant methods. Apply-mode writes only structured repo-owned character DB rows and still needs BridgeLab live DB proof for player `5406`.
- deterministic context-pack builder composes source events, character state, target profiles, subject cards, journal summaries, recent events, reactive quest runtime, control recipe/policy metadata, and latest native context snapshots into `wm.context_pack.v1`; unresolved target/event CLI requests return `UNKNOWN`
- deterministic lab seed `sql/dev/seed_journal_context_5406_world.sql` exists for player `5406`, creature entry `46`, and one seeded `wm_event_log` smoke event
- content workbench for WM-owned items, spells, and shell metadata
- content playcycle wrapper is `WORKING` at repo-test and BridgeLab live-proof level: `python -m wm.content.playcycle item-effect --scenario-json control/examples/content_playcycles/night_watchers_lens_item_effect.json --mode dry-run --summary` validates the managed item draft, slot/snapshot publish preflight, native `player_add_item` scope/policy readiness, runtime-sync intent, fresh quest promotion inputs, and rollback reporting without adding a freeform SQL/GM/LLM mutation lane. On 2026-04-24, BridgeLab proved dry-run/apply/verify/promote/rollback for player `5406`, including quest reward-panel visibility and optional native player-item cleanup.
- managed item reward proof is `WORKING` at DB/runtime-reload and live-effect level: `control/examples/items/night_watchers_lens.json` publishes item `910006` (`Night Watcher's Lens`) from a reserved WM item slot, and BridgeLab quest `910024` (`Bounty: Nightbane Dark Runner - Lens`) now rewards it through `RewardItem1=910006`, `RewardAmount1=1`, plus the existing 12 silver; the current lens effect uses visible aura spell `132` as the wearer marker, then `mod-wm-spells` gives player weapon auto-attacks and wand auto-repeat shots a 10% chance to apply or refresh a visible 10-second target debuff (`770`), halves the attack-outcome defenses covered by the current hook, doubles attack crit chance in that hook, and doubles WM-owned proc hooks such as Bonebound Alpha Echo while the visible debuff is active. On 2026-04-24, user proof confirmed the wearer aura/debuff path after BridgeLab `WmSpells.PlayerGuidAllowList` was fixed to include `5406`.
- random enchant consumable lane is `WORKING` for the original item-use, operator-selected kill grant, and scoped watcher grant proof; the current retune is repo `WORKING` / live `PARTIAL` until in-game focused vellum use is proven. Repo code keeps native action `player_random_enchant_item` as a policy-disabled typed primitive, but the player-facing flow grants consumables from scoped kill rolls instead of mutating gear directly. Item `910007` (`Unstable Enchanting Vellum`) now stacks to `999`, drops at `7%`, applies up to three random enchants through the native item menu, keeps the 15% preserve-existing chance, and gives each enchant roll a 10% chance to use tier 5. Item `910008` (`Enchanting Vellum`) stacks to `999`, drops at `3.5%`, opens an item menu followed by a slot submenu, and rerolls exactly one chosen enchant slot with weighted tiers: 40% tier 3, 30% tier 4, 30% tier 5. Repo tests cover the dual-drop idempotency path and focused slot behavior. On 2026-04-25, BridgeLab SQL apply, native rebuild/restart to worldserver pid `33620`, native `debug_ping` request `164`, direct `player_add_item` request `165` for `910007`, direct `player_add_item` request `166` for `910008`, character inventory persistence, and restarted watcher pid `30224` with `7%` / `3.5%` defaults are `WORKING`. The weighted tier retune was then rebuilt/restarted to worldserver pid `31360`, SQL text was reapplied, native `debug_ping` request `260` reached `done`, and watcher pid `27240` is armed from end; extra focused-vellum grant request `261` failed only because player `5406` was offline. User in-game menu/use proof is still pending.
- Bone Lure consumable lane is repo/build/DB/grant `WORKING` and live gameplay `PARTIAL`: item `910009` (`Bone Lure Charm`) uses known bomb ground-target UX to deploy creature `920102` (`Bone Lure Obelisk`) through `mod-wm-bridge` ItemScript/CreatureScript, scoped to the active WM player. The native runtime gives the obelisk the owner's maximum health, 75% damage reduction, DoT/status-control immunity, 30-second duration, and continuous 200-yard taunt pulses against eligible non-boss enemies while skipping bosses, dungeon bosses, no-taunt creatures, player-owned pets/totems, triggers, and civilians. SQL `2026_04_25_03_wm_bridge_bone_lure_obelisk.sql` is applied in BridgeLab, the native module builds, worldserver restarted to pid `20232`, watcher pid `18768` is armed from end, native `debug_ping` request `262` reached `done`, and native `player_add_item` request `263` granted Jecia five charms. In-game throw/taunt proof remains pending.
- managed item rollback is `WORKING` at repo-test and BridgeLab live-proof level through `python -m wm.items.rollback`: it reads latest item rollback snapshots, deletes never-existing managed rows back to `staged`, restores previous `item_template` rows back to `active`, and reports structured `snapshot` / `mysql` issues. The content playcycle rollback restored item `910006` from snapshot `110`, wrote rollback publish log `272`, reloaded `item_template` through SOAP, and reported `WORKING`.
- spell pipeline V1 is `WORKING` at repo-test level: `python -m wm.spells.publish`, `python -m wm.spells.live_publish`, and `python -m wm.spells.rollback` now cover helper/proc-table preflight, runtime-sync wrapper flow, rollback snapshots, clear-vs-restore reserved-slot status, structured schema/snapshot/MySQL failures, named-shell collision rejection, and the bundled example now lives in managed spell slot `947000`; `wm.content.workbench` now records active/revoked `wm_spell_grant` rows for WM-owned spell learns and revokes, `publish-spell` will not continue into runtime learn after a failed publish, visible spell slots resolve runtime learn through `base_visible_spell_id`, apply-mode learn/unlearn verifies the expected `character_spell` row after a `.saveall` flush plus short retry window, `wm.spells.rollback` revokes still-active `wm_spell_grant` rows for the rolled-back spell when the table exists, and `wm.reserved.db_allocator` now ignores stale shell-band / exact-claim spell rows when allocating managed spell slots; BridgeLab live publish/learn/rollback proof remains `PARTIAL` because managed slot `947000+` is still not itself a server-known learnable spell identity
- repo-owned bootstrap and bridge-lab workflows; `start-bridge-lab-all.bat` is the one-shot BridgeLab launcher for DLL guard, MySQL, realmlist, authserver, worldserver, and the scoped WM watcher for player `5406`, preserving existing bounty rules unless `-ResetBountyRules` is explicitly passed and only rewriting runtime config when `-ConfigureRuntime` is explicitly passed
- BridgeLab solo dungeon runtime tuning is config-load `WORKING` and gameplay-balance `PARTIAL`: `scripts/bridge_lab/Configure-BridgeLabRuntime.ps1` writes AutoBalance/SoloLFG/DynamicLootRates settings for solo 5-player dungeons as 75% original 5-player HP, 50% damage, 75% XP, and 2x dungeon loot. The active BridgeLab config files contain the expected values, were written before the current worldserver start, and worldserver pid `32420` is running from `D:\WOW\WM_BridgeLab\run\bin\worldserver.exe`; live dungeon feel remains unproven until an in-game dungeon check.

### Live sensing and execution

- `native_bridge` is the supported live perception path: it emits canonical WM events, uses player-scoped cursor state, and is the target for current bounty, scene, and companion proof
- retired addon/log transport experiments are historical context only; do not add new feature work on them
- `wm.events.watch` now survives per-iteration spine failures, flushes summary/error lines for automation logs instead of exiting silently, and keeps native bridge projection/evaluation scoped to the requested `--player-guid`; native bridge cursor state is now per player (`last_seen:player:<guid>`) with a legacy `last_seen` fallback for migration. `--mark-existing-evaluated-on-arm` can be paired with `--arm-from-end` for clean live proof windows so already recorded pre-arm events do not create the first dynamic rule.
- reactive bounty installs now have a repo-owned fast path through `control/examples/reactive_bounties/` and `scripts/bridge_lab/Install-BridgeLabReactiveBounty.ps1`
- reactive bounty templates are the supported fast operator lane; implicit auto-bounty creation from arbitrary kills is disabled by default and only available behind explicit opt-in config
- opt-in reactive area-pressure scenes are repo `WORKING` / live `PARTIAL`: when `WM_EVENT_AREA_PRESSURE_SCENE_ENABLED=1`, the existing area-pressure opportunity composes typed native actions instead of a second watcher path: `world_announce_to_player`, `player_restore_health_power`, and optional visible `player_apply_aura` defaulting to spell `687`. `scripts/bridge_lab/Start-BridgeLabNativeWatch.ps1 -EnableAreaPressureScene` exposes the proof lane, keeps normal player scoping, and records the config in watcher metadata. Native action idempotency now includes trigger identity plus `idempotency_suffix`, so repeated area-pressure triggers submit fresh native requests while duplicate handling for the same trigger remains stable.
- `scripts/bridge_lab/Start-BridgeLabAutoBounty.ps1` is the repo-owned BridgeLab operator lane for the opt-in dynamic path: it seeds the full managed quest slot range `910000-910999`, stops the current native watcher, deactivates existing `reactive_bounty:*` rules for the scoped player by default, then relaunches `wm.events.watch` with `WM_REACTIVE_AUTO_BOUNTY_ENABLED=1`, `--arm-from-end`, `--mark-existing-evaluated-on-arm`, `--batch-size 1`, `WM_REACTIVE_AUTO_BOUNTY_MAX_EVENT_AGE_SECONDS=3600`, and `WM_REACTIVE_AUTO_BOUNTY_SINGLE_OPEN_PER_PLAYER=1`.
- when `WM_REACTIVE_AUTO_BOUNTY_ENABLED=1`, the opt-in auto-bounty lane now binds dynamically to the exact observed creature entry after 4 consecutive same-entry kills within 300 seconds and picks the turn-in NPC from the current zone by faction-preferred quest-tie weight instead of a hardcoded target table; the streak evaluator fetches the newest bounded event slice before replaying it chronologically, so long event-log history no longer hides fresh kills, consecutive streaks fire on threshold multiples like 4/8/12 rather than only exactly 4, stale queued kills do not create new dynamic bounty rules, and one unresolved dynamic auto-bounty blocks creation of another for the same player until it is completed/rewarded/cleared. The unresolved-bounty gate prioritizes active rules and no longer caps the player auto-rule scan to 50 rows, because cleanup updates can make old inactive rows newer than the actual open quest.
- dynamic auto-bounty grant proof is `WORKING` for the current trigger/grant leg on BridgeLab: on 2026-04-26, fresh `Hederine Slayer` kills (`creature:7463`) produced rule `reactive_bounty:auto:zone:618:subject:7463`, quest `910103`, reward item `20631` (`Mendicant's Slippers`), native `quest_add` request `312` with trigger-scoped idempotency key `...native_bridge:31366...`, native bridge `quest/granted` event `31367`, WM event-log `quest_granted` event `5483`, SOAP `.quest status 910103 Jecia` reported `Status: Incomplete`, and `saveall` flushed `character_queststatus(5406, 910103)`.
- reactive native `quest_add` idempotency is now trigger-scoped: repeated bursts for the same player/rule/quest produce fresh native requests while duplicate handling for the same trigger remains stable
- dynamic auto-bounty reward selection is now `WORKING` at repo-test level: when the dynamic lane creates a new bounty rule without an explicit reward override, it picks one random stock equipment item from the live loot-backed `item_template` pool for the scoped player, constrained to `RequiredLevel` `player_level-4 .. player_level+1`, the player's class mask, and current armor/shield proficiency exceptions from `character_skills`; the previous stock `Box of Supplies` remains the fallback when no suitable equipment item is found
- `python -m wm.reactive.install_bounty --list-templates --summary` lists bundled templates, and `--template-key <key>` installs one without copying a JSON path
- reactive bounty templates now default to fresh `wm_reserved_slot` quest allocation instead of reusing one mutable live quest ID across iterations
- default bounty reward policy is `WORKING` at repo-test level: when no explicit reward override is supplied, bounty drafts now derive `RewardMoney` from quest level with `max(175, 4 * level^2)`, set `RewardXPDifficulty` to `4` below quest level `25` and `5` at `25+`, and attach stock item `6827` (`Box of Supplies`) as the default supply-cache reward; explicit template/item rewards still override the default box
- WM bounty drafts now force AzerothCore repeatable quest semantics by setting `SpecialFlags |= 1`; rewarded rows may still exist for XP/accounting, but they must not block a later bounty turn-in after quest cache reload
- reactive bounty dry-runs can preview the next free reserved quest slot without staging it or producing a false preflight failure
- shared reactive bounty publishing supports richer quest reward fields when the live `quest_template` schema exposes them:
  - money
  - reward item
  - `RewardXPDifficulty`
  - `RewardSpell` / `RewardDisplaySpell`
  - `RewardFactionID*` plus value/override slots
- native action queue exists with DB-backed policy and player scoping
- native `player_remove_item` is `WORKING` for repo-contract/static tests and BridgeLab live proof: it is scoped to the allowed online player, requires explicit `item_id` plus positive `count`, refuses non-`wm_reserved_slot` item entries unless `admin_override` is present, persists inventory after `DestroyItemCount`, and requests `139` and `142` removed managed item `910006` from player `5406`; follow-up request `143` returned `insufficient_item_count` with `available_count=0`, and the character DB had zero remaining `910006` item instances. Policy stays disabled by default, and the content playcycle rollback path reports player-inventory cleanup explicitly.
- Primitive Pack 1 is `WORKING` in BridgeLab for player `5406`: `player_apply_aura`, `player_remove_aura`, `player_restore_health_power`, `player_add_item`, `player_add_money`, `player_add_reputation`, `creature_spawn`, `creature_despawn`, `creature_say`, and `creature_emote` are implemented in `mod-wm-bridge`, stay policy-disabled by default, and `python -m wm.control.scene_play` plus direct `wm.control.apply` proofs reached native requests `54-72` `done`; `player_add_item` now explicitly saves inventory after grant, with repo tests and BridgeLab build/deploy proof after request `144` exposed DB flush lag; the bundled `field_medic_pulse`, `bonebound_battle_cry`, and `summon_marker` scenes all completed through control/audit, and the `creature_spawn` result payload now returns the real WM-owned `object_id`
- Primitive Pack 2 is `WORKING` in BridgeLab for player `5406`: `player_cast_spell`, `player_set_display_id`, `creature_cast_spell`, `creature_set_display_id`, and `creature_set_scale` are implemented in `mod-wm-bridge`, stay policy-disabled by default, creature mutation still requires WM-owned `wm_bridge_world_object` ownership, and bundled scene `arcane_marker_demo` completed through control/audit with native requests `84-89` `done`
- `context_snapshot_request` is `WORKING` for one-shot bridge-lab proof: scoped player `5406` online, native action request `31` reached `done`, `wm_bridge_context_snapshot` row `1` was written, and `wm.context.builder --event-id 603 --summary` consumed it with `native_snapshot: true`
- native spell learn and unlearn actions exist
- player-owned non-pet summon kill attribution is `WORKING` at repo and BridgeLab event-log level: `mod-wm-bridge` supplements the existing player/pet kill hooks with a guarded `UnitScript::OnUnitDeath` path for player-owned killers that are neither the player nor a real pet/totem, so Echo/guardian/temp-summon kills feed the same native watcher path without double-emitting Alpha pet kills
- `quest_grant` prefers native `quest_add` when bridge config, player scope, and policy are ready, with SOAP fallback otherwise
- control-native convergence V1 is `WORKING` for the current operator scope: repo tests cover audit/request extraction plus stale-event, wrong-player, and idempotency rejection visibility; BridgeLab fresh-event proof on 2026-04-16 reached event `1599` -> proposal `43` -> native `quest_add` request `74` `done` -> `quest_grant_issued` event `1601`, and native bridge event `26505` recorded `quest/granted` for quest `910020`
- the Phase 1 reactive bounty loop has repo-level automated parity coverage and historical native bridge proof for quest `910000`

### Native spell platform

- shell-bank contract exists
- 2026-04-27 Echo seek / Restorer cast / Stasis pool / spacing retune is repo/build/deploy `WORKING` and live `PARTIAL`: seek now searches from the active WM player so Echoes converge on the nearest eligible hostile to Jecia, Restorers can leave the close support ring in seek mode to get into visible cast range, Restorer filler DPS starts a real visible Mind Blast `8092` cast instead of a fake delayed triggered hit, runtime name changes force object-visibility refresh for `Echo Destroyer` / `Echo Restorer`, Stasis adds active Echo counts into the saved pool instead of replacing it, and Echo follow slots use deterministic formation rings with a 1.6 yard spacing target instead of random slot collision. BridgeLab worldserver restarted to pid `28000`; in-game proof remains pending.
- custom ID ledger is `WORKING` at repo-contract level: `data/specs/custom_id_registry.json` is now the exact-claim authority, `docs/CUSTOM_ID_LEDGER.md` is the operator-facing mirror, and stale spell collision between shell `940000` and the managed spell example was removed by moving the managed spell lane to `947000+`
- client patch workspace and local MPQ build lane are `WORKING` at repo/artifact level: `python -m wm.spells.client_patch build` materializes `DBFilesClient\Spell.dbc` plus `DBFilesClient\SkillLineAbility.dbc`, packages them with repo-local Ladik MPQ Editor from `.wm-bootstrap\tools\mpqeditor`, verifies extraction, and can install `patch-z.mpq` to the WoW client `Data` directory when the client is closed
- server Spell.dbc materialization lane is `WORKING` for named compatibility shells: `python -m wm.spells.server_dbc materialize` plus `scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1` now clone server-proof seed rows into `940000`, `940001`, `944000`, `945000`, and `946600`, and the 2026-04-17 BridgeLab proof staged the earlier named ids into `D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc`
- server Spell.dbc cast-shape staging is `WORKING` for the visible `940001` test lane: `Stage-BridgeLabServerSpellDbc.ps1 -SeedProfile castable -SpellId 940001` stages a Raise-Dead-style effect/target row plus presentation fields, and the staged DBC now reports `effect=(28,0,0)`, `targetA=(32,0,0)`, `range=1`, `cast=14`, `icon=221`, `mana=180`
- `mod-wm-spells` exists as the stable native spell-behavior runtime
- lab debug invoke exists for shell-bound behavior testing without a visible client shell
- generic shell-bank V2 is `WORKING` at repo-contract level: pinned compatibility shells remain on `940000`, `940001`, `944000`, and `945000`, while generic cast-shape families now occupy `946000-946999` as five 100-slot families with 100-id reserve gaps
- shell-backed server learn/revoke proof is `WORKING` for named shell `940001` on BridgeLab after the server DBC stage: `wm.content.workbench grant-shell --shell-key bonebound_twins_v1` created `character_spell(5406, 940001)` and an active `wm_spell_grant` row, and `ungrant-shell` removed the character-spell row and revoked that grant; this is server truth only, not final client spellbook/action-bar proof
- Bonebound Alpha native lane is `WORKING` for visible Alpha/Echo bleed on shell `940001`: bridge-lab SQL binds `summon_bonebound_alpha_v3`, `spawn_omega=false`, WM stock-carrier use of `697` / `49126` remains retired while normal Summon Voidwalker `697` is preserved, and the repo/native code applies Alpha and Echo bleed from melee hooks with visible target aura `772` plus WM-owned physical ticks. Echo bleed state is keyed by Echo caster GUID plus target GUID so multiple Echoes can stack independently. Bleed tick damage is attack-power-primary through `bleed_damage_per_attack_power_pct=20`, with direct level/intellect/shadow coefficients zeroed; shadow spell power still contributes indirectly through Alpha attack power transfer. BridgeLab compile/deploy passed on 2026-04-25, worldserver restarted to pid `32248`, and user live proof accepted the retuned damage path.
- Bonebound Alpha Echo attack reacquire and seek-mode control are repo/build `WORKING` and live gameplay `PARTIAL`: Echo maintenance forces threat/combat/attack/chase against Alpha's current victim when Echo Destroyer follow motion gets stale. The active WM player can type `wm echo seek` to make Echo Destroyers attack and Echo Restorers ranged-target/cast at the nearest eligible hostile to the player within the configured seek radius, `wm echo seek 60` to enable seek at a specific radius, `wm echo range 60` to retune seek radius without changing mode, `wm echo follow` to restore close guard behavior, and `wm echo teleport` / `wm echo tp` / `wm echo recall` to teleport all active Echoes back to the player. Runtime seek radius is per-player, scoped to the active WM player, and clamped to `5-100` yards. In-game proof of the owner-centered seek retune is still pending.
- Echo Restorer support variant is repo/build/DB `WORKING` and live gameplay `PARTIAL`: Alpha melee now has a separate `5%` support Echo proc, creature template `920103` (`Echo Restorer`) is SQL-applied in BridgeLab with Skeletal Magelord display `11397` from stock NPC `15121`, and native support logic exists. Restorers have a separate active cap of `10`, Echo Destroyers still use the existing cap, and a pity counter forces a Restorer spawn attempt after `6` successful Destroyer spawns without a successful Restorer. The Restorer picks one configured level-appropriate rare/epic staff model when spawned, copies Alpha stats after the owner-intellect stat transfer path, follows in randomized closer slots around `priest_echo_safe_follow_distance=1.8`, matches Echo Destroyer template speed plus Alpha-derived runtime movement rates after stat recalculation, never uses melee damage, heals/protects/regenerates the lowest hurt owner/Alpha/Echo/group target with visible client-known spells `2061`, `17`, and `139`, shields only targets under active attack/cast pressure, adds owner shadow spell power to healing/shield amounts and `45%` of owner shadow spell power to filler damage, cleanses disease/curse with visible single dispels, uses thresholded Mass Dispel `32375` on a 3 minute cooldown, and starts a real visible Mind Blast cast through spell `8092` for filler damage with `priest_echo_dps_damage_pct=19` and `priest_echo_dps_max_range=100.0`; in-game cast/positioning/speed/seek proof of the retune is still pending.
- Bonebound Echo Stasis is repo `WORKING` / live `PARTIAL`: named shell `946600` stores only Echo Destroyer/Echo Restorer counts in `wm_bonebound_echo_stasis`. If active Echoes exist, casting Stasis adds those active counts into the existing pool and despawns them; if no Echoes are active, casting restores stored counts from the current Bonebound Alpha with fresh runtime stats, full HP/mana, and max timers. Restore preserves any over-cap remainder in the pool. The shell is configured as a 5 second self-cast with Soul Shard reagent presentation; BridgeLab SQL/DBC/build/grant/in-game proof is pending.
- unsafe stock visual seed spell persistence is repo/live `WORKING`: `wm.content.workbench` now refuses to persist stock visual/template spells `116`, `133`, `403`, `770`, `1459`, and `16827` as player learns, because AzerothCore deletes them for Jecia's race/class on login. BridgeLab cleanup removed those six stale `character_spell` rows for player `5406`; use WM shell/custom spell identities for player grants and keep stock spell IDs as templates, visuals, or triggered effects only.
- Bonebound Alpha stat transfer is `WORKING` in native config/code and BridgeLab live proof: summoner total intellect is applied to Alpha stats and shadow spell power is applied to Alpha attack power after the 2026-04-24 `mod_wm_spells.conf` allowlist fix
- Bonebound Alpha fast release submitter is `WORKING`: `python -m wm.spells.summon_release --player-guid 5406 --summary` submits shell `940001` directly and now defaults to behavior `summon_bonebound_alpha_v3`
- Bonebound Alpha Gorehowl weapon config is `WORKING` at DB/config and BridgeLab live level: shell `940001` behavior config sets Alpha virtual item 1 to `28773`, and user proof after the 2026-04-24 allowlist fix confirmed the weapon overlay applies
- persistent combat proficiency repo and live path are `WORKING` for player `5406`: DBC override SQL makes Shield `433`, Leather `414`, and Dual Wield skill `118` login-valid, `python -m wm.spells.shield_proficiency --player-guid 5406 --mode apply --summary` grants only the explicit player GUID through `character_skills`, `character_spell`, and `wm_spell_grant`, and the block-rating passive shell `944000` no longer restores Shield by runtime `SetSkill` or class override hooks; Dual Wield persists through stock spell `674`, `mod-wm-spells` materializes the volatile `CanDualWield()` flag only for active `combat_proficiency` grants, offhand one-handed sword equip works, and Dual Wield displays in the spellbook

## What is partial

- `native_bridge` is not yet the fully proven primary live path for all current WM gameplay loops
- the April 13, 2026 bridge-lab rerun only reached smoke level:
  - `debug_ping` reached `done`
  - `wm.events.watch --adapter native_bridge --arm-from-end` advanced the live high-water mark
  - the full in-game `Kobold Vermin -> quest 910000 -> reward -> cooldown -> regrant` loop was not rerun because validation player `5406` was offline
- broad native action vocabulary exists, but many verbs are still disabled or `not_implemented`; Pack 1 and Pack 2 scene primitives are the current proven mutation slices
- subject recognition is only a first slice:
  - static lookup and live-target resolver wrapping exist
  - DB-backed journal read helpers and resolver-card fallback exist
  - context-pack assembly exists and includes recipe/policy metadata plus latest native snapshot rows when present
  - repo tests are `WORKING` for the resolver, journal reader/inspect, and context-pack assembly
  - bridge-lab DB proof on `127.0.0.1:33307` is `WORKING` for the seeded player `5406` / creature `46` journal and event-backed context pack
  - automatic subject materialization, zone mood, and full proposal-gate previews are still `PARTIAL`
- visible shell-bank spellbook presentation is `WORKING` for `940001`: the refreshed MPQ artifact is installed with `Spell.dbc` and `SkillLineAbility.dbc`, server `940001` is staged with the castable profile, BridgeLab worldserver restarted on pid `8580`, `character_spell(5406,940001)` is persistent, `wm_spell_grant` row `5` is active, and user proof on 2026-04-17 showed the spell in the Warlock/Demonology tab with icon, 180 mana, and 3 second cast; caster animation/action-bar/relog lifecycle polish remains `PARTIAL`
- Bonebound Alpha earlier release-lane smoke proved summon/echo basics, but visible bleed status is now `PARTIAL`: after the visible-bleed rebuild, capture target aura `772` duration plus exact tick and melee values before changing coefficients
- Bonebound Alpha echo mount/dismount restore is `PARTIAL`: repo/static tests cover preserving Echo state during player mount temporary-unsummon, preventing player maintenance from erasing that state while the main pet is absent, and respawning it with remaining lifetime after the Bonebound pet returns; the rebuilt worldserver was deployed to BridgeLab pid `31208`, and live in-game proof is still pending
- Bonebound Alpha stock/pet separation is `PARTIAL`: the structural fix is deployed in BridgeLab so stock Voidwalker stays on creature entry `1860`, Bonebound Alpha moves to WM creature entry `920100`, Jecia's saved Alpha row was migrated off `1860`, and the runtime no longer classifies pets by stock entry/display fallback; fresh in-game proof that casting `697` now summons a real Voidwalker while `940001` summons Alpha is still pending
- Bonebound Alpha Demonology interaction is `PARTIAL`: Alpha is now a real pet created from WM creature entry `920100`, cloned from the Voidwalker template and summoned by shell `940001`, so generic demon/pet/template-family mechanics may apply, but any passive keyed to stock Summon Voidwalker spell `697`, stock creature entry `1860`, or stock CreatedBySpell behavior is not proven
- combat proficiency bot-safety proof is `PARTIAL`: player `5406` is confirmed live for Shield, Leather, and Dual Wield, but a playerbot maintenance cycle still needs to show bots did not inherit the grants
- experimental `template_watch` / `template_publish` comparison work remains isolated in `.worktrees/template-watch-compare`; its dynamic binding idea is useful, but its standalone watcher path is not the production architecture
- implicit auto-bounty generation is not a supported default path; use explicit JSON templates or `--template-key` to install the exact bounty being tested, and enable the dynamic 4-in-a-row auto-bounty lane only when that specific live behavior is what you are validating
- full auto-bounty playcycle proof is still `PARTIAL`: native bridge perception, dynamic rule creation, fresh native quest grant, and client/server quest state are proven live. Quest `910103` (`Bounty: Hederine Slayer`) reached SOAP `Complete` and DB `status=1` / `mobcount1=4`; a pre-fix single-open gate miss then created current active quest `910102` (`Bounty: Hederine Initiate`). Reward -> suppress -> cooldown -> regrant still needs the active quest `910102` to be completed and turned in.
- content playcycle live proof is `WORKING`: dry-run/apply/verify/promote/rollback have BridgeLab proof for player `5406`, fresh quest slot `910075` was allocated for reward promotion, native request `141` granted quest `910075`, native bridge event `27945` recorded `quest/granted`, user screenshot proof confirmed reward-panel visibility for `Night Watcher's Lens`, user proof confirmed Lens aura/debuff plus related `mod-wm-spells` effects after the allowlist fix, rollback restored item `910006` from snapshot `110`, and cleanup request `142` removed the player item copy.

## What is broken or retired

- stock spell carrier reuse for WM abilities is retired
- `mod-wm-prototypes` is not the main summon or ability lane
- visible stock-carrier summon testing is retired
- Bonebound Omega TempSummon parity is broken and retired for the release lane: live proof showed Alpha melee around `120`, Omega melee around `9`, and Omega mana around `20` even after field-copy hardening
- freeform LLM mutation of configs, SQL, shell commands, or arbitrary game state is not allowed

For the summon failure history, read:

- [Summon Failure Postmortem](SUMMON_FAILURE_POSTMORTEM.md)
- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)

## System map

### Key repo areas

- `src/wm/` - Python orchestration, control, content, prompt, and runtime tooling
- `control/` - event/action/recipe/policy contracts
- `native_modules/mod-wm-bridge/` - native sensing and action queue
- `native_modules/mod-wm-spells/` - native shell-bound spell behavior runtime
- `scripts/bridge_lab/` - isolated native build and runtime helpers
- `client_patches/wm_spell_shell_bank/` - shell-bank patch workspace

### Key runtime/data pieces

- `wm_event_log`
- `wm_bridge_event`
- `wm_bridge_action_request`
- `wm_control_proposal`
- `wm_spell_shell`
- `wm_spell_behavior`
- `wm_spell_grant`
- `wm_spell_debug_request`

## Architecture boundary for ambitious features

Use this model when proposing or implementing "wild" abilities:

1. trigger or event
2. Python-side decision and state
3. atomic action sequence or shell-bound native behavior
4. client requirement level

Feature feasibility filter:

- `T1` server only
- `T2` server plus existing client assets
- `T3` client patch required
- `T4` client asset or UI work
- `NOT FEASIBLE` on stock 3.3.5a

If a feature needs a visible spellbook entry, hotbar button, or owned tooltip, treat it as `T3` immediately.

## Read order by task

### If you are working on summon or spell behavior

1. [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)
2. [Summon Failure Postmortem](SUMMON_FAILURE_POSTMORTEM.md)
3. [mod-wm-spells README](../native_modules/mod-wm-spells/README.md)
4. [Spell Shell Bank V1](SPELL_SHELL_BANK_V1.md)

### If you are working on native bridge actions

1. [Native Bridge Action Bus](native-bridge-action-bus.md)
2. [ADR 0002](adr/0002-extend-existing-action-bus.md)
3. [Roadmap](ROADMAP.md)

### If you are working on repo process or agent behavior

1. [../AGENTS.md](../AGENTS.md)
2. [Codex Working Rules](CODEX_WORKING_RULES.md)
3. [Documentation Index](README_OPERATIONS_INDEX.md)

## Known footguns

- Client-visible spell work requires client truth, not just server truth.
- Hidden server-side effects must have a player-facing indication and the server logic must be gated by that indication's live state/duration. Use an aura, buff, debuff, combat-log/system message, or tooltip path; do not ship invisible stat/resource/combat changes and do not attach unrelated stock effects just to make a tooltip appear.
- "Double every proc" is not a free item-template feature. Night Watcher's Lens doubles attack crit in the current melee/ranged outcome hook and WM-owned proc hooks that explicitly check the tracked visible debuff; arbitrary stock/core proc doubling remains `PARTIAL` until a proper proc-event hook is added.
- combat proficiency persistence requires DBC validity plus explicit character rows; do not restore skills with login/update `SetSkill` hooks, class-equip overrides, `playercreateinfo_skills`, `mod_learnspells`, or playerbot maintenance. Dual Wield needs skill `118` to be DBC-valid before spell `674` survives login; native runtime may then materialize `CanDualWield()` from persistent spell `674` only for explicit `combat_proficiency` grants. Two-handed offhand weapons require Titan Grip and are not normal Dual Wield.
- Bonebound Omega field copying is not proof of real combat parity. If a second combat companion returns later, use a true supported pet/guardian chassis or hook-backed damage path and prove health, mana, and melee output in the lab before marking it `WORKING`.
- Alpha echo template truth matters: spawn echo procs from WM creature entry `920101`, not stock Voidwalker `1860`, and copy final Alpha health/power/damage only after `UpdateAllStats()` paths have run.
- Stock Summon Voidwalker `697` must remain a normal warlock spell. WM summon cleanup may remove retired prototype carriers such as `49126`, but must not delete `character_spell(697)` or bind WM scripts back onto `697`.
- Do not treat Warlock/Demonology spellbook placement as proof that every Demonology passive applies. Verify each passive against the actual server check path: pet family/type, creature entry, aura ownership, created-by spell, or explicit spell id.
- Do not let old auto-generated bounty rules drive live tests. Install one explicit template by path or `--template-key`, or explicitly enable the dynamic auto-bounty lane, then arm the watcher from the end and start killing only after arming.
- Do not mix leftover `reactive_bounty:template:*` rows with the dynamic auto-bounty lane. Exact/template rules are matched before dynamic rule creation, so stale template rows can hijack the same kill stream. Use `python -m wm.reactive.auto_bounty --player-guid <guid> --deactivate-existing-bounty-rules --summary` or `scripts/bridge_lab/Start-BridgeLabAutoBounty.ps1` before live dynamic tests.
- Consecutive auto-bounty streaks are based on recorded kill events, not combat text. After the 2026-04-17 bridge patch, player-owned non-pet summons can also contribute to and reset those streaks. Streak code must fetch the newest bounded event slice first and only then replay it chronologically; `ORDER BY EventID ASC LIMIT n` returns stale history on a long-running lab DB and breaks live watcher triggers. The streak key is the exact `subject_entry`, not the display name, so mixed dungeon packs like `Razorfen Quilguard` / `Razorfen Warrior` / `Crimson Whelp` do not count as one shared streak even if the player perceives them as one pull.
- Do not solve a WM/playerbot crash by making WM BridgeLab scripts globally write `AiPlayerbot.EnableBroadcasts = 0`. That is a temporary runtime safety switch at most; WM event capture must remain scoped through `WmBridge.PlayerGuidAllowList` / `wm_bridge_player_scope`, and playerbot broadcast crashes need a targeted playerbot-path fix.
- Primitive Pack 2 display/cast/scale actions are still operator lab primitives, not content defaults. Keep policy disabled outside explicit scoped tests; player display changes are temporary server display changes, not a client shell or persistent appearance system.
- Native `quest_add` parity depends on GM-force-grant semantics. WM force grants must mirror `.quest add` sanity checks, not `player->CanTakeQuest()`, or repeatable/operator quests can reject natively even while the existing SOAP lane succeeds.
- Immediate `character_queststatus` reads are not sufficient proof for a fresh live quest grant on this core branch. For fresh native grants, trust `wm.control.audit`, native bridge `quest/granted`, and GM `.quest status` before claiming the grant failed just because the character DB row is absent or delayed.
- Repeated bounty turn-ins depend on repeatable quest template state, not manual rewarded-row deletion. If a repeated bounty cannot be turned in, first verify `quest_template_addon.SpecialFlags & 1`, then run `.reload all quest`; only clear `character_queststatus_rewarded` as a targeted recovery step when the quest row is confirmed non-repeatable or stale and the player does not have an active copy.
- Default bounty rewards are no longer coin-only; they auto-attach stock `Box of Supplies` plus level-scaled money and XP. Use managed item slots when you need a bespoke reward beyond that stock supply-cache baseline, and do not solve "wand fires while moving" as an item-template-only edit; that still needs native combat/action behavior or client-facing shell work.
- Do not reuse an already accepted/rewarded quest ID when changing visible rewards. On 2026-04-17, quest `910021` kept showing only 12 silver after an item reward edit because that ID had already been accepted/rewarded in the live client session. Publish a fresh reserved quest slot, reload/restart as needed, then grant the new quest ID.
- Control proposals for non-admin event-bound actions must use a fresh source event; old copied proposal JSON will be rejected as stale by policy.
- Dirty lab state can poison summon and pet retests.
- Design docs can be useful and still be stale.
- Current-state docs and postmortems outrank aspirational design notes.
- The repo may contain dirty local experiments; only supported paths in status docs should be treated as trusted.
