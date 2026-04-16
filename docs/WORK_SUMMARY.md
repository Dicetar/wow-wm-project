Status: PARTIAL
Last verified: 2026-04-17
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
- `wm.events.watch` now keeps running across iteration-level spine failures and flushes automation-facing summary/error output promptly
- deterministic planning and execution against the existing publish pipeline

### Reactive quest pipeline

- reusable reactive bounty rule storage
- repo-owned reactive bounty templates under `control/examples/reactive_bounties/`
- one-command bridge-lab install wrapper in `scripts/bridge_lab/Install-BridgeLabReactiveBounty.ps1`
- implicit auto-bounty creation from arbitrary kills is now disabled by default; explicit JSON templates are the fast publish/install lane
- when explicitly enabled, the implicit auto-bounty lane now watches for 4 consecutive kills of the same creature entry within 300 seconds, publishes a quest bound to that exact observed entry, and picks the turn-in NPC from the player's current zone by faction-preferred quest-tie weight
- bundled reactive bounty templates can now be listed with `python -m wm.reactive.install_bounty --list-templates --summary` and installed by key with `--template-key`, so operators do not need to copy full JSON paths for common test bounties
- reactive bounty installs now default to a fresh reserved quest slot unless an explicit `quest_id` is pinned on purpose
- reactive bounty dry-runs can preview a free reserved slot safely and keep apply-mode slot staging strict
- opt-in dynamic 4-in-a-row bounty evaluation now fetches the newest bounded event-log slice before replaying it chronologically, fixing the long-running-lab bug where `ORDER BY EventID ASC LIMIT 400` made the watcher evaluate stale history instead of fresh kills; consecutive streaks now fire on threshold multiples like 4/8/12, not just exactly 4, so a missed pre-arm crossing does not permanently block the current streak
- shared bounty drafts and publish SQL now carry richer reward fields:
  - item reward
  - spell reward / display spell
  - XP difficulty
  - reputation reward slots mapped to the current `quest_template` schema
- BridgeLab bounty reward proof is `WORKING` at DB/runtime-reload level for fresh quest slot `910024`: managed item slot `910006` (`Night Watcher's Lens`) is published from `control/examples/items/night_watchers_lens.json`, rewards a cloth head item with Intellect, Stamina, spell power, visible wearer aura spell `132`, and a native 10% direct-hit target debuff proc gated by equipped item plus visible aura, and is wired into `RewardItem1` / `RewardAmount1` alongside the old 12 silver
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
- Primitive Pack 1 is now `WORKING` in BridgeLab behind policy-disabled defaults: `player_apply_aura`, `player_remove_aura`, `player_restore_health_power`, `player_add_item`, `player_add_money`, `player_add_reputation`, `creature_spawn`, `creature_despawn`, `creature_say`, and `creature_emote` are implemented in `mod-wm-bridge`, WM-owned spawned creatures record `LiveGUIDLow` in `wm_bridge_world_object` for guarded follow-up actions, and the live proof on 2026-04-16 for player `5406` reached native requests `54-72` `done`
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
- bundled Primitive Pack 1 scenes now exist for `field_medic_pulse`, `bonebound_battle_cry`, and `summon_marker`, so operators can exercise ordered native action sequences without creating a second execution engine
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
- summon/spell platform status is documented separately in `docs/SUMMON_SPELL_PLATFORM_STATUS.md`, including retired stock-carrier paths and the current shell-bank direction
- Bonebound Alpha v3 repo/native status is `WORKING` for focused repo tests, native build, bridge-lab SQL binding, and worldserver restart on shell `940001`: the live behavior row now uses `summon_bonebound_alpha_v3`, `spawn_omega=false`, Alpha Gorehowl visual item `28773`, low physical bleed ticks through the legacy `shadow_dot_*` config keys, and a 7.5% Alpha echo proc path
- Bonebound Alpha fast release submitter is `WORKING` as `python -m wm.spells.summon_release`; it skips proof preflights and submits shell `940001` directly for repeated operator use, now defaulting to `summon_bonebound_alpha_v3`
- Bonebound Alpha echo hardening is `WORKING` at repo/build/SQL level: echo procs now use WM creature template `920101`, copy Alpha final health/power/damage after stat recalculation, and randomize follow slots around the player
- Bonebound Alpha echo mount/dismount restore is `PARTIAL`: repo/static tests cover preserving missing Echo state during player mount temporary-unsummon, preventing player maintenance from erasing that state while the main pet is absent, and respawning it after the Bonebound pet returns; the rebuilt worldserver was deployed to BridgeLab pid `31208`, and live in-game proof is still pending
- Bonebound Alpha live release-lane smoke is `WORKING`: the 2026-04-16 build and SQL applied successfully, worldserver restarted, player `5406` came online, release request `11` completed on shell `940001`, and user validation accepted the low bleed / echo behavior; exact combat-log values were not captured
- Bonebound Omega parity is `BROKEN` and retired for the release lane: live evidence showed Alpha damage around `120`, Omega damage around `9`, and Omega mana around `20`; TempSummon field-copy hardening did not produce reliable combat parity
- persistent WM combat proficiency repo and live path are `WORKING` for player `5406`: high-ID `skillraceclassinfo_dbc` / `skilllineability_dbc` override SQL makes Shield `433`, Leather `414`, and Dual Wield skill `118` login-valid, `python -m wm.spells.shield_proficiency --player-guid 5406 --mode apply --summary` grants only explicit player GUIDs, Dual Wield persists through spell `674`, `mod-wm-spells` syncs the volatile Dual Wield flag only for active `combat_proficiency` grants, offhand one-handed sword equip works, Dual Wield displays in the spellbook, and `passive_intellect_block_v1` shell `944000` remains separate as an intellect/spellpower block-rating passive
- Bonebound Alpha visible spell lifecycle remains `PARTIAL` until the client shell patch and spellbook/action-bar path are proven end-to-end
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
- item reward publishing is proven for DB rows and runtime reload, but `Night Watcher's Lens` client/equip/passive behavior remains `PARTIAL` until the live quest turn-in, equip, and visible target-debuff refresh behavior are confirmed; if stale after reload, restart worldserver before changing item schema again
- hidden item effects are not acceptable without player-facing indication; use visible auras/buffs/debuffs/messages/tooltips, and do not use unrelated stock spells as flavor carriers
- generic stock/core proc chance doubling is not proven; the current lens doubles WM-owned proc hooks that explicitly opt in, including Bonebound Alpha Echo
- visible quest reward iteration must use fresh reserved quest slots after a player has accepted/rewarded an older test ID; `910021` stayed visually stale after mutation, so `910024` replaced it for the lens reward proof
- most native mutation action kinds are intentionally disabled/not implemented until their C++ bodies pass lab tests
- Questie needs a tiny compat shim for WM custom quest ids because upstream Questie-335 does not know repo-owned quest ids like `910000`
- Phase 1 native bounty parity remains `PARTIAL` until the full in-game loop is rerun end-to-end on the current bridge lab
- dynamic per-trigger template watching remains experimental; the keepable pieces are being folded into the shared reactive/publish path instead of promoting a second watcher architecture
- auto-generated active bounty rules are not the default operator model; old lab rows should be treated as dirty state and replaced by explicit `reactive_bounty:template:*` installs from JSON path or bundled `--template-key`, unless you are intentionally validating the opt-in dynamic 4-in-a-row auto-bounty lane
- the dynamic 4-in-a-row auto-bounty lane counts recorded kill events, not UI combat text. After the 2026-04-17 bridge patch, player-owned non-pet summons feed the same streak path. Do not reintroduce oldest-first bounded history scans; fetch newest first, replay chronologically for streak math, and preserve threshold-multiple triggering for long live streaks.
- subject recognition and memory remain `PARTIAL` at live/lab level until subject cards can be materialized automatically, seeded rows are proven against the lab DB, fresh native snapshots are consumed, and full proposal-gate previews exist
- combat proficiencies must not be added through `playercreateinfo_skills`, `playercreateinfo_spell_custom`, `mod_learnspells`, playerbot factory code, runtime `SetSkill` reapply, or class/equip override hooks; the only runtime exception is Dual Wield materializing `CanDualWield()` from persistent spell `674` behind explicit skill `118` validity and an explicit `combat_proficiency` grant
- Dual Wield is one-handed offhand capability; two-handed offhand weapons require Titan Grip and must be treated as a separate feature
- Omega stat tuning by TempSummon field copy is retired. Do not claim a second combat companion is `WORKING` from target-frame fields alone; prove health, mana, and damage output or use a true pet/guardian/hook-backed design.
- Alpha echo template/name/health bugs must be fixed through server truth: use WM creature template `920101` and write final copied Alpha fields after stat recalculation, not before.

## Recommended workflow

1. clone repo
2. run `setup-wm.bat`
3. run `build-wm.bat`
4. edit `.wm-bootstrap\run\configs\worldserver.conf` and `.wm-bootstrap\run\configs\authserver.conf`
5. apply `sql\bootstrap\wm_bootstrap.sql`
6. use `python -m wm.control.inspect/new/validate/apply` for manual control tests
7. continue WM feature work from the repo, not from machine-local rebuild leftovers

For native bridge action work, use `setup-bridge-lab.bat` and `build-bridge-lab.bat` once, then use `incremental-bridge-lab.bat` for normal C++ edits. Runtime tests should start `start-bridge-lab-mysql.bat`, run `configure-bridge-lab.bat`, and prove `debug_ping`/`debug_echo`/`debug_fail` before promoting anything back to a working realm.
