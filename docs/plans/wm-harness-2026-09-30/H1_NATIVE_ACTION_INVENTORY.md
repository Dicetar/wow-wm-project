Status: PARTIAL
Last reviewed: 2026-09-30
Evidence: source inventory, 82 focused tests passed, BridgeLab worldserver build succeeded twice; live recovery unproven
Doc type: audit

# H1 Native Action Retry Inventory

The queue receipt is in the world DB (`wm_bridge_action_request`). An action's actual effect can be in character DB, world DB, live server memory, or the player's client. `CompleteAction` writes the receipt separately. The gap between effect and receipt makes a timed-out claim ambiguous. Request idempotency prevents a second *submission with the same key*, but did not prevent the old lease recovery from replaying the same row.

All implemented actions registered in `wm_bridge_*_actions.cpp` are covered below. `uncertain` means hold and reconcile; it does not mean the effect failed. The only automatic retry allowlist is `debug_ping`, `debug_echo`, `debug_fail`, whose handlers only write the receipt.

| Action kinds | Effect location | Reconciliation evidence | Crash/retry judgment |
|---|---|---|---|
| `debug_ping`, `debug_echo`, `debug_fail` | World DB receipt only | Request status/result | Retry under `MaxAttempts`; no gameplay effect. |
| `player_add_item`, `player_remove_item`, `player_random_enchant_item` | Character DB inventory/item instance, plus live player inventory | Compare player inventory/item instance and enchant state with pre-effect snapshot; inspect request and character DB transaction | **Uncertain.** `player_add_item` commits `SaveInventoryAndGoldToDB` before `CompleteAction`; repeating can grant twice. Removal/enchant also commit separately. Item count alone may not prove which request changed it. |
| `player_send_mail` | Character DB mail | Inspect recipient mail and exact message attributes; correlate timestamps/request | **Uncertain.** Mail transaction commits before world DB receipt; replay can send duplicate mail. |
| `player_add_money`, `player_add_reputation`, `player_restore_health_power` | Live player state, later character DB persistence | Compare character state to pre-effect snapshot, native events, and request | **Uncertain.** Additive effects cannot be replayed from a missing receipt. Healing is bounded but still an effect. |
| `player_apply_aura`, `player_remove_aura`, `player_cast_spell`, `player_learn_spell`, `player_unlearn_spell`, `player_add_title`, `player_remove_title`, `player_set_display_id`, `player_play_sound` | Live player/client and sometimes character DB | Inspect scoped player aura/spell/title/display state and event/receipt; sound may have no durable trace | **Uncertain.** Some set-like operations may appear repeatable, but casting and client-visible effects can trigger secondary effects. Do not generalize replay safety. |
| `quest_add`, `quest_remove`, `quest_complete`, `quest_fail` | Player quest state and character DB | Inspect character quest status/objectives and request, including whether a reward was indirectly triggered | **Uncertain.** Quest transitions can be consequential even when final status looks the same. |
| `wm_counter_set`, `wm_counter_increment`, `wm_counter_clear` | World DB WM counters and quest progression | Inspect counter row, source event, and request | **Uncertain.** Increment is plainly additive; set/clear may trigger downstream quest state. |
| `creature_spawn`, `creature_despawn`, `creature_say`, `creature_emote`, `creature_cast_spell`, `creature_set_display_id`, `creature_set_scale`, `creature_set_name`, `creature_set_faction`, `creature_set_health_pct`, `creature_set_react_state`, `creature_yell`, `creature_whisper_player`, `creature_move_to`, `creature_follow_player`, `creature_stop_movement`, `creature_attack_player`, `creature_attack_target` | Live map and `wm_bridge_world_object` for owned spawns | Inspect owned-object row, live GUID, map presence, target/player state, and request | **Uncertain.** Spawn can occur before its owned-object row/receipt. Speech, spells, and attacks are not replay-safe; set-like operations still require live-object identity. |
| `gameobject_spawn`, `gameobject_despawn`, `gameobject_set_state` | Live map and `wm_bridge_world_object` | Inspect owned-object row, live GUID/state, map presence, and request | **Uncertain.** Summon and row insertion/receipt are separate. |
| `companion_spawn`, `companion_despawn`, `companion_set_state`, `companion_follow`, `companion_wait`, `companion_move_to`, `companion_say`, `companion_whisper`, `companion_emote` | Live map, `wm_bridge_world_object`, `wm_bridge_companion` | Inspect companion key, active GUID, owned-object row, map state, and request | **Uncertain.** Spawn and persistence are multi-step; speech/movement can already have happened. |
| `context_snapshot_request` | World DB snapshot/request rows | Inspect snapshot by request ID and timestamp | **Uncertain pending proof.** Read-only sensing still writes a snapshot; duplicate snapshots can mislead downstream consumers. |
| `world_announce_to_player`, `player_chat_message`, `player_close_gossip` | Client-visible transient effect; possible chat/event rows | Inspect event records where available and ask whether player saw it | **Uncertain.** No reliable durable per-delivery proof. |

## Recovery Contract

- Python maintenance and native polling use the same three-action retry allowlist. All other expired claims, including debug actions at `MaxAttempts`, become `uncertain` and are retained for operator inspection. Terminal cleanup deliberately excludes `uncertain`.
- Waiting sequence rows require predecessors to be `done`. An `uncertain` predecessor holds the sequence; a later completion can resolve it. An operator must reconcile or explicitly dispose of an orphaned sequence.
- A late `CompleteAction` may replace `uncertain` with the worker's actual result. It cannot overwrite a row that was otherwise moved to a different status.
- This is a **containment fix**, not exactly-once execution. The poller now writes a unique `ClaimToken` with a synchronous conditional claim update and dispatches only if a read-back returns its token. Two pollers selecting the same row cannot both dispatch. The token migration must precede the binary rollout. Effect/receipt atomicity across databases remains unsolved.
- No automatic compensation or new request key is created for an uncertain effect. Reconciliation must inspect the domain effect and preserve the original request identity.

## Next Proof

The initial full suite ran at 1,263 passed / 5 failed. After the H1 test fixture was corrected, two consecutive full runs were 1,263 passed / 5 failed and 1,264 passed / 4 failed. Four failures are in the already-dirty autoplay draft tests; the intermittent fifth was a Windows `PermissionError` replacing an autoplay temp state file. No full-suite green claim is made. The H1-focused suite passed at 82 tests before and after claim fencing. The incremental BridgeLab worldserver build succeeded before and after claim fencing with one unrelated duplicate-symbol warning and `-NoStageRuntime`; no binary was deployed or server restarted.

Before live proof, close or explicitly isolate the red test baseline. Then apply the additive claim-token migration, stage/restart in a controlled lab window, and exercise two-poller claim contention plus lease expiry without rewards: debug retry, non-debug uncertainty, sequence hold, late completion, and no duplicate effect. Domain-specific reconciliation remains needed before claiming H1 complete.
