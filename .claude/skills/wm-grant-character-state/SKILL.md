---
name: wm-grant-character-state
description: Adjust a character's state through the native bus — money, reputation, health/power, or auras. Use this WHENEVER the WM should change a player's standing or vitals directly (reward copper, bump faction rep, heal, apply/remove a buff). Triggers: "give the player gold/copper", "add reputation with faction X", "heal the character", "apply/remove an aura", "grant money reward". IMPORTANT: only a subset of player_* actions are actually implemented by the bridge — this skill calls out which.
---

# Grant character-state changes

These enqueue native-bus actions (`wm_bridge_action_request`) the worldserver
applies to the **online**, allow-listed player. Same enqueue mechanics as
**wm-grant-item** (idempotency key, `CreatedBy='wm-slice'`, player online,
GUID on `WmBridge.PlayerGuidAllowList`).

## What the bridge ACTUALLY implements (safe to use)
Per `src/wm/sources/native_bridge/action_kinds.py` (`implemented=True`):

| Action | Effect | Payload (verified where noted) |
|---|---|---|
| `player_apply_aura` | apply a buff/aura | `{"spell_id": <id>, "duration": -1}` (−1 persistent) — **verified** |
| `player_remove_aura` | remove an aura | `{"spell_id": <id>}` |
| `player_add_money` | grant copper | amount in copper — confirm key in `test_native_bridge_actions.py` |
| `player_add_reputation` | adjust faction standing | faction + value — confirm keys in the same tests |
| `player_restore_health_power` | heal / restore power | — |
| `player_cast_spell` / `player_learn_spell` / `player_unlearn_spell` | cast/teach/remove a spell | `{"spell_id": <id>}` |
| `player_set_display_id` | change model | `{"display_id": <id>}` |

Example (money):
```sql
INSERT INTO wm_bridge_action_request
  (IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel)
VALUES ('wm.reward.money:5408:<ts>', 5408, 'player_add_money',
        '{"copper":1234}', 'pending', 'wm-slice', 'medium');
```
> The exact money/reputation payload keys are interpreted by the C++ bridge —
> confirm them against `tests/test_native_bridge_actions.py` before relying on a
> specific key. `player_apply_aura` is the one verified end-to-end this session.

## Registered but NOT implemented (the bridge will NOT execute — do not use yet)
`player_add_xp`, `player_remove_money`, `player_set_phase` / `player_clear_phase`,
`player_teleport`, `player_summon_to_location`, `player_resurrect`,
`player_set_speed`, `player_equip_item`, `player_create_bound_item`,
`player_send_mail` / `player_send_mail_with_items`, `player_add_title` /
`player_remove_title`, `player_add_achievement_credit`, `player_show_menu`,
`player_close_gossip`, `player_play_sound`, `player_play_movie`.

If you need one of these, it's a **native-bridge implementation task**, not
something a bus row will satisfy today — flag it rather than enqueuing a row that
sits unprocessed.

## Verify
```sql
SELECT Status, ResultJSON, ErrorText FROM wm_bridge_action_request
WHERE IdempotencyKey = '<your key>';
```

## Gotchas
- Enqueued an unimplemented action → the row won't process to `done`; check the
  implemented list above first.
- `player_not_online` / guid-allowlist mismatch → same as the other grant skills.
