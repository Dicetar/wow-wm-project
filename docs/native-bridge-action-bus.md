# Native Bridge Action Bus

The native action bus is the next WM bridge layer after native perception.

It lets WM enqueue one fixed, typed server action into `wm_bridge_action_request`, while `mod-wm-bridge` validates player scope and policy before executing it. C++ still does not plan, generate story, run arbitrary SQL, run GM commands, edit files, or decide cooldown policy. WM Python and the `control/` registry remain the brain.

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
- `context_snapshot_request`

Everything risky should be proven in `D:\WOW\WM_BridgeLab` before promotion.

## Tables

Core queue and gates:

- `wm_bridge_action_request`: one append-style action request with idempotency, status, payload, result, and error state.
- `wm_bridge_action_policy`: DB policy per action kind/profile with enabled flag, max risk, cooldown, burst limit, and admin-only flag.
- `wm_bridge_player_scope`: DB-backed live player allowlist.
- `wm_bridge_runtime_status`: native bridge heartbeat/status records.

Support tables staged for future capability bodies:

- `wm_bridge_world_object`
- `wm_bridge_companion`
- `wm_bridge_gossip_override`
- `wm_bridge_item_script`
- `wm_bridge_spell_intercept`
- `wm_bridge_spell_script`
- `wm_bridge_counter`
- `wm_bridge_chat_keyword`

## Lab Workflow

Create and build an isolated bridge lab instead of touching the working rebuild:

```powershell
.\setup-bridge-lab.bat
.\build-bridge-lab.bat
```

Create a DB copy for lab testing only when you explicitly want it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bridge_lab\New-BridgeLabDbCopy.ps1 -ConfirmCreateLabDbCopy
```

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
python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind debug_echo --idempotency-key lab-debug-echo-1 --payload-json '{\"text\":\"hello\"}' --wait --summary
```

Submit an intentional failure:

```powershell
python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind debug_fail --idempotency-key lab-debug-fail-1 --wait --summary
```

Expected result for `debug_fail`: status `failed`, with structured error text.

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
```

The validator rejects unknown native verbs before they reach the queue.

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

1. Prove `debug_ping`/`debug_echo`/`debug_fail` in `D:\WOW\WM_BridgeLab`.
2. Harden `context_snapshot_request`, because it is observational and useful for debugging.
3. Add one tiny mutation with easy rollback, such as `world_announce_to_player`.
4. Add `quest_add` as the first replacement for SOAP quest grant.
5. Add item/spell/player/object verbs only after each has a dedicated lab test and policy default.

Do not enable broad mutation policy on the working realm until this sequence is green.
