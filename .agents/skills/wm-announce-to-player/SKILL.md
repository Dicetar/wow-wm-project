---
name: wm-announce-to-player
description: Send a server announcement / system message to a specific player via the native bus. Use this WHENEVER the WM should surface a line of text to the player out-of-band — a regard whisper, a beat acknowledgement, a reactive callout. Triggers: "announce to the player", "send a system message", "show the player a line of text", "WM says something to character X", "server message to player Y". A lightweight, low-risk way to make the WM's presence felt.
---

# Announce to a player

Enqueues a `world_announce_to_player` action (implemented ✓, `environment`, low
risk) — a scoped server announcement to one online player. Same enqueue
mechanics/allowlist/online rules as the other grant skills; runs under
**wm-live-bridge-lab**.

## Do it
```python
from wm.db.mysql_cli import MysqlCliClient
from wm.cli.native_applier import NativeApplier
applier = NativeApplier(client=MysqlCliClient(), host="127.0.0.1", port=33307,
                        user="acore", password="acore", database="acore_world")
applier._insert_action_request(
    idempotency_key="wm.announce:5408:<ts>",
    player_guid=5408, action_kind="world_announce_to_player",
    payload={"message": "The regard has taken your measure."})
```
> Payload key is `message` (as used throughout `wm.content.release` /
> `wm.living`); confirm in `src/wm/content/release.py` if a variant is needed.

## Use it for "hidden mechanic → visible signal"
Per **wm-content-release**, hidden server behavior should pair with a visible
signal. A `world_announce_to_player` is one of the cheapest visible
acknowledgements (alongside an aura/buff or quest), so the player perceives that
the WM reacted — useful right after an approved proposal applies.

## Verify
`SELECT Status, ResultJSON FROM wm_bridge_action_request WHERE IdempotencyKey='wm.announce:5408:<ts>';`

## Gotchas
- Player offline → `player_not_online`; the message isn't queued for later.
- It's a transient chat line, not persistent state — for lasting signal use an
  aura/quest/journal entry too.
