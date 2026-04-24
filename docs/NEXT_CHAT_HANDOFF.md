Status: PARTIAL
Last verified: 2026-04-24
Verified by: Codex
Doc type: handoff

# Next Chat Handoff

This is the short, practical handoff for continuing WM work in a fresh chat.

Use this with:

- [Documentation Index](README_OPERATIONS_INDEX.md)
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

## Current Working Areas

- Event spine: canonical events, projection, rule evaluation, reaction logs, cooldowns, inspect/watch/run flows.
- Control lane: `wm.control.new`, `wm.control.validate`, `wm.control.apply`, `wm.control.audit`, stale-event policy, idempotency, wrong-player rejection, and native request audit extraction.
- Native bridge: typed action queue, player scope, policy rows, primitive action packs, and BridgeLab control/audit proof for the first scene primitives.
- Reactive bounty templates: fast operator install path through bundled templates and reserved quest slots.
- Dynamic auto-bounty: opt-in 4 consecutive same-entry kills within 300 seconds, zone-based turn-in NPC selection, random suitable equipment reward selection, player-scoped native bridge cursor/evaluation, one-event BridgeLab apply batches, a one-hour dynamic-rule freshness gate, and one unresolved dynamic auto-bounty per player by default.
- Bounty publishing: repeatable quest semantics through `quest_template_addon.SpecialFlags |= 1`, level-scaled money, XP difficulty, item rewards, spell rewards, and reputation rewards where schema supports them.
- Custom ID governance: exact claims live in `data/specs/custom_id_registry.json`; docs mirror that ledger.
- Spell shell path: named shell/client patch/server DBC pipeline is working at repo/artifact level, with `940001` as the Bonebound Alpha lane.
- Bonebound Alpha: supported summon lane is single Alpha on shell `940001`, creature entry `920100`, echo entry `920101`; Omega is retired. Visible bleed fix is repo-patched, BridgeLab-compiled with `Build-BridgeLabIncremental.ps1 -NoStageRuntime`, SQL-migrated, and deployed on worldserver pid `8312`, but live `PARTIAL` until in-game proof of target aura `772` plus physical ticks.
- Persistent combat proficiencies: Shield, Leather, and Dual Wield are explicit-GUID grants backed by DBC validity, not login hooks or class overrides.
- BridgeLab solo dungeon tuning: active config files are staged for solo 5-player dungeons at 75% original 5-player HP, 50% damage, 75% XP, and 2x dungeon loot. Worldserver restarted to pid `8312`, so live dungeon behavior is still `PARTIAL` only until in-game check.

## Current Partial or Open Areas

- Phase 1 native bounty parity remains `PARTIAL` until a full live trigger -> grant -> complete -> reward -> suppress -> cooldown -> regrant loop is rerun on current code.
- Dynamic auto-bounty live proof is `WORKING` for the trigger/grant leg and still `PARTIAL` for the full playcycle. On 2026-04-24, Jecia's `Mottled Scytheclaw` (`1022`) streak created quest `910076`, native `quest_add` request `147` reached `done`, and native bridge emitted `quest/granted` event `28031`; complete -> reward -> suppress -> cooldown -> regrant still needs proof.
- Random enchant consumable lane is repo `WORKING` / live `PARTIAL`: native action `player_random_enchant_item` remains policy-disabled by default, but the player-facing path is item `910007` (`Unstable Enchanting Vellum`). `python -m wm.reactive.random_enchant --player-guid 5406 --chance-pct 2.5 --mode apply --summary` now deterministically rolls recent kill events and submits selected events as `player_add_item` grants for the consumable. The watcher path is opt-in through `WM_RANDOM_ENCHANT_ON_KILL_ENABLED=1` or `Start-BridgeLabNativeWatch.ps1 -EnableRandomEnchantOnKill`; it requires player scope and does not run globally. BridgeLab native build and SQL apply are done; next proof needs deploy/restart when Jecia can relog, consumable grant, in-game right-click menu, enchant application, and one selected kill-roll proof.
- Bonebound Alpha visible bleed and echo mount/dismount restore still need live proof after the next native build/restart.
- Bonebound Alpha Demonology passive compatibility is not globally proven.
- Combat proficiency playerbot negative proof is still open.
- Client-visible spell shell polish remains open for animation/action-bar/relog lifecycle.
- Generic shell-bank V2 families need one live proof per family before marking client lab proof `WORKING`.

## Immediate Bug Context

Latest live issue: Jecia killed `Mottled Scytheclaw` (`1022`) and initially got no quest. Native bridge perception was `WORKING`; the watcher had died and the event runner was projecting/evaluating unscoped global backlog. Fixes now in repo:

- native bridge cursor key is per-player: `last_seen:player:<guid>`, with a legacy `last_seen` fallback.
- `execute_event_spine()` passes `player_guid` into unprojected/unevaluated event reads, so a scoped run does not evaluate other characters' backlog.
- BridgeLab auto-bounty watcher starts with `--batch-size 1` to avoid multiple apply plans in one iteration.
- dynamic auto-bounty creation ignores stale queued kills by default via `WM_REACTIVE_AUTO_BOUNTY_MAX_EVENT_AGE_SECONDS=3600`.
- dynamic auto-bounty creation is serial per player by default via `WM_REACTIVE_AUTO_BOUNTY_SINGLE_OPEN_PER_PLAYER=1`; this prevents fast pulls from stacking several fresh WM bounty quests before the player can complete or clear the first one.
- repo scripts no longer write global `AiPlayerbot.EnableBroadcasts = 0`; that is a temporary runtime safety switch only, not a WM deployment behavior.

Live recovery was applied:

- stale April 17 Jecia backlog was flushed without creating plans.
- quest `910076` (`Bounty: Mottled Scytheclaw`) was granted by native request `147`.
- after the one-open dynamic-bounty gate landed, the watcher was restarted on pid `30580`; recheck with the status script instead of assuming it is still alive.
- read-only DB check after restart showed old dynamic auto-bounty quests `910090`, `910097`, and `910098` still active on Jecia with `character_queststatus.status=3`. With `WM_REACTIVE_AUTO_BOUNTY_SINGLE_OPEN_PER_PLAYER=1`, these intentionally block new dynamic auto-bounty creation until they are completed, abandoned, or cleaned through a typed quest-cleanup path.

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

Next best step is to clear or complete Jecia's currently active dynamic auto-bounty quests (`910090`, `910097`, `910098`), then run one clean new streak to prove the serial dynamic-bounty gate. Verify:

- `wm.events.inspect` shows a fresh `kill_burst_detected`
- `wm_reaction_log` has a fresh applied reaction
- `wm_bridge_action_request` has a new `quest_add` row with a trigger-specific idempotency key
- native bridge emits `quest/granted`
- the quest appears in the client
- turn-in works and reward state emits
- immediate extra streaks do not create a second dynamic bounty while the first one is still unresolved
- immediate retrigger is suppressed
- cooldown reopens a new fresh request
