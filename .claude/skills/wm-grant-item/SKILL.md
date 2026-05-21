---
name: wm-grant-item
description: Push an item into a specific character's bags via the native action bus. Use this WHENEVER the WM should give a player an item directly — a quest reward, a starter token, a managed power item, or any inventory grant. Triggers: "grant item X to character Y", "give the player this item", "push item to character", "add item to their bags", "mail them the item". The item must already exist on the server (see wm-create-item first).
---

# Grant an item to a character

Enqueues a `player_add_item` action on the native bus
(`wm_bridge_action_request`); the worldserver queue poller adds it to the
**online** player's inventory.

## Prerequisites
- The item **exists in `item_template`** and the worldserver was reloaded
  (use **wm-create-item** if not).
- The **player is online** (else `player_not_online`).
- Bags have room (else the grant fails / mails depending on server behavior —
  for guaranteed delivery to an offline or full-bag player, use mail instead).

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

## Mail variant (offline-safe)
Use `action_kind="player_send_mail_with_items"` with a payload carrying subject,
body, and item list — delivers via the mailbox so it survives offline / full bags.

## Verify
```sql
SELECT Status, ResultJSON, ErrorText FROM wm_bridge_action_request
WHERE IdempotencyKey = 'slice.item_grant:humming_token:910500:5408';
```

## Gotchas
- `player_not_online` → log in and re-enqueue, or use the mail variant.
- Duplicate idempotency key → pick a fresh one.
- Item entry unknown to the server → reload (wm-create-item step 4 analog) first.
