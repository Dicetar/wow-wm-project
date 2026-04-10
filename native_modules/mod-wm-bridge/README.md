# mod-wm-bridge

Thin native WM bridge for AzerothCore.

Responsibilities:

- observe server-truth hooks
- emit append-only raw rows into `wm_bridge_event`
- optionally process WM-owned rows from `wm_bridge_action_request`
- keep WM planning, cooldowns, and publishing outside the core

Default safety posture:

- the module is installed but inert by default
- `WmBridge.PlayerGuidAllowList = ""` emits nothing for every player
- `WmBridge.ActionQueue.Enable = 0` executes no native actions
- `WmBridge.DbControl.Enable = 0` avoids DB-scope queries until bootstrap SQL is present
- set `WmBridge.PlayerGuidAllowList = "5406"` to observe only that player
- or enable `WmBridge.DbControl.Enable = 1` and insert `5406` into `wm_bridge_player_scope`
- `WmBridge.Emit.Loot = 0` by default until the loot hook is hardened further
- `WmBridge.PlayerGuidAllowList = "*"` is available only for short debug runs

Live allowlist changes:

- edit `WmBridge.PlayerGuidAllowList`
- run `.reload config` in worldserver, or use WM SOAP helper:
  `python -m wm.sources.native_bridge.configure --player-guid 5406 --reload-via-soap --summary`
- clear observation with:
  `python -m wm.sources.native_bridge.configure --clear --reload-via-soap --summary`

Current emitted slice:

- `combat.kill`
- `quest.accepted`
- `quest.granted`
- `quest.completed`
- `quest.rewarded`
- `loot.item`
- `gossip.opened`
- `gossip.selected`
- `area.entered`

Native action bus:

- queue table: `wm_bridge_action_request`
- live player scope: `wm_bridge_player_scope`
- policy gates: `wm_bridge_action_policy`
- runtime heartbeat/status: `wm_bridge_runtime_status`
- queue robustness: request expiry, stale-claim recovery, max attempts, priority, and simple ordered sequences
- implemented native actions in this foundation pass: `debug_ping`, `debug_echo`, `debug_fail`, `context_snapshot_request`, `world_announce_to_player`
- broad mutation verbs are registered in WM Python/control contracts but remain policy-disabled and return `not_implemented` in C++ until each body has a lab test

Bridge lab build note:

- `.\incremental-bridge-lab.bat` resyncs the repo-owned `mod-wm-bridge` source into `D:\WOW\WM_BridgeLab` before running MSBuild, so fast native iterations do not require a full workspace rebuild just to pick up local bridge edits.

Queue timing fields:

- `ExpiresAt`: pending request deadline; pending rows become `expired` after this.
- `ClaimExpiresAt`: native execution lease; stale `claimed` rows return to `pending` until `MaxAttempts` is reached.
- `PurgeAfter`: Python cleanup hint only; C++ never deletes audit/debug rows automatically.
- `Priority`: `1` urgent, `5` normal, `9` background.
- `SequenceID`/`SequenceOrder`/`WaitForPrior`: optional manual/admin sequence ordering. Lower-order rows must be `done` before a waiting row runs.

Enable one-player lab action testing:

1. Apply `data/sql/world/updates/2026_04_10_00_wm_bridge_action_bus.sql`.
2. Set `WmBridge.DbControl.Enable = 1` and `WmBridge.ActionQueue.Enable = 1`.
3. Insert player scope through WM:
   `python -m wm.sources.native_bridge.actions_cli scope-player --player-guid 5406 --summary`
4. Submit a ping:
   `python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind debug_ping --idempotency-key lab-debug-ping-1 --wait --summary`

Submit a small ordered sequence:

```powershell
python -m wm.sources.native_bridge.actions_cli submit-sequence --player-guid 5406 --sequence-id lab-seq-1 --actions-json '[{"action_kind":"debug_ping"},{"action_kind":"debug_echo","payload":{"message":"after ping"}}]' --wait --summary
```

Inspect and maintain the queue:

```powershell
python -m wm.sources.native_bridge.actions_cli inspect --player-guid 5406 --limit 10 --summary
python -m wm.sources.native_bridge.actions_cli recover-stale --summary
python -m wm.sources.native_bridge.actions_cli cleanup --older-than-seconds 3600 --summary
```
