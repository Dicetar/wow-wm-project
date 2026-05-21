---
name: wm-native-smoke-test
description: Verify the native bridge is alive and processing actions, using the debug action kinds (debug_ping, debug_echo, debug_fail). Use this WHENEVER you've rebuilt/restarted the worldserver or native module, or before a live proof, to confirm the action bus actually executes before blaming content. Triggers: "is the bridge alive", "ping the native bridge", "smoke-test the action bus", "did the worldserver pick up the native module", "debug ping". The first thing to run when a bus action mysteriously sits pending.
---

# Native bridge smoke test

Before debugging why a grant/publish "didn't work," confirm the bus itself is
processing. The bridge implements three debug actions (`implemented=True`,
`admin_only`, `default_enabled`): `debug_ping` (returns a health pong),
`debug_echo` (echoes its payload), `debug_fail` (intentionally fails — exercises
catch-and-park). They're in the freeform-allowed set, so no content gates apply.

Runs under **wm-live-bridge-lab** (runtime/scope).

## Ping (the one-liner)
```sql
INSERT INTO wm_bridge_action_request
  (IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel)
VALUES ('wm.smoke.ping:<ts>', 5408, 'debug_ping', '{}', 'pending', 'wm-slice', 'low');
```
Then poll:
```sql
SELECT Status, ResultJSON, ErrorText FROM wm_bridge_action_request
WHERE IdempotencyKey = 'wm.smoke.ping:<ts>';
-- Status='done' with a pong result  -> the bridge is alive and processing.
```
`debug_echo` takes a freeform `payload` and returns it; `debug_fail` always lands
`failed` (use it to confirm catch-and-park routes errors to the issues queue, not
a crash).

## Audited path (alternative)
A native action can also be applied through the control proposal pipeline as a
`control.proposal.v1` with `action.kind="native_bridge_action"`,
`payload={"native_action_kind":"debug_ping","payload":{}}` (see
`tests/test_control_apply_cli.py`). Use that when you want the full
proposal/audit trail; the raw insert above is fine for a quick check.

## What a result tells you
- **`done` / pong** → bridge healthy; if a real action still fails, it's the
  action's own preconditions (allowlist, online, implemented?), not the bus.
- **Stuck `pending`** → the watcher/queue poller isn't running, or the player
  isn't allow-listed (debug_ping is admin/scope-checked too) → restart/allowlist.
- **`failed` on debug_ping** (not debug_fail) → native module not loaded/healthy;
  rebuild + restart the worldserver.

## Gotchas
- Treat a stuck debug_ping as "the bus is down," and fix that before touching content.
- `debug_*` are admin/testing-only; don't ship them in player-facing proposals.
