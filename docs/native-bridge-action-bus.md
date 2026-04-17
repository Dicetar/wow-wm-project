Status: PARTIAL
Last verified: 2026-04-17
Verified by: Codex
Doc type: reference

# Native Bridge Action Bus

The native action bus is the next WM bridge layer after native perception.

It lets WM enqueue one fixed, typed server action into `wm_bridge_action_request`, while `mod-wm-bridge` validates player scope and policy before executing it. C++ still does not plan, generate story, run arbitrary SQL, run GM commands, edit files, or decide cooldown policy. WM Python and the `control/` registry remain the brain.

Gossip close is intentionally WM-derived for now. This AzerothCore branch exposes clean gossip open/select hooks, but not a clean module hook for close/cancel. WM emits `gossip_session_expired` after a configurable timeout when a native `talk` event has no matching `gossip_select`.

## Safety Defaults

The action bus is compiled but inert until explicitly enabled:

- `WmBridge.ActionQueue.Enable = 0`
- `WmBridge.DbControl.Enable = 0`
- `WmBridge.PlayerGuidAllowList = ""`
- most native mutation verbs are disabled in `wm_bridge_action_policy`
- most mutation verbs return `not_implemented` in C++ until each body has a lab test

Implemented native actions in the first safe slice:

- `debug_ping`
- `debug_echo`
- `debug_fail`
- `context_snapshot_request` writes one `wm_bridge_context_request` plus one `wm_bridge_context_snapshot` when the scoped player is online; live bridge-lab proof is `WORKING`
- `quest_add`
- `world_announce_to_player`
- Primitive Pack 1 is `WORKING` in BridgeLab behind policy-disabled defaults:
  - `player_apply_aura`
  - `player_remove_aura`
  - `player_restore_health_power`
  - `player_add_item`
  - `player_add_money`
  - `player_add_reputation`
  - `creature_spawn`
  - `creature_despawn`
  - `creature_say`
  - `creature_emote`
- Primitive Pack 2 is `PARTIAL` behind policy-disabled defaults:
  - `player_cast_spell`
  - `player_set_display_id`
  - `creature_cast_spell`
  - `creature_set_display_id`
  - `creature_set_scale`
  - repo tests and BridgeLab native build are `WORKING`
  - live scene proof is blocked until scoped player `5406` is online; request `83` failed with `player_not_online`

Everything risky should be proven in `D:\WOW\WM_BridgeLab` before promotion.

`quest_add` now emits a native bridge `quest/granted` row on success so WM can observe the grant through the same event spine instead of relying only on the action result.
For WM force-grant parity, `quest_add` mirrors GM `.quest add` sanity checks: reject item-start quests and already-active quests, but do not reuse `player->CanTakeQuest()`, because that is stricter than the existing SOAP/GM path and can reject repeatable/operator WM grants that are supposed to succeed.
The higher-level WM `quest_grant` action now prefers native `quest_add` when bridge config, player scope, and policy are ready, and falls back to SOAP only when native is not currently available.

## Tables

Core queue and gates:

- `wm_bridge_action_request`: one append-style action request with idempotency, status, payload, priority, optional sequence metadata, lease/attempt state, result, and error state.
- `wm_bridge_action_policy`: DB policy per action kind/profile with enabled flag, max risk, cooldown, burst limit, and admin-only flag.
- `wm_bridge_player_scope`: DB-backed live player allowlist.
- `wm_bridge_runtime_status`: native bridge heartbeat/status records.

Queue timing and ordering:

- `ExpiresAt` is the pending request deadline. If the row is still `pending` after this time, native code marks it `expired`.
- `ClaimExpiresAt` is the execution lease. If worldserver crashes while a row is `claimed`, the next native poll or the Python maintenance CLI requeues it until `MaxAttempts` is reached.
- `PurgeAfter` is only a Python cleanup hint. C++ never deletes terminal audit/debug rows automatically.
- `Priority` sorts pending work as `1=urgent`, `5=normal`, `9=background`.
- `SequenceID`, `SequenceOrder`, and `WaitForPrior` support manual/admin scene tests. Waiting rows run only after lower-order rows in the same sequence are `done`; if a prior row fails/rejects/expires, later waiting rows fail with `sequence_prior_failed`.
- `TargetMapID`, `TargetX`, `TargetY`, `TargetZ`, `TargetO`, and `TargetPlayerGUID` are optional structural coordinates for future spawn/move/teleport-style actions. Flexible details remain in `PayloadJSON`.

Support tables staged for future capability bodies:

- `wm_bridge_world_object`
- `wm_bridge_companion`
- `wm_bridge_gossip_override`
- `wm_bridge_item_script`
- `wm_bridge_spell_intercept`
- `wm_bridge_spell_script`
- `wm_bridge_counter`
- `wm_bridge_chat_keyword`

Primitive Pack 1 uses `wm_bridge_world_object.LiveGUIDLow` so WM-owned creature follow-up actions can resolve the spawned live creature safely by low GUID without touching non-WM-owned world objects. `creature_spawn` now inserts the ownership row synchronously before the immediate lookup so live result JSON carries the real `object_id` instead of `0`.
Primitive Pack 2 keeps the same guard: `creature_cast_spell`, `creature_set_display_id`, and `creature_set_scale` resolve only rows owned by the scoped player in `wm_bridge_world_object`, and they fail/reject rather than mutating arbitrary world creatures. `player_cast_spell` and `player_set_display_id` resolve only the scoped online player; display changes are temporary server-side display changes, not a persistent appearance or client shell system.

## Lab Workflow

Create and build an isolated bridge lab instead of touching the working rebuild:

```powershell
.\setup-bridge-lab.bat
.\build-bridge-lab.bat
```

The full build path regenerates CMake and resets the lab build directory. Use it for the first build or when source layout/CMake inputs changed. For normal native bridge C++ edits, use the incremental path instead:

```powershell
.\incremental-bridge-lab.bat
```

`incremental-bridge-lab.bat` builds the existing generated solution target `worldserver` and then stages runtime DLLs/output. If you only need to restage after a successful manual MSBuild run:

```powershell
.\stage-bridge-lab-runtime.bat
```

The incremental path also resyncs repo-owned local modules like `native_modules/mod-wm-bridge` into `D:\WOW\WM_BridgeLab` before compiling, so native bridge edits do not require a full workspace regenerate just to reach the lab binary.

The current proven lab dependency layout uses a copied MySQL data directory under `D:\WOW\WM_BridgeLab\deps\mysql`. Start it on an isolated port and point lab configs at it:

```powershell
.\start-bridge-lab-mysql.bat
.\configure-bridge-lab.bat
```

For normal runtime use after the lab has been built and staged:

```powershell
.\start-bridge-lab-server.bat
```

This launcher starts lab MySQL, syncs the auth realmlist to the lab world port, and uses a graceful-first worldserver restart helper instead of force-killing the process immediately.
`configure-bridge-lab.bat` also forces `mod_weather_vibe.conf` to `WeatherVibe.Debug = 0`, so WeatherVibe debug pushes do not pollute bridge/action tests by default.

Defaults:

- lab MySQL: `127.0.0.1:33307`
- lab worldserver port: `8095`
- lab SOAP port: `7879`
- lab data files: `D:\WOW\Azerothcore_WoTLK_Rebuild\run\data` as a read-only data source

The lab MySQL path avoids needing root permissions on the working MySQL instance and keeps queue/action tests away from the live `acore_*` databases. `New-BridgeLabDbCopy.ps1` remains available for admin-credential dump/import flows, but the preferred local path is the copied lab MySQL runtime.

Promotion is intentionally gated:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bridge_lab\Promote-BridgeBuild.ps1 -ConfirmPromoteToWorkingRebuild
```

That script copies only `authserver.exe` and `worldserver.exe`. It intentionally does not copy runtime DLLs, which prevents another MySQL/OpenSSL/`legacy.dll` mix-up.

## Enabling One Player

After applying the bootstrap/module SQL and rebuilding the bridge in the lab, enable DB-backed scope in `mod_wm_bridge.conf`:

```ini
WmBridge.DbControl.Enable = 1
WmBridge.ActionQueue.Enable = 1
```

Then scope a single player from WM:

```powershell
python -m wm.sources.native_bridge.actions_cli scope-player --player-guid 5406 --summary
```

This writes `wm_bridge_player_scope`; no config file edit is needed after DB control is enabled.

## Native Queue Smoke Test

Submit a non-mutating ping:

```powershell
python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind debug_ping --idempotency-key lab-debug-ping-1 --wait --summary
```

Expected result:

- request row is created in `wm_bridge_action_request`
- native module claims it
- status becomes `done`
- result contains a `pong` message

Submit an echo:

```powershell
python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind debug_echo --idempotency-key lab-debug-echo-1 --wait --summary
```

Submit an intentional failure:

```powershell
python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind debug_fail --idempotency-key lab-debug-fail-1 --wait --summary
```

Expected result for `debug_fail`: status `failed`, with structured error text.

Request one bounded context snapshot proof:

```powershell
python -m wm.context.snapshot --player-guid 5406 --timeout-seconds 10 --summary
.\scripts\bridge_lab\Request-BridgeLabContextSnapshot.ps1 -PlayerGuid 5406 -TimeoutSeconds 10 -Summary
```

Current status:

- `WORKING`: action row reaches `done` and a newer `wm_bridge_context_snapshot` row appears for the scoped player.
- `PARTIAL`: if lab `worldserver` is not running, the action row remains `pending`.
- `PARTIAL`: if player `5406` is not online, the rebuilt lab worldserver consumes the request and fails it with `player_not_online`.
- `BROKEN`: action row fails, rejects, expires, or bridge/action tables are unavailable.
- `UNKNOWN`: not used for this operator command.

Lab verification on 2026-04-15:

- `context_snapshot_request` request `31` reached `done`
- `wm_bridge_context_snapshot` row `1` was written for player `5406`
- snapshot payload included player location plus nearby creature/gameobject arrays
- `python -m wm.context.builder --event-id 603 --summary` consumed the snapshot and reported `native_snapshot: true`

Submit a small ordered sequence:

```powershell
python -m wm.sources.native_bridge.actions_cli submit-sequence --player-guid 5406 --sequence-id lab-seq-1 --actions-json '[{"action_kind":"debug_ping"},{"action_kind":"debug_echo","payload":{"message":"after ping"}}]' --wait --summary
```

Inspect and maintain queue state:

```powershell
python -m wm.sources.native_bridge.actions_cli inspect --player-guid 5406 --limit 10 --summary
python -m wm.sources.native_bridge.actions_cli recover-stale --summary
python -m wm.sources.native_bridge.actions_cli cleanup --older-than-seconds 3600 --summary
```

`world_announce_to_player` is implemented but policy-disabled by default. Enable it only in the lab for one scoped player:

```powershell
python -m wm.sources.native_bridge.actions_cli policy --action-kind world_announce_to_player --enable --max-risk-level low --cooldown-ms 1000 --burst-limit 5 --summary
python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind world_announce_to_player --payload-json '{"message":"WM bridge lab ping"}' --idempotency-key lab-announce-1 --wait --summary
```

Lab verification on 2026-04-11:

- isolated incremental `worldserver` target built successfully in `D:\WOW\WM_BridgeLab`
- lab runtime staging wrote `D:\WOW\WM_BridgeLab\state\runtime-dlls.lock.json`
- lab MySQL ran from `D:\WOW\WM_BridgeLab\deps\mysql` on port `33307`
- lab worldserver started on the lab DB/config
- `debug_ping` reached `done`
- `debug_echo` reached `done`
- `debug_fail` reached expected `failed`
- duplicate `debug_ping` idempotency key reused the same request row
- `world_announce_to_player` reached `done` and produced an in-game player-visible message
- `quest_add` placed quest `910000` directly into Jecia's quest journal and the quest was turn-in capable

Phase 1 parity evidence as of 2026-04-13:

- repo automated coverage now includes:
  - native kill-burst threshold crossing exactly once
  - native-preferred `quest_grant`
  - SOAP fallback when native prerequisites are not ready
  - post-reward cooldown reopen after expiry
  - one `execute_event_spine` integration pass with runtime reconciliation events recorded separately from the grant action
- explicit bounty templates are now the operator lane for live proof; implicit auto-bounty creation is disabled by default and must not be used to explain watcher behavior
- historical bridge-lab evidence for player `5406` includes:
  - `wm_bridge_action_request` `quest_add` rows reaching `done`
  - native `quest_granted` for `Bounty: Kobold Vermin`
  - native `quest_completed` for `Bounty: Kobold Vermin`
  - native `quest_rewarded` for `Bounty: Kobold Vermin`
  - WM cooldown state for `reactive_bounty:kobold_vermin`
- April 13, 2026 smoke rerun status:
  - `debug_ping` request reached `done`
  - `wm.events.watch --adapter native_bridge --arm-from-end --max-iterations 1` advanced the high-water mark for player `5406`
  - the full same-day in-game bounty rerun did not complete because player `5406` was offline

If you use Questie-335 while testing WM custom quests, install the repo addon under `wow_addons/WMQuestieCompat` into the client `Interface\AddOns\` folder. It suppresses Questie tracker spam for WM-owned quest ids like `910000`.

Two build compatibility fixes are now part of the repo:

- `mod-wm-bridge` includes the DB query result header required by current AzerothCore headers
- the compatibility overlay disables Boost.Asio coroutine/concept support for the old Playerbots command server translation unit when building against Boost 1.87

## Manual Control Proposal Path

Manual and future LLM proposals use the same control action kind:

```json
{
  "kind": "native_bridge_action",
  "payload": {
    "native_action_kind": "debug_ping",
    "payload": {},
    "created_by": "manual",
    "risk_level": "low",
    "expires_seconds": 60
  }
}
```

Example proposal:

```powershell
python -m wm.control.validate --proposal control\examples\proposals\manual_native_debug_ping.json --summary
python -m wm.control.apply --proposal control\examples\proposals\manual_native_debug_ping.json --mode dry-run --summary
python -m wm.control.apply --proposal control\examples\proposals\manual_native_debug_ping.json --mode apply --confirm-live-apply --summary
python -m wm.control.audit --idempotency-key <key-from-apply-summary> --summary
```

Experimental scene play uses the same control/native path, but builds one proposal per step from bundled JSON under `control/scenes/`:

```powershell
python -m wm.control.scene_play --scene field_medic_pulse --player-guid 5406 --mode dry-run --summary
python -m wm.control.scene_play --scene summon_marker --player-guid 5406 --mode apply --confirm-live-apply --summary
python -m wm.control.scene_play --scene arcane_marker_demo --player-guid 5406 --mode dry-run --summary
```

Scene JSON is intentionally strict:

- every step must reference a registered, implemented native action kind
- payload must stay a JSON object
- risk levels must be `low`, `medium`, or `high`
- scene play is an operator wrapper over `manual_admin_action`, not a second executor

The validator rejects unknown native verbs before they reach the queue. Non-admin event-bound proposals also reject stale source events by default through `control/policies/direct_apply.json` `max_source_event_age_seconds=600`; build proposals from fresh `wm_event_log` rows instead of copying old example JSON for live apply.

Current control-native convergence status:

- `WORKING`: repo tests cover proposal validation, idempotency rejection, wrong-player rejection, stale-event rejection, audit row fetch/list, and native request extraction from `quest_grant` / `native_bridge_action` execution results.
- `WORKING`: BridgeLab control debug proof ran through `wm.control.validate`, `wm.control.apply`, and `wm.control.audit`; native `debug_ping` request `36` reached `done`.
- `WORKING`: repo tests cover Primitive Pack 1 payload contracts, policy-disabled defaults, WM-owned creature guards, `creature_spawn` synchronous object-id return, and `wm.control.scene_play` scene loading/summary behavior.
- `WORKING`: BridgeLab Primitive Pack 1 proof for player `5406` reached native requests `54-72` `done`:
  - `field_medic_pulse` completed restore -> aura -> announce
  - `summon_marker` completed spawn -> say -> emote -> despawn with spawn result `object_id=4`
  - `bonebound_battle_cry` completed spawn -> say -> emote -> buff
  - direct control applies proved `player_remove_aura`, `player_add_money`, `player_add_reputation`, and `player_add_item`
- `PARTIAL`: repo tests and BridgeLab native build cover Primitive Pack 2 contracts/guards for `player_cast_spell`, `player_set_display_id`, `creature_cast_spell`, `creature_set_display_id`, and `creature_set_scale`; `arcane_marker_demo` is available, but the first live apply stopped at request `83` with `player_not_online`, so visible behavior is not yet proven
- `WORKING`: fresh bounty `quest_grant` rerun on 2026-04-16 reached event `1599`, proposal `43`, and native `quest_add` request `74` `done`; `wm.control.audit` linked the source event to the native request/result, `wm.executor` recorded `quest_grant_issued` event `1601`, native bridge event `26505` recorded `quest/granted` for quest `910020`, and GM `.quest status 910020 Jecia` reported `Incomplete`

## Broad Action Vocabulary

The broad action vocabulary lives in:

- `src/wm/sources/native_bridge/action_kinds.py`
- `control/actions/native/native_bridge_action.json`

The C++ source is split by future capability area:

- `wm_bridge_player_actions.cpp`
- `wm_bridge_inventory_actions.cpp`
- `wm_bridge_quest_actions.cpp`
- `wm_bridge_creature_actions.cpp`
- `wm_bridge_gossip_actions.cpp`
- `wm_bridge_companion_actions.cpp`
- `wm_bridge_environment_actions.cpp`
- `wm_bridge_debug_actions.cpp`

This keeps future incremental builds smaller: most later work should be filling one capability file, not changing module layout or the queue contract.

## Next Native Action Hardening Order

Recommended order:

1. Keep the current bounty loop stable with native `quest_add` as the preferred grant transport and SOAP as fallback.
2. Harden `context_snapshot_request`, because it is observational and useful for debugging.
3. Add quest completion/reward verbs only after the native quest-granted/rewarded event chain is verified end-to-end.
4. Finish Primitive Pack 2 live proof for cast/display/scale through `arcane_marker_demo`.
5. Add item/spell/player/object verbs only after each has a dedicated lab test and policy default.

Do not enable broad mutation policy on the working realm until this sequence is green.
