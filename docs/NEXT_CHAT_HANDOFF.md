Status: PARTIAL
Last verified: 2026-04-26
Verified by: Codex
Doc type: handoff

# Next Chat Handoff

This is the short, practical handoff for continuing WM work in a fresh chat.

Use this with:

- [Documentation Index](README_OPERATIONS_INDEX.md)
- [Roadmap](ROADMAP.md)
- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)
- [Work Summary](WORK_SUMMARY.md)
- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)
- [Custom ID Ledger](CUSTOM_ID_LEDGER.md)

## Repo State

Repo path: `D:\WOW\wm-project`

Default validation player: `5406` / Jecia

BridgeLab MySQL is `127.0.0.1:33307`. Do not use default `3306` for BridgeLab proof.

The repo is an external-first World Master platform for AzerothCore:

- Python WM owns decisions, validation, audit, publishing, rollback, and operator workflow.
- Native modules own sensing and typed atomic actions.
- `control/` is the operator and future LLM contract lane.
- Freeform SQL, freeform GM commands, and direct LLM mutation are not supported architecture.
- The roadmap direction is per-character World Master progression: personal arcs, exclusive rewards/unlocks, item-granted abilities, visible shell powers, live scenes, companion behavior, and conversation steering.

## Current Working Areas

- Event spine: canonical events, projection, rule evaluation, reaction logs, cooldowns, inspect/watch/run flows.
- Control lane: `wm.control.new`, `wm.control.validate`, `wm.control.apply`, `wm.control.audit`, stale-event policy, idempotency, wrong-player rejection, and native request audit extraction.
- Native bridge: typed action queue, player scope, policy rows, primitive action packs, and BridgeLab control/audit proof for the first scene primitives.
- Reactive bounty templates: fast operator install path through bundled templates and reserved quest slots.
- Dynamic auto-bounty: opt-in 4 consecutive same-entry kills within 300 seconds, zone-based turn-in NPC selection, random suitable equipment reward selection, player-scoped native bridge cursor/evaluation, one-event BridgeLab apply batches, a one-hour dynamic-rule freshness gate, one unresolved dynamic auto-bounty per player by default, full managed quest-slot seeding before BridgeLab proof, and pre-arm backlog marking when arming from end.
- Bounty publishing: repeatable quest semantics through `quest_template_addon.SpecialFlags |= 1`, level-scaled money, XP difficulty, item rewards, spell rewards, and reputation rewards where schema supports them.
- Custom ID governance: exact claims live in `data/specs/custom_id_registry.json`; docs mirror that ledger.
- Spell shell path: named shell/client patch/server DBC pipeline is working at repo/artifact level, with `940001` as the Bonebound Alpha lane.
- Bonebound Alpha: supported summon lane is single Alpha on shell `940001`, creature entry `920100`, echo entry `920101`; Omega is retired. Visible Alpha/Echo bleed is live `WORKING` after the 2026-04-25 BridgeLab proof: melee hooks apply visible target aura `772`, physical ticks are WM-owned, Echo bleed stacks independently by caster GUID plus target GUID, and tick damage is attack-power-primary through `bleed_damage_per_attack_power_pct=20`.
- Persistent combat proficiencies: Shield, Leather, and Dual Wield are explicit-GUID grants backed by DBC validity, not login hooks or class overrides.
- BridgeLab solo dungeon tuning: active config files are staged for solo 5-player dungeons at 75% original 5-player HP, 50% damage, 75% XP, and 2x dungeon loot. Config-load proof is `WORKING` because the files contain the expected values and current worldserver pid `32420` started after they were written; live dungeon feel is still `PARTIAL` until an in-game check.

## Current Partial or Open Areas

- Phase 1 native bounty parity remains `PARTIAL` until a full live trigger -> grant -> complete -> reward -> suppress -> cooldown -> regrant loop is rerun on current code.
- Dynamic auto-bounty live proof is `WORKING` for the trigger/grant leg and still `PARTIAL` for the full playcycle. On 2026-04-26, Jecia's `Hederine Slayer` (`7463`) streak created quest `910103`, reward item `20631` (`Mendicant's Slippers`), native `quest_add` request `312` reached `done`, native bridge emitted `quest/granted` event `31367`, WM recorded event `5483`, and SOAP/DB later showed quest `910103` complete (`status=1`, `mobcount1=4`). A pre-fix single-open gate miss then created current active quest `910102` (`Bounty: Hederine Initiate`); the code now prioritizes active rules and scans all player auto-rule quest IDs instead of the 50 newest updated rows. Complete -> reward -> suppress -> cooldown -> regrant still needs proof on `910102` or a later clean bounty.
- Random enchant consumable item-use, operator-selected kill grant, and scoped watcher grant paths are live `WORKING` for the original `910007` proof; the current two-vellum retune is repo `WORKING` / live `PARTIAL` until user in-game focused vellum use is proven. Native action `player_random_enchant_item` remains policy-disabled by default. The player-facing path now grants `910007` (`Unstable Enchanting Vellum`) at `7%` and `910008` (`Enchanting Vellum`) at `3.5%` from scoped kill rolls when `WM_RANDOM_ENCHANT_ON_KILL_ENABLED=1`; it still requires player scope and does not run globally. `910007` stacks to `999`, applies up to three enchants, preserves existing slots at 15%, and has a 10% chance per roll to use tier 5. `910008` stacks to `999`, lets the player choose target item then enchant slot, and rerolls one chosen slot with weighted tiers: 40% tier 3, 30% tier 4, 30% tier 5. Old proof covered direct grant request `160`, live stack proof, user right-click/enchant/consume proof, forced scoped kill-roll request `161`, and watcher requests `162`/`163`. On 2026-04-25, SQL `2026_04_25_02_wm_bridge_enchanting_vellum_variants.sql` was applied, `mod-wm-bridge` was rebuilt/restarted to worldserver pid `33620`, native request `164` reached `done` for `debug_ping`, requests `165` / `166` granted `910007` / `910008`, inventory persistence showed `910007` count `40` and `910008` count `1`, and watcher pid `30224` was armed from end with random enchant drops enabled at `7%` / `3.5%`. The weighted tier change was rebuilt/restarted to worldserver pid `31360`; request `260` `debug_ping` reached `done`, request `261` extra `910008` grant failed with `player_not_online`, and watcher pid `27240` is now armed from end.
- Bone Lure consumable is no longer the active proof target; user accepted the lane as OK before moving back to roadmap work. Repo/build/DB/grant status remains `WORKING`: item `910009` (`Bone Lure Charm`) and creature `920102` (`Bone Lure Obelisk`) are claimed, SQL `2026_04_25_03_wm_bridge_bone_lure_obelisk.sql` is applied, native compile is clean, worldserver pid `20232` ran the proof build, native request `262` `debug_ping` reached `done`, request `263` granted five charms, and gameplay was accepted by user. Keep detailed taunt/leash regression proof in mind before broadening the mechanic.
- Reactive area-pressure scene feature is repo `WORKING` / live `PARTIAL`: `WM_EVENT_AREA_PRESSURE_SCENE_ENABLED=1` makes the existing area-pressure opportunity compose typed native `world_announce_to_player`, `player_restore_health_power`, and optional visible `player_apply_aura` actions. `Start-BridgeLabNativeWatch.ps1 -EnableAreaPressureScene` exposes the BridgeLab proof lane. Native action idempotency now includes trigger identity plus `idempotency_suffix`, preventing repeated event triggers from reusing the first native request.
- Bonebound Alpha/Echo visible bleed is `WORKING` after user live proof on 2026-04-25. Echo bleed stacks independently by caster GUID plus target GUID, and ticks scale primarily from caster melee attack power (`bleed_damage_per_attack_power_pct=20`). Echo Destroyer seek/follow/range/teleport control and Echo Restorer Mind Blast/positioning/speed/seek retune are deployed on BridgeLab pid `28000`: active WM player can type `wm echo seek`, `wm echo seek 60`, `wm echo range 60`, `wm echo follow`, or `wm echo teleport` / `wm echo tp` / `wm echo recall`; seek radius is per-player runtime state clamped to `5-100` yards. Restorers should cast visible Mind Blast `8092` at up to `100` yards, participate in seek as ranged casters, spread in closer formation slots between player and Destroyers, and move at Destroyer-matched template/runtime speed. Live proof still needs confirmation. Echo mount/dismount restore still needs live proof.
- 2026-04-27 retune after the above: seek now chooses nearest eligible hostile to Jecia, not nearest to each Echo; Restorers can leave the close support ring in seek mode to get into visible cast range; Restorer Mind Blast starts a real visible `8092` cast instead of a fake delayed triggered hit; active Echo names force object-visibility refresh; Bonebound Echo Stasis adds active Echo counts into the saved pool instead of replacing it and restores only when no Echoes are active; Echo follow slots use deterministic formation rings with a 1.6 yard spacing target to reduce model-merge. BridgeLab worldserver pid is now `28000`; live proof is still needed.
- 2026-04-27 server-error cleanup: Jecia had stale stock visual/template spells `116`, `133`, `403`, `770`, `1459`, and `16827` persisted in `character_spell`, causing AzerothCore login validation errors and deletion messages. Those rows were deleted from BridgeLab, and `wm.content.workbench` now blocks those IDs from persistent player learn paths. Stock visual/template spell IDs remain allowed as DBC seed/effect/visual references only.
- Bonebound Alpha Demonology passive compatibility is not globally proven.
- Combat proficiency playerbot negative proof is still open.
- Client-visible spell shell polish remains open for animation/action-bar/relog lifecycle.
- Generic shell-bank V2 families need one live proof per family before marking client lab proof `WORKING`.

## Immediate Bug Context

Latest live issue is resolved for the trigger/grant leg. Root cause on 2026-04-26 was not perception: the dynamic auto-bounty planner could resolve a bounty, but lab `wm_reserved_slot` only had quest rows `910000-910099`, so there were zero free quest slots even though the ledger range is `910000-910999`. The old path silently returned `None` on slot exhaustion and then marked kills evaluated.

Fixes now in repo:

- native bridge cursor key is per-player: `last_seen:player:<guid>`, with a legacy `last_seen` fallback.
- `execute_event_spine()` passes `player_guid` into unprojected/unevaluated event reads, so a scoped run does not evaluate other characters' backlog.
- BridgeLab auto-bounty watcher starts with `--batch-size 1` to avoid multiple apply plans in one iteration.
- dynamic auto-bounty creation ignores stale queued kills by default via `WM_REACTIVE_AUTO_BOUNTY_MAX_EVENT_AGE_SECONDS=3600`.
- dynamic auto-bounty creation is serial per player by default via `WM_REACTIVE_AUTO_BOUNTY_SINGLE_OPEN_PER_PLAYER=1`; this prevents fast pulls from stacking several fresh WM bounty quests before the player can complete or clear the first one.
- repo scripts no longer write global `AiPlayerbot.EnableBroadcasts = 0`; that is a temporary runtime safety switch only, not a WM deployment behavior.
- `ReactiveAutoBountyManager` now raises a visible operator error when a valid dynamic plan cannot allocate a reserved quest slot.
- `Start-BridgeLabAutoBounty.ps1` seeds quest slots `910000-910999` before arming.
- `wm.events.watch --mark-existing-evaluated-on-arm` marks already recorded scoped event backlog evaluated when paired with `--arm-from-end`; the auto-bounty starter uses it by default so pre-arm events do not create the first active rule.
- the unresolved-bounty gate no longer limits the player auto-rule scan to 50 rows; it orders active rules first, then updated time, so bulk deactivation cannot hide the actual open quest behind newer inactive rows.

Live recovery was applied:

- the full managed quest slot range was seeded in BridgeLab: existing `100`, inserted `900`.
- watcher restarted cleanly on pid `21272` with `mark_existing_evaluated_on_arm=true`, cursor `last_seen:player:5406`, and no active auto rules / no unevaluated backlog before the fresh proof.
- fresh `Hederine Slayer` (`7463`) kills produced quest `910103` (`Bounty: Hederine Slayer`), native request `312` `done`, native bridge event `31367`, and WM event `5483`; later `saveall` showed `910103` complete with `mobcount1=4`.
- current active rule is `reactive_bounty:auto:zone:618:subject:7461` for quest `910102` (`Bounty: Hederine Initiate`). SOAP reports `910102` incomplete; after `saveall`, DB showed `mobcount1=2`. Finish `910102` with two more `7461` kills, then turn in at Witch Doctor Mau'ari (`10307`) to prove reward/cooldown/regrant.

Previous Whelp failure context:

The user killed "Crimson Whelps", but the live event stream showed exact entries:

- `1043` = `Lost Whelp`
- `1069` = `Crimson Whelp`

WM detected burst thresholds and applied reactions:

- `Lost Whelp` bounty: quest `910046`
- `Crimson Whelp` bounty: quest `910047`

Both quest rows were repeatable:

- `quest_template_addon.SpecialFlags = 1`

The problem was native request idempotency. `quest_grant` used a stable native request key based only on rule/player/quest:

```python
f"{plan.plan_key}:native:quest_add:{quest_id}"
```

That caused later bursts for the same bounty rule to reuse the first completed `wm_bridge_action_request`, so no fresh native `quest_add` request was enqueued.

The fix is in `src/wm/events/executor.py`: native quest grant idempotency now includes trigger identity from `plan.metadata["source_event_key"]`, `opportunity_metadata["source_event_key"]`, or `opportunity_metadata["trigger_event_id"]`.

Regression coverage is in `tests/test_event_executor.py`: repeated grants with the same plan key and quest ID but different trigger source keys must submit different native idempotency keys.

## Useful Commands

Set BridgeLab DB environment first:

```powershell
$env:PYTHONPATH='src'
$env:WM_WORLD_DB_PORT='33307'
$env:WM_CHAR_DB_PORT='33307'
```

Inspect recent live events:

```powershell
python -m wm.events.inspect --player-guid 5406 --limit 40 --summary
```

Inspect dynamic auto-bounty state:

```powershell
python -m wm.reactive.auto_bounty --player-guid 5406 --summary
```

Start clean dynamic auto-bounty lane:

```powershell
.\scripts\bridge_lab\Start-BridgeLabAutoBounty.ps1 -PlayerGuid 5406 -Mode apply -BatchSize 1 -ReactiveAutoBountyMaxEventAgeSeconds 3600
```

Check watcher:

```powershell
.\scripts\bridge_lab\Get-BridgeLabNativeWatchStatus.ps1 -WorkspaceRoot D:\WOW\wm-project -TailLines 10
```

Focused tests for the latest bounty/watch path:

```powershell
python -m pytest tests/test_event_executor.py tests/test_event_rules.py tests/test_reactive_auto_bounty.py tests/test_bounty_reward_picker.py -q
```

Full tests:

```powershell
python -m pytest -q
```

## Hard Rules

- Trust current-state docs over roadmap/design notes.
- Classify outcomes as `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`.
- Do not reuse stock spell IDs as permanent WM carriers.
- Do not remove or hijack stock Summon Voidwalker `697`.
- Do not revive Bonebound Omega without a new structural design and live damage/resource proof.
- Do not restore combat proficiencies with login/update `SetSkill` hooks, class equip overrides, `playercreateinfo_skills`, `mod_learnspells`, or playerbot maintenance.
- Do not mutate accepted/rewarded quest IDs for visible reward iteration; allocate a fresh reserved quest slot.
- Do not mix stale `reactive_bounty:template:*` rows with the dynamic auto-bounty lane.
- Dynamic auto-bounty streaks are exact `subject_entry`, not display name, creature family, or dungeon pull.
- Do not make WM BridgeLab scripts globally disable playerbot broadcasts as a permanent fix. Scope WM event capture through WM bridge allowlists/player scope, and fix playerbot broadcast crashes in the playerbot path.
- Hidden server effects need player-facing indication through an aura, buff, debuff, message, or tooltip, and hidden logic must be gated by the visible state/duration.
- After three failed attempts on the same approach, stop and document the structural reason before changing code again.

## Next Best Step

Next best step is to finish the active `Bounty: Hederine Initiate` quest `910102`, then prove reward/cooldown/regrant. Jecia needs two more `Hederine Initiate` (`7461`) kills based on the latest saved DB state, then turn in at Witch Doctor Mau'ari (`10307`). Verify:

- `character_queststatus(5406, 910102).mobcount1` reaches `4`
- turn-in works and reward state emits
- immediate extra streaks do not create a second dynamic bounty while the first one is still unresolved
- immediate retrigger is suppressed
- cooldown reopens a new fresh request
