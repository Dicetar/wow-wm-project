Status: PARTIAL
Last verified: 2026-04-15
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
- reactive bounty installs now default to a fresh reserved quest slot unless an explicit `quest_id` is pinned on purpose
- reactive bounty dry-runs can preview a free reserved slot safely and keep apply-mode slot staging strict
- shared bounty drafts and publish SQL now carry richer reward fields:
  - item reward
  - spell reward / display spell
  - XP difficulty
  - reputation reward slots mapped to the current `quest_template` schema
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
- successful native `quest_add` now emits a native `quest/granted` bridge event so perception stays aligned with mutation
- `quest_grant` remains the public WM action, but now prefers native bridge when the player/policy/config path is ready and falls back to SOAP otherwise
- historical bridge-lab evidence from April 11, 2026 shows `Bounty: Kobold Vermin` running through native `quest_granted`, native `quest_completed`, native `quest_rewarded`, and the WM post-reward cooldown row for player `5406`
- April 13, 2026 smoke reran successfully against `D:\WOW\WM_BridgeLab` for `debug_ping` and `wm.events.watch --adapter native_bridge --arm-from-end`, but the full live bounty loop was not rerun because player `5406` was offline

### Control contract workbench

- repo-owned `control/` registry for events, actions, recipes, policies, examples, schemas, and runtime checks
- `native_bridge_action` contract lets humans and later LLMs submit one fixed native action kind through the same proposal gates
- Pydantic `ControlProposal` contract is shared by manual proposals and future LLM proposals
- manual inspect/new/validate/apply commands exercise the same coordinator path as LLM proposals
- live apply is one registered action per proposal, with player scope, source event checks, dry-run, idempotency, and audit state
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
- Bonebound Twins debug/native status is `WORKING` for repo tests, native build, bridge-lab SQL binding, and debug invoke on shell `940001`: on 2026-04-15, request `7` for player `5406` executed `summon_bonebound_twin_v2` and persisted `Bonebound Alpha` with `CreatedBySpell=940001`
- Bonebound Twins fast release submitter is `WORKING` as `python -m wm.spells.summon_release`; it skips proof preflights and submits the known shell `940001` request directly for repeated operator use, with bridge-lab request `8` reaching `done` in the same second on 2026-04-15
- Bonebound Twins Gorehowl weapon config is `WORKING` for the release lane: request `9` reached `done`, and live shell `940001` behavior config has both Alpha and Omega virtual item 1 set to `28773`
- persistent WM combat proficiency repo and live path are `WORKING` for player `5406`: high-ID `skillraceclassinfo_dbc` / `skilllineability_dbc` override SQL makes Shield `433`, Leather `414`, and Dual Wield skill `118` login-valid, `python -m wm.spells.shield_proficiency --player-guid 5406 --mode apply --summary` grants only explicit player GUIDs, Dual Wield persists through spell `674`, `mod-wm-spells` syncs the volatile Dual Wield flag only for active `combat_proficiency` grants, offhand one-handed sword equip works, Dual Wield displays in the spellbook, and `passive_intellect_block_v1` shell `944000` remains separate as an intellect/spellpower block-rating passive
- Bonebound Twins visible spell and mount/dismount lifecycle remain `PARTIAL` until the client shell patch and current live temporary-unsummon visual test are both proven
- combat proficiency playerbot proof remains `PARTIAL`: Shield, Leather, and Dual Wield are confirmed live for player `5406`, but playerbot maintenance is still unchecked for no inheritance

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
- most native mutation action kinds are intentionally disabled/not implemented until their C++ bodies pass lab tests
- Questie needs a tiny compat shim for WM custom quest ids because upstream Questie-335 does not know repo-owned quest ids like `910000`
- Phase 1 native bounty parity remains `PARTIAL` until the full in-game loop is rerun end-to-end on the current bridge lab
- dynamic per-trigger template watching remains experimental; the keepable pieces are being folded into the shared reactive/publish path instead of promoting a second watcher architecture
- subject recognition and memory remain `PARTIAL` at live/lab level until subject cards can be materialized automatically, seeded rows are proven against the lab DB, fresh native snapshots are consumed, and full proposal-gate previews exist
- combat proficiencies must not be added through `playercreateinfo_skills`, `playercreateinfo_spell_custom`, `mod_learnspells`, playerbot factory code, runtime `SetSkill` reapply, or class/equip override hooks; the only runtime exception is Dual Wield materializing `CanDualWield()` from persistent spell `674` behind explicit skill `118` validity and an explicit `combat_proficiency` grant
- Dual Wield is one-handed offhand capability; two-handed offhand weapons require Titan Grip and must be treated as a separate feature

## Recommended workflow

1. clone repo
2. run `setup-wm.bat`
3. run `build-wm.bat`
4. edit `.wm-bootstrap\run\configs\worldserver.conf` and `.wm-bootstrap\run\configs\authserver.conf`
5. apply `sql\bootstrap\wm_bootstrap.sql`
6. use `python -m wm.control.inspect/new/validate/apply` for manual control tests
7. continue WM feature work from the repo, not from machine-local rebuild leftovers

For native bridge action work, use `setup-bridge-lab.bat` and `build-bridge-lab.bat` once, then use `incremental-bridge-lab.bat` for normal C++ edits. Runtime tests should start `start-bridge-lab-mysql.bat`, run `configure-bridge-lab.bat`, and prove `debug_ping`/`debug_echo`/`debug_fail` before promoting anything back to a working realm.
