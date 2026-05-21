---
name: wm-spawn-creature
description: Spawn and lightly control an NPC/creature in the world via the native bus — spawn, despawn, set display/scale, say, emote, cast a spell. Use this WHENEVER the WM should place or animate a creature for a scene or encounter. Triggers: "spawn a creature/NPC", "despawn that mob", "make the NPC say/emote something", "set the creature's model/scale", "have the creature cast a spell". Only a verified subset of creature actions is implemented — this skill lists exactly which.
---

# Spawn / control a creature

Enqueues `creature_*` native-bus actions. Runs under **wm-live-bridge-lab**
(scope/runtime) — player/scope rules and online/world state apply.

## Implemented (safe to use) — per `action_kinds.py` `implemented=True`
| Action | Effect |
|---|---|
| `creature_spawn` | spawn a creature (by template entry, at a location) |
| `creature_despawn` | remove a spawned creature |
| `creature_set_display_id` | change its model |
| `creature_set_scale` | change its size |
| `creature_say` | local-chat line |
| `creature_emote` | play an emote |
| `creature_cast_spell` | have it cast a spell |

Example (spawn):
```sql
INSERT INTO wm_bridge_action_request
  (IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel)
VALUES ('wm.creature_spawn:<key>', 5408, 'creature_spawn',
        '{"creature_entry":<entry>, ...location...}', 'pending', 'wm-slice', 'medium');
```
> Exact payload keys (entry, position, orientation, despawn timer) are interpreted
> by the C++ bridge — confirm against `tests/test_native_bridge_actions.py` /
> `mod-wm-bridge` before relying on a specific key. I have not run creature spawn
> end-to-end this session.

## Registered but NOT implemented (do NOT use — row will sit pending)
`creature_set_name`, `creature_set_subname`, `creature_set_faction`,
`creature_set_npc_flags`, `creature_set_health_pct`, `creature_set_phase`,
`creature_move_to`, `creature_follow_player`, `creature_stop_movement`,
`creature_set_waypoints`, `creature_yell`, `creature_whisper_player`,
`creature_attack_target`, `creature_attack_player`, `creature_flee`,
`creature_evade`, `creature_set_react_state`. (Movement/faction/aggro control is
a native-bridge implementation task, not a bus row today.)

## Gotchas
- Used a movement/faction action → not implemented; nothing happens.
- New `creature_template` (a brand-new NPC definition) is a separate, partial
  capability — spawning uses existing templates.
