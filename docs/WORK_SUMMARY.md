Status: PARTIAL
Last verified: 2026-04-24
Verified by: Codex
Doc type: handoff

# Work Summary

For the best current entrypoint, start with:

- [Documentation Index](README_OPERATIONS_INDEX.md)
- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)

This repository is now a real WM platform baseline, not just an idea pile.

## What was built

### Event spine

- canonical WM event log, cursor storage, cooldowns, and reaction history
- inspect, preview, run, and watch flows
- `wm.events.watch` now keeps running across iteration-level spine failures, flushes automation-facing summary/error output promptly, scopes native bridge projection/evaluation to the requested player, and uses per-player native bridge cursors (`last_seen:player:<guid>`) with a one-time legacy cursor fallback
- deterministic planning and execution against the existing publish pipeline

### Reactive quest pipeline

- reusable reactive bounty rule storage
- repo-owned reactive bounty templates under `control/examples/reactive_bounties/`
- one-command bridge-lab install wrapper in `scripts/bridge_lab/Install-BridgeLabReactiveBounty.ps1`
- implicit auto-bounty creation from arbitrary kills is now disabled by default; explicit JSON templates are the fast publish/install lane
- `scripts/bridge_lab/Start-BridgeLabAutoBounty.ps1` is now the repo-owned BridgeLab start lane for the dynamic path: it stops the current native watcher, clears existing `reactive_bounty:*` rows for the scoped player by default, then restarts `wm.events.watch` with auto-bounty enabled, armed from the end, one-event apply batches, a one-hour dynamic-rule freshness gate, and one-open-dynamic-bounty-per-player gating
- when explicitly enabled, the implicit auto-bounty lane now watches for 4 consecutive kills of the same creature entry within 300 seconds, publishes a quest bound to that exact observed entry, picks the turn-in NPC from the player's current zone by faction-preferred quest-tie weight, refuses to create dynamic bounty rules from stale queued kills, and refuses to stack a second unresolved dynamic bounty on the same player
- dynamic auto-bounties now also pick one random stock equipment reward from the live loot-backed item pool for the scoped player when no explicit reward override is present, constrained by player level window, class mask, and persistent armor/shield proficiency exceptions from `character_skills`; the old `Box of Supplies` path remains the fallback when no suitable equipment candidate exists
- bundled reactive bounty templates can now be listed with `python -m wm.reactive.install_bounty --list-templates --summary` and installed by key with `--template-key`, so operators do not need to copy full JSON paths for common test bounties
- reactive bounty installs now default to a fresh reserved quest slot unless an explicit `quest_id` is pinned on purpose
- reactive bounty dry-runs can preview a free reserved slot safely and keep apply-mode slot staging strict
- opt-in dynamic 4-in-a-row bounty evaluation now fetches the newest bounded event-log slice before replaying it chronologically, fixing the long-running-lab bug where `ORDER BY EventID ASC LIMIT 400` made the watcher evaluate stale history instead of fresh kills; consecutive streaks now fire on threshold multiples like 4/8/12, not just exactly 4, so a missed pre-arm crossing does not permanently block the current streak
- dynamic auto-bounty trigger/grant proof is `WORKING` for the current BridgeLab grant leg: Jecia's 2026-04-24 `Mottled Scytheclaw` (`creature:1022`) streak created quest `910076`, native `quest_add` request `147` reached `done`, and native bridge emitted `quest/granted` event `28031`; full turn-in/cooldown/regrant proof remains open
- native `quest_add` requests from reactive bounty grants now include the trigger identity in the idempotency key, so a later same-rule bounty burst submits a fresh native request instead of reusing the first completed request forever
- bounty drafts now centralize repeatable quest marking (`SpecialFlags |= 1`) so repeated WM bounty turn-ins are a template property instead of a per-installer accident; live quest `910024` was verified with repeatable addon state and the BridgeLab quest cache was reloaded on 2026-04-17
- default bounty rewards are now `WORKING` at repo-test level: if a draft/template does not pin its own reward, the shared bounty builder emits level-scaled money `max(175, 4 * level^2)`, `RewardXPDifficulty` `4` below quest level `25` and `5` at `25+`, and stock supply item `6827` (`Box of Supplies`)
- shared bounty drafts and publish SQL now carry richer reward fields:
  - item reward
  - spell reward / display spell
  - XP difficulty
  - reputation reward slots mapped to the current `quest_template` schema
- BridgeLab bounty reward proof is `WORKING` at DB/runtime-reload and live-effect level: managed item slot `910006` (`Night Watcher's Lens`) is published from `control/examples/items/night_watchers_lens.json`, rewards a cloth head item with Intellect, Stamina, spell power, visible wearer aura spell `132`, and a native 10% weapon-auto/wand-auto target debuff proc gated by equipped item plus visible aura. The 2026-04-24 BridgeLab retest passed after `WmSpells.PlayerGuidAllowList` was fixed to include `5406`.
- content playcycle wrapper is `WORKING` at repo-test and BridgeLab live-proof level: `python -m wm.content.playcycle item-effect` accepts strict `wm.content_playcycle.item_effect.v1` scenarios from `control/examples/content_playcycles/`, composes managed item publish, runtime-sync summary, native `player_add_item`, fresh reactive bounty slot promotion, verify checks, item rollback, and optional native cleanup, and rejects freeform SQL/GM/shell/LLM mutation fields. The 2026-04-24 Night Watcher's Lens proof covered dry-run/apply/verify/promote/reward-panel/rollback/cleanup for player `5406`.
- managed item rollback is `WORKING` at repo-test and BridgeLab live-proof level through `python -m wm.items.rollback`: latest item snapshots can dry-run, apply delete-slot rollback, apply previous-row restore, update reserved slot state, and return structured failures for missing/malformed snapshots or MySQL errors; BridgeLab rollback restored item `910006` from snapshot `110` and wrote rollback publish log `272`
- spell pipeline V1 is now `WORKING` at repo-test level: `python -m wm.spells.publish` discovers live `spell_linked_spell` / `spell_proc` columns, snapshots current helper/proc rows, builds deterministic publish SQL, rejects named-shell spell-id collisions, and the bundled managed example now lives at `947000`; `python -m wm.spells.live_publish` mirrors the item live wrapper for spell-side DB publish plus optional runtime sync; `python -m wm.spells.rollback` restores or clears those rows, keeps reserved spell slots `active` when previous rows existed, returns them to `staged` when the slot was previously empty, revokes still-active `wm_spell_grant` rows for the rolled-back spell when the table exists, and fails explicitly on malformed snapshots or unsupported live restore schemas; `wm.content.workbench` records active/revoked `wm_spell_grant` rows for WM-owned spell learns and revokes, blocks `publish-spell` runtime learn when publish did not succeed, resolves visible-slot runtime learn through `base_visible_spell_id`, verifies `character_spell` state after apply using `.saveall` plus a short retry window, and `wm.reserved.db_allocator` also guards managed spell allocation against stale shell-band/exact-claim rows; BridgeLab helper scripts now exist for publish, grant, rollback, and server Spell.dbc staging; managed-slot live proof is still `PARTIAL`, because `947000+` is not itself a server-known learnable spell identity
- named shell server-truth proof is now `WORKING` on BridgeLab: `python -m wm.spells.server_dbc materialize` plus `scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1` stage `940000`, `940001`, `944000`, and `945000` into the rebuild `Spell.dbc`, `grant-shell` on `940001` creates `character_spell(5406, 940001)` and an active `wm_spell_grant`, and `ungrant-shell` removes the row and revokes the grant
- visible client-shell packaging is now `WORKING` at repo/artifact and spellbook-presentation level: `python -m wm.spells.client_patch build` materializes `DBFilesClient\Spell.dbc` plus `DBFilesClient\SkillLineAbility.dbc`, packages them with repo-local Ladik MPQ Editor, and verifies extraction. The refreshed 2026-04-17 package sets `940001` to icon `221`, cast time index `14`, mana cost `180`, Summon Voidwalker visual `4054`, and a Warlock/Demonology skill-line mapping cloned from Summon Voidwalker. The package is installed, BridgeLab staged matching server DBC fields with `-SeedProfile castable`, worldserver restarted on pid `8580`, `character_spell(5406,940001)` is persistent, active `wm_spell_grant` row `5` exists, and user proof showed the visible spell in the Demon tab; refreshed animation/action-bar/relog lifecycle proof is still `PARTIAL`
- direct quest grant through SOAP
- runtime quest-state polling from the characters DB
- suppression while a reactive quest is active, complete-but-not-turned-in, or cooling down after reward
- repo automated coverage now proves the rewarded-state reopen path after the post-reward cooldown expires
- repo automated coverage now also proves one native-bridge spine pass end-to-end with runtime reconciliation recorded separately from the grant action

### Hidden addon bridge

- `WMBridge` addon under `wow_addons/WMBridge`
- hidden addon-message transport
- addon-log adapter reading AzerothCore addon-message logging as the current working live source
- `combat_log` retained only as fallback/debug

### Native bridge rollout

- repo-owned `mod-wm-bridge` native module
- append-only `wm_bridge_event` raw event table
- `native_bridge` WM adapter maps raw rows into canonical events
- module is inert by default through empty `WmBridge.PlayerGuidAllowList`
- WM helper can update the allowlist and reload config without a worldserver restart
- DB-backed player scope through `wm_bridge_player_scope` can be enabled for live allowlist control after bootstrap SQL is present
- native action bus foundation through `wm_bridge_action_request`, `wm_bridge_action_policy`, and `wm_bridge_runtime_status`
- broad native action vocabulary is registered, with `debug_ping`, `debug_echo`, `debug_fail`, `context_snapshot_request`, `world_announce_to_player`, and `quest_add` proven in the first safe slice
- Primitive Pack 1 is now `WORKING` in BridgeLab behind policy-disabled defaults: `player_apply_aura`, `player_remove_aura`, `player_restore_health_power`, `player_add_item`, `player_add_money`, `player_add_reputation`, `creature_spawn`, `creature_despawn`, `creature_say`, and `creature_emote` are implemented in `mod-wm-bridge`, WM-owned spawned creatures record `LiveGUIDLow` in `wm_bridge_world_object` for guarded follow-up actions, and the live proof on 2026-04-16 for player `5406` reached native requests `54-72` `done`; `player_add_item` now persists inventory immediately after grant, with repo tests and BridgeLab build/deploy proof after request `144` exposed DB flush lag
- Primitive Pack 2 is `WORKING` in BridgeLab behind policy-disabled defaults: `player_cast_spell`, `player_set_display_id`, `creature_cast_spell`, `creature_set_display_id`, and `creature_set_scale` have typed native bodies, payload contracts, disabled policy seed SQL, repo tests, a successful BridgeLab native build, and live control/audit proof through `arcane_marker_demo` requests `84-89` `done`
- native `player_remove_item` is now `WORKING` as a scoped, policy-disabled cleanup primitive at repo/static-test and BridgeLab live level. It requires explicit `item_id` and positive `count`, rejects non-reserved item entries unless `admin_override` is present, persists inventory after `DestroyItemCount`, and requests `139` / `142` removed managed item `910006` from player `5406`; follow-up request `143` confirmed `available_count=0`, and it is exposed to the content playcycle rollback path for optional player inventory cleanup
- random enchant consumable lane is `PARTIAL`: the low-level native `player_random_enchant_item` primitive remains policy-disabled, but the player-facing path now grants item `910007` (`Unstable Enchanting Vellum`) from selected scoped kill rolls and lets the player right-click it to choose an eligible equipped item. The item script applies random enchant IDs from `item_enchantment_random_tiers`, defaults to a guaranteed first enchant, and gives existing enchant slots a 15% preserve chance instead of always overwriting. Repo tests, BridgeLab native build, and lab SQL apply are `WORKING`; deploy/restart/use proof is pending because player `5406` was online during implementation.
- successful native `quest_add` now emits a native `quest/granted` bridge event so perception stays aligned with mutation
- native `quest_add` now mirrors GM `.quest add` sanity checks for WM force grants: it rejects item-start quests and already-active quests, but does not reuse `player->CanTakeQuest()`, because that was stricter than the existing SOAP/GM lane and broke native parity for repeatable WM bounty grants
- player-owned non-pet summon kill attribution is now `WORKING` at repo and BridgeLab event-log level: `mod-wm-bridge` adds a guarded `OnUnitDeath` emitter for player-owned killers that are neither the player nor a real pet/totem, so Echo/guardian/temp-summon kills join the same native watcher path without duplicating Alpha pet kills
- `quest_grant` remains the public WM action, but now prefers native bridge when the player/policy/config path is ready and falls back to SOAP otherwise
- historical bridge-lab evidence from April 11, 2026 shows `Bounty: Kobold Vermin` running through native `quest_granted`, native `quest_completed`, native `quest_rewarded`, and the WM post-reward cooldown row for player `5406`
- April 13, 2026 smoke reran successfully against `D:\WOW\WM_BridgeLab` for `debug_ping` and `wm.events.watch --adapter native_bridge --arm-from-end`, but the full live bounty loop was not rerun because player `5406` was offline

### Control contract workbench

- repo-owned `control/` registry for events, actions, recipes, policies, examples, schemas, and runtime checks
- `native_bridge_action` contract lets humans and later LLMs submit one fixed native action kind through the same proposal gates
- Pydantic `ControlProposal` contract is shared by manual proposals and future LLM proposals
- manual inspect/new/validate/apply commands exercise the same coordinator path as LLM proposals
- live apply is one registered action per proposal, with player scope, source event checks, dry-run, idempotency, and audit state
- `python -m wm.control.audit` can inspect `wm_control_proposal` rows by idempotency key, source event, or player and summarize source event, validation, dry-run/apply state, and native request ids/statuses when present
- `python -m wm.control.apply --summary` now prints idempotency, audit/apply status, and native request id/status for `quest_grant` and generic `native_bridge_action` execution results
- experimental scene play now exists as `python -m wm.control.scene_play`; it loads bundled control scenes from `control/scenes/`, rejects unknown or unimplemented native action kinds up front, and summary output now includes per-step native request refs when execution produced them
- bundled Primitive Pack scenes now exist for `field_medic_pulse`, `bonebound_battle_cry`, `summon_marker`, and `arcane_marker_demo`, so operators can exercise ordered native action sequences without creating a second execution engine
- BridgeLab live proof for the bundled scenes is `WORKING`: `field_medic_pulse` completed through requests `54-56`, `summon_marker` through `65-68`, and `bonebound_battle_cry` through `61-64`; control audit shows proposal -> native request -> result linkage for those scene steps
- the `creature_spawn` result payload race is fixed: native code now inserts the WM-owned row synchronously before the immediate lookup, so live result JSON returns the real `object_id` instead of `0`
- control proposal loading accepts UTF-8 BOM JSON, because Windows PowerShell `Set-Content -Encoding UTF8` can emit a BOM and should not break operator-created proposal files
- direct apply policy now rejects stale non-admin source events through `max_source_event_age_seconds=600`; repo tests cover stale-event, wrong-player, and duplicate-idempotency rejection visibility
- LLM-authored live apply is blocked unless `WM_LLM_DIRECT_APPLY=1`

### Runtime DLL guard

- build now records a `runtime-dlls.lock.json` hash inventory for MySQL/OpenSSL runtime DLLs
- rebuilt launcher can fail fast before `authserver.exe` or `worldserver.exe` starts with mismatched DLLs
- this directly targets the previous `legacy.dll` / `libcrypto` entry-point breakage

### Shared internal refs

- typed refs for players, creatures, NPCs, quests, items, and spells
- internal schemas now carry structured refs instead of leaking anonymous integers everywhere

### Subject recognition

- initial `wm.subjects` slice maps existing target profiles into WM subject cards
- `python -m wm.subjects.inspect` can inspect a creature entry from static lookup JSON or the live runtime resolver
- `SubjectJournalReader` now checks for WM journal tables, loads subject definitions/enrichments/counters/raw events when present, and can merge resolver-built subject cards when DB subject rows or live DB access are absent
- `python -m wm.journal.inspect` can inspect one player and one creature subject and render the loaded journal status/counters/events
- prompt demo callers now pass the resolved target profile into the journal reader, preventing missing WM subject rows from collapsing the journal package to `null`
- deterministic lab seed `sql/dev/seed_journal_context_5406_world.sql` now upserts one creature subject for entry `46`, resets only player `5406`'s seeded rows for that subject, and inserts one `wm_event_log` smoke event
- `wm.context_pack.v1` assembly now packages source event, character state, target profile, subject card, journal summary, recent events, related subject events, reactive quest runtime, control recipe/policy metadata, and latest native snapshot rows when present
- `python -m wm.context.snapshot` and `scripts/bridge_lab/Request-BridgeLabContextSnapshot.ps1` provide a bounded one-shot request/wait path for native context snapshot proof
- repo status is `WORKING` for resolver, journal reader/inspect, context pack assembly, and bounded snapshot command tests
- bridge-lab DB status is `WORKING`: on 2026-04-14, `wm.journal.inspect` and event-backed `wm.context.builder` were proven against `127.0.0.1:33307` using `sql/dev/seed_journal_context_5406_world.sql`
- native snapshot status is `WORKING` for one-shot bridge-lab proof: on 2026-04-15, scoped player `5406` was online, native request `31` reached `done`, snapshot row `1` was written, duplicate idempotency lookup returned the existing snapshot, and event-backed context pack output included `native_snapshot: true`

### Rebuilt latest-source baseline

- latest Playerbot-branch AzerothCore source reconstruction
- large module set cloned from upstream/community repos
- compatibility overlay for loader/API drift
- launcher/rebuild helpers for native WM module work
- repo-owned lab launcher and realmlist sync helpers for `D:\WOW\WM_BridgeLab`
- isolated bridge lab wrappers keep native rebuild experiments in `D:\WOW\WM_BridgeLab` instead of the working rebuild
- incremental bridge lab build/stage wrappers avoid full rebuilds after the first generated solution exists
- isolated lab MySQL can run from the copied lab data directory on port `33307`, keeping bridge queue tests off the working DB
- graceful-first lab worldserver restart helper falls back to force only if the process hangs
- bridge lab runtime configuration forces `WeatherVibe.Debug = 0` so weather debugging does not spam the client during WM tests
- bridge lab runtime configuration now stages solo 5-player dungeon tuning through AutoBalance, SoloLFG, and DynamicLootRates: 75% original 5-player HP, 50% damage, 75% XP, and 2x dungeon loot. The active BridgeLab config files were restaged before the 2026-04-24 worldserver restart to pid `8312`, so live behavior remains `PARTIAL` until an in-game dungeon check.
- summon/spell platform status is documented separately in `docs/SUMMON_SPELL_PLATFORM_STATUS.md`, including retired stock-carrier paths and the current shell-bank direction
- custom ID governance is `WORKING` at repo-contract level: `data/specs/custom_id_registry.json` now tracks exact custom claims, `data/specs/reserved_id_ranges.json` is coarse allocator policy only, managed spell slots moved to `947000-947999`, and the shell-bank contract no longer shares exact spell ids with managed spell examples
- generic shell-bank V2 is `WORKING` at repo-contract level: the patch workspace now preserves pinned compatibility shells while pre-seeding five cast-shape generic families in `946000-946999`
- Bonebound Alpha v3 visible bleed status is `PARTIAL`: repo/native code now applies Alpha bleed only from the Alpha melee hook, uses visible target aura spell `772` as the duration/status marker, keeps WM-owned physical bleed ticks with level/intellect scaling and no shadow spell-power scaling, and moves drafts/SQL from legacy `shadow_dot_*` keys to `bleed_*` while preserving legacy parsing. BridgeLab compile passed on 2026-04-24 with `Build-BridgeLabIncremental.ps1 -NoStageRuntime`; SQL migration and runtime restart to pid `8312` are done, and in-game proof remains pending.
- Bonebound Alpha fast release submitter is `WORKING` as `python -m wm.spells.summon_release`; it skips proof preflights and submits shell `940001` directly for repeated operator use, now defaulting to `summon_bonebound_alpha_v3`
- Bonebound Alpha stock-spell cleanup is `PARTIAL` after a structural fix: the earlier cleanup-only proof was overstated because stock `697` still summoned Alpha while Bonebound shared creature entry `1860`. The current repo/build/DB fix moves Alpha to WM creature entry `920100`, removes runtime stock entry/display fallback, keeps stock Voidwalker on `1860`, migrates Jecia's saved Alpha row off `1860`, preserves `character_spell(697)`, and keeps WM dispatch only on `940001`; fresh in-game proof is still pending
- Bonebound Alpha echo hardening is `WORKING` at repo/build/SQL level: echo procs now use WM creature template `920101`, copy Alpha final health/power/damage after stat recalculation, randomize follow slots around the player, and allow up to `40` active Echoes
- Bonebound Alpha echo mount/dismount restore is `PARTIAL`: repo/static tests cover preserving missing Echo state during player mount temporary-unsummon, preventing player maintenance from erasing that state while the main pet is absent, and respawning it after the Bonebound pet returns; the rebuilt worldserver was deployed to BridgeLab pid `31208`, and live in-game proof is still pending
- Bonebound Alpha earlier release-lane smoke proved summon/echo basics but did not prove visible bleed status; exact combat-log values and visible aura duration must be captured after the visible-bleed rebuild.
- Bonebound Omega parity is `BROKEN` and retired for the release lane: live evidence showed Alpha damage around `120`, Omega damage around `9`, and Omega mana around `20`; TempSummon field-copy hardening did not produce reliable combat parity
- persistent WM combat proficiency repo and live path are `WORKING` for player `5406`: high-ID `skillraceclassinfo_dbc` / `skilllineability_dbc` override SQL makes Shield `433`, Leather `414`, and Dual Wield skill `118` login-valid, `python -m wm.spells.shield_proficiency --player-guid 5406 --mode apply --summary` grants only explicit player GUIDs, Dual Wield persists through spell `674`, `mod-wm-spells` syncs the volatile Dual Wield flag only for active `combat_proficiency` grants, offhand one-handed sword equip works, Dual Wield displays in the spellbook, and `passive_intellect_block_v1` shell `944000` applies intellect/spellpower block rating after the 2026-04-24 `WmSpells.PlayerGuidAllowList` fix
- Bonebound Alpha visible spell lifecycle remains `PARTIAL` for caster animation/action-bar/relog proof, even though spellbook presentation is now user-proven
- Bonebound Alpha Demonology passive compatibility remains `PARTIAL`: Alpha now uses WM creature entry `920100`, cloned from the Voidwalker template and summoned by shell `940001`, so generic demon/pet/template-family mechanics may apply, but passives keyed specifically to stock spell `697`, stock creature entry `1860`, or stock CreatedBySpell behavior are unproven
- combat proficiency playerbot proof remains `PARTIAL`: Shield, Leather, and Dual Wield are confirmed live for player `5406`, but playerbot maintenance is still unchecked for no inheritance
- control-native convergence live proof is `WORKING` for the current V1 scope: BridgeLab proved control-driven `debug_ping` through `wm.control.validate/apply/audit` with native request `36` reaching `done`, and the fresh source-event bounty grant rerun on 2026-04-16 reached event `1599` -> proposal `43` -> native `quest_add` request `74` `done` -> `quest_grant_issued` event `1601`, while native bridge event `26505` recorded `quest/granted` for quest `910020`; GM `.quest status 910020 Jecia` reported `Incomplete`, so the live quest state is proven even though immediate `character_queststatus` reads stayed empty

### IPP cleanup work

- normalized the realm/client to `patch-S`
- kept the three required `Skill*.dbc` files active
- rolled back IPP optional SQL changes from the live world DB
- preserved mailbox unphasing through a repo-owned override SQL

## Current source of truth

For the portable workflow, the repo now owns:

- WM SQL bootstrap and overrides
- WM control contracts and proposal examples
- addon bridge source
- portable source/dependency manifest
- bootstrap/build scripts
- docs for setup and development

## Known limitations

- latest-source rebuilt realm is good for WM/native module development, but not guaranteed gameplay parity with the old repack
- some repack-specific/custom NPC or world content still drifts because newer module trees do not perfectly match the historical pack
- WeatherVibe is loaded but still needs meaningful zone/profile data
- optional IPP extras are intentionally excluded from the default portable bootstrap path
- item reward publishing is proven for DB rows, runtime reload, and live Lens aura/debuff behavior after the 2026-04-24 `mod-wm-spells` allowlist fix; if stale after reload, verify `WmSpells.PlayerGuidAllowList = "5406"` and restart worldserver before changing item schema again
- hidden item effects are not acceptable without player-facing indication; use visible auras/buffs/debuffs/messages/tooltips, gate the hidden server logic by that visible state/duration, and do not use unrelated stock spells as flavor carriers
- generic stock/core proc chance doubling is not proven; the current lens doubles attack crit chance in the available attack-outcome hook and WM-owned proc hooks that explicitly opt in, including Bonebound Alpha Echo
- visible quest reward iteration must use fresh reserved quest slots after a player has accepted/rewarded an older test ID; `910021` stayed visually stale after mutation, so `910024` replaced it for the lens reward proof
- most native mutation action kinds are intentionally disabled/not implemented until their C++ bodies pass lab tests
- Primitive Pack 2 is proven in BridgeLab but is still not a default gameplay surface; keep cast/display/scale policies disabled outside scoped operator tests.
- Questie needs a tiny compat shim for WM custom quest ids because upstream Questie-335 does not know repo-owned quest ids like `910000`
- Phase 1 native bounty parity remains `PARTIAL` until the full in-game loop is rerun end-to-end on the current bridge lab
- dynamic per-trigger template watching remains experimental; the keepable pieces are being folded into the shared reactive/publish path instead of promoting a second watcher architecture
- auto-generated active bounty rules are not the default operator model; old lab rows should be treated as dirty state and replaced by explicit `reactive_bounty:template:*` installs from JSON path or bundled `--template-key`, unless you are intentionally validating the opt-in dynamic 4-in-a-row auto-bounty lane
- if you are intentionally validating the dynamic 4-in-a-row lane, do not leave old `reactive_bounty:template:*` rows active for the same player; template/exact rules are matched before dynamic rule creation and can hijack the kill stream. Use `python -m wm.reactive.auto_bounty --player-guid <guid> --deactivate-existing-bounty-rules --summary` or `scripts/bridge_lab/Start-BridgeLabAutoBounty.ps1`.
- the dynamic 4-in-a-row auto-bounty lane counts recorded kill events, not UI combat text. After the 2026-04-17 bridge patch, player-owned non-pet summons feed the same streak path. Do not reintroduce oldest-first bounded history scans; fetch newest first, replay chronologically for streak math, and preserve threshold-multiple triggering for long live streaks. The streak key is the exact creature entry, not a shared family/name bucket, so mixed dungeon pulls will not trigger a single bounty unless the kills really are the same entry repeatedly.
- do not make BridgeLab WM scripts globally disable playerbot broadcasts as a permanent fix. WM event capture is scoped through WM bridge allowlists/player scope; playerbot broadcast crashes need targeted playerbot-path fixes or a clearly temporary runtime safety switch.
- subject recognition and memory remain `PARTIAL` at live/lab level until subject cards can be materialized automatically, seeded rows are proven against the lab DB, fresh native snapshots are consumed, and full proposal-gate previews exist
- combat proficiencies must not be added through `playercreateinfo_skills`, `playercreateinfo_spell_custom`, `mod_learnspells`, playerbot factory code, runtime `SetSkill` reapply, or class/equip override hooks; the only runtime exception is Dual Wield materializing `CanDualWield()` from persistent spell `674` behind explicit skill `118` validity and an explicit `combat_proficiency` grant
- Dual Wield is one-handed offhand capability; two-handed offhand weapons require Titan Grip and must be treated as a separate feature
- Omega stat tuning by TempSummon field copy is retired. Do not claim a second combat companion is `WORKING` from target-frame fields alone; prove health, mana, and damage output or use a true pet/guardian/hook-backed design.
- Alpha echo template/name/health bugs must be fixed through server truth: use WM creature template `920101` and write final copied Alpha fields after stat recalculation, not before.
- client-visible spell work has two separate gates: build/install the client MPQ and stage/restart the matching server DBC profile. A server-known spell row alone is not a client spellbook proof. A running WoW client locks `patch-z.mpq`, so close the client before reinstalling a refreshed MPQ.
- stock Summon Voidwalker `697` must stay stock. Do not clean it from `character_spell`, do not attach WM scripts to it, and do not use it as a permanent WM carrier.

## Recommended workflow

1. clone repo
2. run `setup-wm.bat`
3. run `build-wm.bat`
4. edit `.wm-bootstrap\run\configs\worldserver.conf` and `.wm-bootstrap\run\configs\authserver.conf`
5. apply `sql\bootstrap\wm_bootstrap.sql`
6. use `python -m wm.control.inspect/new/validate/apply` for manual control tests
7. continue WM feature work from the repo, not from machine-local rebuild leftovers

For native bridge action work, use `setup-bridge-lab.bat` and `build-bridge-lab.bat` once, then use `incremental-bridge-lab.bat` for normal C++ edits. Runtime tests should start `start-bridge-lab-mysql.bat`, run `configure-bridge-lab.bat`, and prove `debug_ping`/`debug_echo`/`debug_fail` before promoting anything back to a working realm.
