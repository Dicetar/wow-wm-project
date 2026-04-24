Status: PARTIAL
Last verified: 2026-04-24
Verified by: Codex
Doc type: handoff

# WM Platform Handoff

This is the current entrypoint for a new engineer or LLM.

Use this with:

- [Documentation Index](README_OPERATIONS_INDEX.md)
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
- deterministic context-pack builder composes source events, character state, target profiles, subject cards, journal summaries, recent events, reactive quest runtime, control recipe/policy metadata, and latest native context snapshots into `wm.context_pack.v1`; unresolved target/event CLI requests return `UNKNOWN`
- deterministic lab seed `sql/dev/seed_journal_context_5406_world.sql` exists for player `5406`, creature entry `46`, and one seeded `wm_event_log` smoke event
- content workbench for WM-owned items, spells, and shell metadata
- content playcycle wrapper is `WORKING` at repo-test and BridgeLab live-proof level: `python -m wm.content.playcycle item-effect --scenario-json control/examples/content_playcycles/night_watchers_lens_item_effect.json --mode dry-run --summary` validates the managed item draft, slot/snapshot publish preflight, native `player_add_item` scope/policy readiness, runtime-sync intent, fresh quest promotion inputs, and rollback reporting without adding a freeform SQL/GM/LLM mutation lane. On 2026-04-24, BridgeLab proved dry-run/apply/verify/promote/rollback for player `5406`, including quest reward-panel visibility and optional native player-item cleanup.
- managed item reward proof is `WORKING` at DB/runtime-reload and live-effect level: `control/examples/items/night_watchers_lens.json` publishes item `910006` (`Night Watcher's Lens`) from a reserved WM item slot, and BridgeLab quest `910024` (`Bounty: Nightbane Dark Runner - Lens`) now rewards it through `RewardItem1=910006`, `RewardAmount1=1`, plus the existing 12 silver; the current lens effect uses visible aura spell `132` as the wearer marker, then `mod-wm-spells` gives player weapon auto-attacks and wand auto-repeat shots a 10% chance to apply or refresh a visible 10-second target debuff (`770`), halves the attack-outcome defenses covered by the current hook, doubles attack crit chance in that hook, and doubles WM-owned proc hooks such as Bonebound Alpha Echo while the visible debuff is active. On 2026-04-24, user proof confirmed the wearer aura/debuff path after BridgeLab `WmSpells.PlayerGuidAllowList` was fixed to include `5406`.
- random enchant consumable lane is `PARTIAL`: repo code keeps native action `player_random_enchant_item` as a policy-disabled typed primitive, but the player-facing flow is now item `910007` (`Unstable Enchanting Vellum`). The opt-in scoped kill hook behind `WM_RANDOM_ENCHANT_ON_KILL_ENABLED=1` deterministically rolls 2-3% kill events and submits `player_add_item` for the consumable instead of mutating gear directly. Using the consumable opens a native item gossip menu for eligible equipped weapons/armor, applies random enchant IDs from `item_enchantment_random_tiers`, gives existing enchant slots a default 15% preserve chance, persists inventory, and consumes one vellum only after an enchant/preserve result. Repo tests, BridgeLab native build, and lab SQL apply are `WORKING`; deploy/restart/use proof is pending because player `5406` was online during implementation.
- managed item rollback is `WORKING` at repo-test and BridgeLab live-proof level through `python -m wm.items.rollback`: it reads latest item rollback snapshots, deletes never-existing managed rows back to `staged`, restores previous `item_template` rows back to `active`, and reports structured `snapshot` / `mysql` issues. The content playcycle rollback restored item `910006` from snapshot `110`, wrote rollback publish log `272`, reloaded `item_template` through SOAP, and reported `WORKING`.
- spell pipeline V1 is `WORKING` at repo-test level: `python -m wm.spells.publish`, `python -m wm.spells.live_publish`, and `python -m wm.spells.rollback` now cover helper/proc-table preflight, runtime-sync wrapper flow, rollback snapshots, clear-vs-restore reserved-slot status, structured schema/snapshot/MySQL failures, named-shell collision rejection, and the bundled example now lives in managed spell slot `947000`; `wm.content.workbench` now records active/revoked `wm_spell_grant` rows for WM-owned spell learns and revokes, `publish-spell` will not continue into runtime learn after a failed publish, visible spell slots resolve runtime learn through `base_visible_spell_id`, apply-mode learn/unlearn verifies the expected `character_spell` row after a `.saveall` flush plus short retry window, `wm.spells.rollback` revokes still-active `wm_spell_grant` rows for the rolled-back spell when the table exists, and `wm.reserved.db_allocator` now ignores stale shell-band / exact-claim spell rows when allocating managed spell slots; BridgeLab live publish/learn/rollback proof remains `PARTIAL` because managed slot `947000+` is still not itself a server-known learnable spell identity
- repo-owned bootstrap and bridge-lab workflows
- BridgeLab solo dungeon runtime tuning is `PARTIAL`: `scripts/bridge_lab/Configure-BridgeLabRuntime.ps1` now writes AutoBalance/SoloLFG/DynamicLootRates settings for solo 5-player dungeons as 75% original 5-player HP, 50% damage, 75% XP, and 2x dungeon loot. The active BridgeLab config files were restaged before the 2026-04-24 worldserver restart to pid `8312`; live behavior is unproven until an in-game dungeon check.

### Live sensing and execution

- `addon_log` is the currently proven live perception path
- `native_bridge` exists and can emit canonical WM events
- `wm.events.watch` now survives per-iteration spine failures, flushes summary/error lines for automation logs instead of exiting silently, and keeps native bridge projection/evaluation scoped to the requested `--player-guid`; native bridge cursor state is now per player (`last_seen:player:<guid>`) with a legacy `last_seen` fallback for migration.
- reactive bounty installs now have a repo-owned fast path through `control/examples/reactive_bounties/` and `scripts/bridge_lab/Install-BridgeLabReactiveBounty.ps1`
- reactive bounty templates are the supported fast operator lane; implicit auto-bounty creation from arbitrary kills is disabled by default and only available behind explicit opt-in config
- `scripts/bridge_lab/Start-BridgeLabAutoBounty.ps1` is the repo-owned BridgeLab operator lane for the opt-in dynamic path: it stops the current native watcher, deactivates existing `reactive_bounty:*` rules for the scoped player by default, then relaunches `wm.events.watch` with `WM_REACTIVE_AUTO_BOUNTY_ENABLED=1`, `--arm-from-end`, `--batch-size 1`, `WM_REACTIVE_AUTO_BOUNTY_MAX_EVENT_AGE_SECONDS=3600`, and `WM_REACTIVE_AUTO_BOUNTY_SINGLE_OPEN_PER_PLAYER=1`.
- when `WM_REACTIVE_AUTO_BOUNTY_ENABLED=1`, the opt-in auto-bounty lane now binds dynamically to the exact observed creature entry after 4 consecutive same-entry kills within 300 seconds and picks the turn-in NPC from the current zone by faction-preferred quest-tie weight instead of a hardcoded target table; the streak evaluator fetches the newest bounded event slice before replaying it chronologically, so long event-log history no longer hides fresh kills, consecutive streaks fire on threshold multiples like 4/8/12 rather than only exactly 4, stale queued kills do not create new dynamic bounty rules, and one unresolved dynamic auto-bounty blocks creation of another for the same player until it is completed/rewarded/cleared.
- dynamic auto-bounty grant proof is `WORKING` for the current trigger/grant leg on BridgeLab: on 2026-04-24, Jecia's `Mottled Scytheclaw` kills (`creature:1022`) produced rule `reactive_bounty:auto:zone:11:subject:1022`, quest `910076`, native `quest_add` request `147` with trigger-scoped idempotency key `...native_bridge:27975...`, and native bridge `quest/granted` event `28031`; `character_queststatus` for player `5406` contains quest `910076`.
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
- custom ID ledger is `WORKING` at repo-contract level: `data/specs/custom_id_registry.json` is now the exact-claim authority, `docs/CUSTOM_ID_LEDGER.md` is the operator-facing mirror, and stale spell collision between shell `940000` and the managed spell example was removed by moving the managed spell lane to `947000+`
- client patch workspace and local MPQ build lane are `WORKING` at repo/artifact level: `python -m wm.spells.client_patch build` materializes `DBFilesClient\Spell.dbc` plus `DBFilesClient\SkillLineAbility.dbc`, packages them with repo-local Ladik MPQ Editor from `.wm-bootstrap\tools\mpqeditor`, verifies extraction, and can install `patch-z.mpq` to the WoW client `Data` directory when the client is closed
- server Spell.dbc materialization lane is `WORKING` for named compatibility shells: `python -m wm.spells.server_dbc materialize` plus `scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1` now clone server-proof seed rows into `940000`, `940001`, `944000`, and `945000`, and the 2026-04-17 BridgeLab proof staged those ids into `D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc`
- server Spell.dbc cast-shape staging is `WORKING` for the visible `940001` test lane: `Stage-BridgeLabServerSpellDbc.ps1 -SeedProfile castable -SpellId 940001` stages a Raise-Dead-style effect/target row plus presentation fields, and the staged DBC now reports `effect=(28,0,0)`, `targetA=(32,0,0)`, `range=1`, `cast=14`, `icon=221`, `mana=180`
- `mod-wm-spells` exists as the stable native spell-behavior runtime
- lab debug invoke exists for shell-bound behavior testing without a visible client shell
- generic shell-bank V2 is `WORKING` at repo-contract level: pinned compatibility shells remain on `940000`, `940001`, `944000`, and `945000`, while generic cast-shape families now occupy `946000-946999` as five 100-slot families with 100-id reserve gaps
- shell-backed server learn/revoke proof is `WORKING` for named shell `940001` on BridgeLab after the server DBC stage: `wm.content.workbench grant-shell --shell-key bonebound_twins_v1` created `character_spell(5406, 940001)` and an active `wm_spell_grant` row, and `ungrant-shell` removed the character-spell row and revoked that grant; this is server truth only, not final client spellbook/action-bar proof
- Bonebound Alpha native lane is `PARTIAL` for the visible bleed fix on shell `940001`: bridge-lab SQL binds `summon_bonebound_alpha_v3`, `spawn_omega=false`, WM stock-carrier use of `697` / `49126` remains retired while normal Summon Voidwalker `697` is preserved, and the repo/native code now applies Alpha bleed only from the Alpha melee hook with visible target aura `772` plus WM-owned physical ticks. BridgeLab compile passed on 2026-04-24 with `Build-BridgeLabIncremental.ps1 -NoStageRuntime`; the SQL migration was applied and worldserver restarted to pid `8312`, but in-game proof is still pending.
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
- full auto-bounty playcycle proof is still `PARTIAL`: native bridge perception, dynamic rule creation, and fresh native quest grant are proven live for `Mottled Scytheclaw` -> quest `910076`, but complete -> reward -> suppress -> cooldown -> regrant still needs a clean armed-watcher proof.
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
