---
name: wm-remove-item
description: Remove an item from a character's bags via the native bus. Use this WHENEVER the WM should take an item back — reclaiming a quest token, cleaning a mis-granted item, or resetting a test inventory. Triggers: "remove item X from character Y", "take back the item I granted", "delete the token from their bags", "clear the item from the player". Counterpart to wm-grant-item.
---

# Remove an item from a character

Enqueues a `player_remove_item` action (implemented ✓) on the native bus; the
worldserver removes it from the **online** player's inventory. Same enqueue
mechanics, allowlist, and online requirement as **wm-grant-item**.

## Do it
```python
from wm.db.mysql_cli import MysqlCliClient
from wm.cli.native_applier import NativeApplier
applier = NativeApplier(client=MysqlCliClient(), host="127.0.0.1", port=33307,
                        user="acore", password="acore", database="acore_world")
applier._insert_action_request(
    idempotency_key="wm.item_remove:910500:5408",
    player_guid=5408, action_kind="player_remove_item",
    payload={"item_id": 910500, "count": 1})
```
Raw SQL: same `wm_bridge_action_request` insert with `ActionKind='player_remove_item'`.
> Payload mirrors `player_add_item` (`item_id`, `count`); confirm against
> `tests/test_native_bridge_actions.py` if a count edge case matters.

## Prerequisites & verify
- GUID on `WmBridge.PlayerGuidAllowList`; player online (else `player_not_online`).
- `SELECT Status, ResultJSON FROM wm_bridge_action_request WHERE IdempotencyKey='wm.item_remove:910500:5408';`

## Gotchas
- Player doesn't have the item → result reflects nothing removed; not a bus error.
- Row stuck `pending` → GUID not allow-listed, or queue/worldserver not running
  (smoke-test with **wm-native-smoke-test**).
