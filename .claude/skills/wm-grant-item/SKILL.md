---
name: wm-grant-item
description: Push an item into a specific character's bags via the native action bus. Use this WHENEVER the WM should give a player an item directly — a quest reward, a starter token, a managed power item, or any inventory grant. Triggers: "grant item X to character Y", "give the player this item", "push item to character", "add item to their bags", "mail them the item". The item must already exist on the server (see wm-create-item first).
---

# Grant an item to a character

Enqueues a `player_add_item` action on the native bus
(`wm_bridge_action_request`); the worldserver queue poller adds it to the
**online** player's inventory.

## Prerequisites
- **The target GUID is on `WmBridge.PlayerGuidAllowList`** (in
  `D:\WOW\WM_BridgeLab\run\configs\modules\mod_wm_bridge.conf`). The bridge skips
  actions for non-allow-listed characters. Add via
  `Configure-BridgeLabRuntime.ps1 -WmBridgePlayerGuidAllowList "...,<guid>"` and
  **restart the worldserver** (allowlist is read at startup).
- The item **exists in `item_template`** and the worldserver was reloaded
  (use **wm-create-item** if not).
- The **player is online** (else `player_not_online`).
- Bags have room (else the grant fails depending on server behavior).

## Do it (Python seam)
```python
from wm.db.mysql_cli import MysqlCliClient
from wm.cli.native_applier import NativeApplier
applier = NativeApplier(client=MysqlCliClient(), host="127.0.0.1", port=33307,
                        user="acore", password="acore", database="acore_world")
applier._insert_action_request(
    idempotency_key="slice.item_grant:humming_token:910500:5408",
    player_guid=5408, action_kind="player_add_item",
    payload={"item_id": 910500, "count": 1})
```

## Raw SQL form
```sql
INSERT INTO wm_bridge_action_request
  (IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel)
VALUES ('slice.item_grant:humming_token:910500:5408', 5408, 'player_add_item',
        '{"item_id":910500,"count":1}', 'pending', 'wm-slice', 'low');
```

## Mail variant — NOT available yet
`player_send_mail_with_items` is **registered but NOT implemented** in the native
bridge (`action_kinds.py` has no `implemented=True`). A bus row for it will sit
unprocessed — do **not** use it as an offline-delivery path today. Wiring it is a
native-bridge task. For now, grant to an online player via `player_add_item`
(above). (`player_equip_item` and `player_create_bound_item` are likewise not
implemented yet.)

## Verify
```sql
SELECT Status, ResultJSON, ErrorText FROM wm_bridge_action_request
WHERE IdempotencyKey = 'slice.item_grant:humming_token:910500:5408';
```

## Gotchas
- Row stuck `pending` / guid mismatch → GUID not on `WmBridge.PlayerGuidAllowList`
  (add + restart worldserver).
- `player_not_online` → log in and re-enqueue (no working offline/mail fallback yet).
- Duplicate idempotency key → pick a fresh one.
- Item entry unknown to the server → reload (wm-create-item step 4 analog) first.
