---
name: wm-mark-for-attention
description: Activate a character for the WM by applying the marker aura (spell 946500), which the bridge emits as an "applied" event the aura sentinel turns into wm.attention.granted. Use this WHENEVER you want the WM to start watching/driving a specific character — kicking off the slice, onboarding a demo char, or re-marking someone. Triggers: "mark this character for attention", "activate the WM on character X", "apply the attention marker", "start the WM watching player Y", "kick off the slice on guid Z".
---

# Mark a character for WM attention

The WM's first-class activation signal is the **marker aura, spell 946500**
("WM: Marked for Attention"). When applied to a player, the native bridge emits
an `EventFamily='aura' EventType='applied'` row on `wm_bridge_event`; the aura
sentinel (`BridgeEventPump`) sees `spell_id=946500` and fires
`wm.attention.granted` into the runtime, which starts the arc (b00). This — not
a starter item — is the activation trigger.

## Prerequisites
- Target GUID on `WmBridge.PlayerGuidAllowList` **and** `WmSpells.PlayerGuidAllowList`
  (it's an aura via the spells module), set in the BridgeLab confs + worldserver
  restart. See **wm-grant-ability** / **wm-reload-worldserver**.
- **946500 must be in `WmBridge.Emit.AuraSpellAllowList`** — that's what makes the
  bridge emit the `applied` event the sentinel keys on. (Already set on BridgeLab:
  `"946602,132,687,770,946500"`.) Without it the aura applies but no event fires,
  so the WM never notices.
- The marker spell exists server-side. (On BridgeLab it's a testing-only
  `acore_world.spell_dbc` row — fine for the marker; player-facing ability spells
  follow the shell-bank path, ADR 0003.)
- Player online.

## Apply it (native bus — verified payload)
```python
from wm.db.mysql_cli import MysqlCliClient
from wm.cli.native_applier import NativeApplier
applier = NativeApplier(client=MysqlCliClient(), host="127.0.0.1", port=33307,
                        user="acore", password="acore", database="acore_world")
applier._insert_action_request(
    idempotency_key="wm.mark.attention:5408:<unix-ts>",
    player_guid=5408, action_kind="player_apply_aura",
    payload={"spell_id": 946500, "duration": -1})   # -1 = persistent
```
Raw SQL equivalent:
```sql
INSERT INTO wm_bridge_action_request
  (IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel)
VALUES ('wm.mark.attention:5408:<ts>', 5408, 'player_apply_aura',
        '{"spell_id":946500,"duration":-1}', 'pending', 'wm-slice', 'low');
```

## GM alternative (in-client)
A GM can apply it directly in the client console: `.aura 946500`. Same effect —
the bridge emits the `applied` event either way.

## Verify
```sql
-- the bridge applied it:
SELECT Status, ResultJSON FROM wm_bridge_action_request
WHERE IdempotencyKey LIKE 'wm.mark.attention:5408:%' ORDER BY RequestID DESC LIMIT 1;
-- the sentinel-visible event landed:
SELECT BridgeEventID, EventType FROM wm_bridge_event
WHERE EventFamily='aura' AND EventType='applied' AND PlayerGUID=5408
  AND PayloadJSON LIKE '%"spell_id":946500%' ORDER BY BridgeEventID DESC LIMIT 1;
```
Then bootstrap/poll the slice (panel **Slice** tab → Bootstrap → Poll) and b00
should advance.

## Gotchas
- Aura applies but the WM never reacts → 946500 not in `Emit.AuraSpellAllowList`,
  so no `applied` event fired.
- Row stuck `pending`/guid mismatch → GUID not on the bridge/spells allowlists.
- Client tooltip shows a placeholder ("Caster Centered AOE 0001") → cosmetic;
  the marker still works server-side. A real client patch would fix the art.
