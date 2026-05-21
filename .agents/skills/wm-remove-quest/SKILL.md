---
name: wm-remove-quest
description: Remove a quest from a specific character's log via the native bus. Use this WHENEVER the WM should pull a quest back from a player — abandoning a mis-granted quest, resetting an arc beat, or cleaning a test grant. Triggers: "remove quest X from character Y", "abandon the player's quest", "take back the quest I granted", "clear quest from their log". NOTE: completing/turning in a quest is NOT a bus action — the player does that in-game.
---

# Remove a quest from a character

Enqueues a `quest_remove` action (implemented ✓) on the native bus; the
worldserver removes it from the **online** player's log. Same enqueue mechanics,
allowlist, and online requirement as **wm-grant-quest**.

## What is NOT available
- `quest_complete` / `quest_complete_objective` / `quest_reward` are **registered
  but NOT implemented** in the bridge. You cannot force-complete or turn in a
  quest via the bus — the player completes it in-game (which is what fires the
  `quest_completed` event the arc/watcher react to). Don't enqueue these; the row
  will sit `pending`.

## Do it
```python
from wm.db.mysql_cli import MysqlCliClient
from wm.cli.native_applier import NativeApplier
applier = NativeApplier(client=MysqlCliClient(), host="127.0.0.1", port=33307,
                        user="acore", password="acore", database="acore_world")
applier._insert_action_request(
    idempotency_key="wm.quest_remove:910500:5408",
    player_guid=5408, action_kind="quest_remove",
    payload={"quest_id": 910500})
```
Raw SQL: same `wm_bridge_action_request` insert with `ActionKind='quest_remove'`,
`PayloadJSON='{"quest_id":910500}'`.

## Prerequisites & verify
- GUID on `WmBridge.PlayerGuidAllowList`; player online. (See wm-grant-quest.)
- Verify: `SELECT Status, ResultJSON FROM wm_bridge_action_request WHERE IdempotencyKey='wm.quest_remove:910500:5408';`

## Gotchas
- Row stuck `pending` → GUID not allow-listed, or player offline.
- Wanted to "finish" the quest for the player → not possible via bus; only removal.
