Status: PARTIAL
Last verified: 2026-04-17
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
- managed item reward proof is `WORKING` at DB/runtime-reload level: `control/examples/items/night_watchers_lens.json` publishes item `910006` (`Night Watcher's Lens`) from a reserved WM item slot, and BridgeLab quest `910024` (`Bounty: Nightbane Dark Runner - Lens`) now rewards it through `RewardItem1=910006`, `RewardAmount1=1`, plus the existing 12 silver; the current lens effect uses visible aura spell `132` as the wearer marker, then `mod-wm-spells` gives direct player attacks/wand-style hits a 10% chance to apply or refresh a visible 10-second target debuff (`770`) that bypasses attack avoidance/defense hooks and doubles WM-owned proc hooks such as Bonebound Alpha Echo; client-visible equip/passive proof is still `PARTIAL` until the fresh quest is turned in and the target debuff is confirmed in-game
- repo-owned bootstrap and bridge-lab workflows

### Live sensing and execution

- `addon_log` is the currently proven live perception path
- `native_bridge` exists and can emit canonical WM events
- `wm.events.watch` now survives per-iteration spine failures and flushes summary/error lines for automation logs instead of exiting silently on the first exception
- reactive bounty installs now have a repo-owned fast path through `control/examples/reactive_bounties/` and `scripts/bridge_lab/Install-BridgeLabReactiveBounty.ps1`
- reactive bounty templates are the supported fast operator lane; implicit auto-bounty creation from arbitrary kills is disabled by default and only available behind explicit opt-in config
- when `WM_REACTIVE_AUTO_BOUNTY_ENABLED=1`, the opt-in auto-bounty lane now binds dynamically to the exact observed creature entry after 4 consecutive same-entry kills within 300 seconds and picks the turn-in NPC from the current zone by faction-preferred quest-tie weight instead of a hardcoded target table; the streak evaluator fetches the newest bounded event slice before replaying it chronologically, so long event-log history no longer hides fresh kills, and consecutive streaks fire on threshold multiples like 4/8/12 rather than only exactly 4
- `python -m wm.reactive.install_bounty --list-templates --summary` lists bundled templates, and `--template-key <key>` installs one without copying a JSON path
- reactive bounty templates now default to fresh `wm_reserved_slot` quest allocation instead of reusing one mutable live quest ID across iterations
- reactive bounty dry-runs can preview the next free reserved quest slot without staging it or producing a false preflight failure
- shared reactive bounty publishing supports richer quest reward fields when the live `quest_template` schema exposes them:
  - money
  - reward item
  - `RewardXPDifficulty`
  - `RewardSpell` / `RewardDisplaySpell`
  - `RewardFactionID*` plus value/override slots
- native action queue exists with DB-backed policy and player scoping
- Primitive Pack 1 is `WORKING` in BridgeLab for player `5406`: `player_apply_aura`, `player_remove_aura`, `player_restore_health_power`, `player_add_item`, `player_add_money`, `player_add_reputation`, `creature_spawn`, `creature_despawn`, `creature_say`, and `creature_emote` are implemented in `mod-wm-bridge`, stay policy-disabled by default, and `python -m wm.control.scene_play` plus direct `wm.control.apply` proofs reached native requests `54-72` `done`; the bundled `field_medic_pulse`, `bonebound_battle_cry`, and `summon_marker` scenes all completed through control/audit, and the `creature_spawn` result payload now returns the real WM-owned `object_id`
- Primitive Pack 2 is `PARTIAL`: repo tests and the BridgeLab native build are `WORKING` for `player_cast_spell`, `player_set_display_id`, `creature_cast_spell`, `creature_set_display_id`, and `creature_set_scale`; all stay policy-disabled by default, creature mutation still requires WM-owned `wm_bridge_world_object` ownership, and bundled scene `arcane_marker_demo` exists, but live apply request `83` failed with `player_not_online` before proving visible in-game behavior
- `context_snapshot_request` is `WORKING` for one-shot bridge-lab proof: scoped player `5406` online, native action request `31` reached `done`, `wm_bridge_context_snapshot` row `1` was written, and `wm.context.builder --event-id 603 --summary` consumed it with `native_snapshot: true`
- native spell learn and unlearn actions exist
- player-owned non-pet summon kill attribution is `WORKING` at repo and BridgeLab event-log level: `mod-wm-bridge` supplements the existing player/pet kill hooks with a guarded `UnitScript::OnUnitDeath` path for player-owned killers that are neither the player nor a real pet/totem, so Echo/guardian/temp-summon kills feed the same native watcher path without double-emitting Alpha pet kills
- `quest_grant` prefers native `quest_add` when bridge config, player scope, and policy are ready, with SOAP fallback otherwise
- control-native convergence V1 is `WORKING` for the current operator scope: repo tests cover audit/request extraction plus stale-event, wrong-player, and idempotency rejection visibility; BridgeLab fresh-event proof on 2026-04-16 reached event `1599` -> proposal `43` -> native `quest_add` request `74` `done` -> `quest_grant_issued` event `1601`, and native bridge event `26505` recorded `quest/granted` for quest `910020`
- the Phase 1 reactive bounty loop has repo-level automated parity coverage and historical native bridge proof for quest `910000`

### Native spell platform

- shell-bank contract exists
- client patch workspace exists
- `mod-wm-spells` exists as the stable native spell-behavior runtime
- lab debug invoke exists for shell-bound behavior testing without a visible client shell
- Bonebound Alpha native lane is `WORKING` at repo/build level on shell `940001`: bridge-lab SQL now binds `summon_bonebound_alpha_v3`, `spawn_omega=false`, stock carriers `697` / `49126` remain retired, and the native module builds with low physical bleed ticks plus a 7.5% Alpha echo melee-hook behavior
- Bonebound Alpha stat transfer is `WORKING` in native config/code: summoner total intellect is applied to Alpha stats and shadow spell power is applied to Alpha attack power
- Bonebound Alpha fast release submitter is `WORKING`: `python -m wm.spells.summon_release --player-guid 5406 --summary` submits shell `940001` directly and now defaults to behavior `summon_bonebound_alpha_v3`
- Bonebound Alpha Gorehowl weapon config is `WORKING` in BridgeLab: shell `940001` behavior config sets Alpha virtual item 1 to `28773`
- persistent combat proficiency repo and live path are `WORKING` for player `5406`: DBC override SQL makes Shield `433`, Leather `414`, and Dual Wield skill `118` login-valid, `python -m wm.spells.shield_proficiency --player-guid 5406 --mode apply --summary` grants only the explicit player GUID through `character_skills`, `character_spell`, and `wm_spell_grant`, and the block-rating passive shell `944000` no longer restores Shield by runtime `SetSkill` or class override hooks; Dual Wield persists through stock spell `674`, `mod-wm-spells` materializes the volatile `CanDualWield()` flag only for active `combat_proficiency` grants, offhand one-handed sword equip works, and Dual Wield displays in the spellbook

## What is partial

- `native_bridge` is not yet the fully proven primary live path for all current WM gameplay loops
- the April 13, 2026 bridge-lab rerun only reached smoke level:
  - `debug_ping` reached `done`
  - `wm.events.watch --adapter native_bridge --arm-from-end` advanced the live high-water mark
  - the full in-game `Kobold Vermin -> quest 910000 -> reward -> cooldown -> regrant` loop was not rerun because validation player `5406` was offline
- broad native action vocabulary exists, but many verbs are still disabled or `not_implemented`; Pack 2 cast/display/scale verbs are implemented but not live-proven
- subject recognition is only a first slice:
  - static lookup and live-target resolver wrapping exist
  - DB-backed journal read helpers and resolver-card fallback exist
  - context-pack assembly exists and includes recipe/policy metadata plus latest native snapshot rows when present
  - repo tests are `WORKING` for the resolver, journal reader/inspect, and context-pack assembly
  - bridge-lab DB proof on `127.0.0.1:33307` is `WORKING` for the seeded player `5406` / creature `46` journal and event-backed context pack
  - automatic subject materialization, zone mood, and full proposal-gate previews are still `PARTIAL`
- visible shell-bank spells are not yet proven end-to-end in the client because the local patch artifact is not finalized and installed from repo instructions
- Bonebound Alpha live release-lane smoke is `WORKING`: on 2026-04-16 the SQL applied, worldserver restarted, player `5406` came online, release request `11` completed on shell `940001`, and user validation accepted the low bleed / echo behavior; future damage tuning should still capture exact tick and melee values before changing coefficients
- Bonebound Alpha echo mount/dismount restore is `PARTIAL`: repo/static tests cover preserving Echo state during player mount temporary-unsummon, preventing player maintenance from erasing that state while the main pet is absent, and respawning it with remaining lifetime after the Bonebound pet returns; the rebuilt worldserver was deployed to BridgeLab pid `31208`, and live in-game proof is still pending
- combat proficiency bot-safety proof is `PARTIAL`: player `5406` is confirmed live for Shield, Leather, and Dual Wield, but a playerbot maintenance cycle still needs to show bots did not inherit the grants
- experimental `template_watch` / `template_publish` comparison work remains isolated in `.worktrees/template-watch-compare`; its dynamic binding idea is useful, but its standalone watcher path is not the production architecture
- implicit auto-bounty generation is not a supported default path; use explicit JSON templates or `--template-key` to install the exact bounty being tested, and enable the dynamic 4-in-a-row auto-bounty lane only when that specific live behavior is what you are validating
- full auto-bounty grant proof after the April 17, 2026 event-window fix is still `PARTIAL`: native bridge perception and event-log ingestion are proven live, but the fresh 4-in-a-row kill -> grant -> turn-in loop must be rerun from an armed watcher

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
- Hidden server-side effects must have a player-facing indication. Use an aura, buff, debuff, combat-log/system message, or tooltip path; do not ship invisible stat/resource/combat changes and do not attach unrelated stock effects just to make a tooltip appear.
- "Double every proc" is not a free item-template feature. Night Watcher's Lens doubles WM-owned proc hooks that explicitly check the tracked debuff; arbitrary stock/core proc doubling remains `PARTIAL` until a proper proc-event hook is added.
- combat proficiency persistence requires DBC validity plus explicit character rows; do not restore skills with login/update `SetSkill` hooks, class-equip overrides, `playercreateinfo_skills`, `mod_learnspells`, or playerbot maintenance. Dual Wield needs skill `118` to be DBC-valid before spell `674` survives login; native runtime may then materialize `CanDualWield()` from persistent spell `674` only for explicit `combat_proficiency` grants. Two-handed offhand weapons require Titan Grip and are not normal Dual Wield.
- Bonebound Omega field copying is not proof of real combat parity. If a second combat companion returns later, use a true supported pet/guardian chassis or hook-backed damage path and prove health, mana, and melee output in the lab before marking it `WORKING`.
- Alpha echo template truth matters: spawn echo procs from WM creature entry `920101`, not stock Voidwalker `1860`, and copy final Alpha health/power/damage only after `UpdateAllStats()` paths have run.
- Do not let old auto-generated bounty rules drive live tests. Install one explicit template by path or `--template-key`, or explicitly enable the dynamic auto-bounty lane, then arm the watcher from the end and start killing only after arming.
- Consecutive auto-bounty streaks are based on recorded kill events, not combat text. After the 2026-04-17 bridge patch, player-owned non-pet summons can also contribute to and reset those streaks. Streak code must fetch the newest bounded event slice first and only then replay it chronologically; `ORDER BY EventID ASC LIMIT n` returns stale history on a long-running lab DB and breaks live watcher triggers.
- Primitive Pack 2 display/cast/scale actions are still operator lab primitives, not content defaults. Keep policy disabled outside explicit scoped tests; player display changes are temporary server display changes, not a client shell or persistent appearance system.
- Native `quest_add` parity depends on GM-force-grant semantics. WM force grants must mirror `.quest add` sanity checks, not `player->CanTakeQuest()`, or repeatable/operator quests can reject natively even while the existing SOAP lane succeeds.
- Immediate `character_queststatus` reads are not sufficient proof for a fresh live quest grant on this core branch. For fresh native grants, trust `wm.control.audit`, native bridge `quest/granted`, and GM `.quest status` before claiming the grant failed just because the character DB row is absent or delayed.
- Bounty rewards should use managed item slots when coin-only rewards feel meaningless. Do not solve "wand fires while moving" as an item-template-only edit; that needs a native combat/action behavior or client-facing shell work.
- Do not reuse an already accepted/rewarded quest ID when changing visible rewards. On 2026-04-17, quest `910021` kept showing only 12 silver after an item reward edit because that ID had already been accepted/rewarded in the live client session. Publish a fresh reserved quest slot, reload/restart as needed, then grant the new quest ID.
- Control proposals for non-admin event-bound actions must use a fresh source event; old copied proposal JSON will be rejected as stale by policy.
- Dirty lab state can poison summon and pet retests.
- Design docs can be useful and still be stale.
- Current-state docs and postmortems outrank aspirational design notes.
- The repo may contain dirty local experiments; only supported paths in status docs should be treated as trusted.
