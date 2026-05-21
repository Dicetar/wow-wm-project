---
name: wm-grant-quest
description: Push an existing quest into a specific character's quest log via the native action bus. Use this WHENEVER you want the WM to give a player a quest directly (no NPC offer) — granting a managed quest you just published, advancing an arc beat, or handing out a bounty. Triggers: "grant quest X to character Y", "give the player this quest", "push quest to character", "add quest to their log". The quest must already exist on the server (see wm-create-quest first).
---

# Grant a quest to a character

Enqueues a `quest_add` action on the native action bus
(`wm_bridge_action_request`). The worldserver's queue poller picks it up and
adds the quest to the **online** player's log — the same effect as a GM
`.quest add`, but driven by the WM with full audit + idempotency.

## Prerequisites
- **The target GUID is on `WmBridge.PlayerGuidAllowList`.** The native bridge
  only executes actions for allow-listed characters; for anyone else the action
  is skipped (you'll see a guid/allowlist mismatch result, not `done`). The list
  lives in `D:\WOW\WM_BridgeLab\run\configs\modules\mod_wm_bridge.conf` (e.g.
  `WmBridge.PlayerGuidAllowList = "5406,5405,5408"`). Add the GUID via
  `scripts/bridge_lab/Configure-BridgeLabRuntime.ps1 -WmBridgePlayerGuidAllowList "...,<guid>"`
  (or edit the conf), then **restart the worldserver** — the allowlist is read
  at startup, not hot-reloaded.
- The quest **exists in `quest_template`** and the worldserver has been
  reloaded (use **wm-create-quest** if it doesn't).
- The **player must be online** — the bus returns `player_not_online` otherwise
  (state lives in memory; a save flushes it to `character_queststatus`).
- You know the character GUID. Discover the active WM character from the marker
  aura's `applied` event on `wm_bridge_event` — do **not** peek
  `acore_characters.characters` to "look up" a name.

## Do it (Python seam — preferred)
`NativeApplier` builds the row with the right idempotency key:
```python
from wm.db.mysql_cli import MysqlCliClient
from wm.cli.native_applier import NativeApplier
applier = NativeApplier(client=MysqlCliClient(), host="127.0.0.1", port=33307,
                        user="acore", password="acore", database="acore_world")
applier.insert_quest_add(character_guid=5408, quest_id=910500,
                         idempotency_key="slice.quest_grant:b00:910500:5408")
```
Idempotency key convention: `slice.quest_grant:<beat-or-source>:<quest_id>:<guid>`.
Re-using a key that already succeeded will **collide** (unique constraint) — use a
fresh key, or delete the prior `wm-slice` row, to re-grant.

## Raw SQL form (if you can't run Python)
```sql
INSERT INTO wm_bridge_action_request
  (IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel)
VALUES ('slice.quest_grant:b00:910500:5408', 5408, 'quest_add',
        '{"quest_id":910500}', 'pending', 'wm-slice', 'low');
```

## Verify it landed
```sql
SELECT Status, ResultJSON, ErrorText FROM wm_bridge_action_request
WHERE IdempotencyKey = 'slice.quest_grant:b00:910500:5408';
-- Status='done', ResultJSON message="quest_added"  -> in the player's log
```
`character_queststatus` may stay empty until a `.saveall` (SOAP) or logout, since
AzerothCore holds character state in memory.

## Gotchas
- **Row never leaves `pending` / guid mismatch** → the GUID isn't on
  `WmBridge.PlayerGuidAllowList`; add it and restart the worldserver.
- `player_not_online` → log the character in, then re-enqueue.
- `Duplicate entry ... uq_..._idem` → the key was used before; pick a new one.
- Bus result `failed` with "already completed" → the player already finished that
  quest. Grant a fresh managed quest instead (see wm-create-quest).
