Status: DESIGN_ONLY
Last verified: 2026-05-17
Verified by: Claude
Doc type: design

# Native Capability Expansion V1

## Why

"Go wide early": the native action vocabulary is already broad (99 registered
kinds) but only 26 have C++ bodies and, until now, only 18 had an enforceable
payload contract. The cheap, early, offline work is the **contract + validator
layer** so every verb is precise and pre-flight-validated before the expensive,
lab-gated C++ pass. This doc batches the remaining C++ hook work by the roadmap
feature it unlocks so the lab passes are efficient, not piecemeal.

State after this change: payload contracts cover 54/99 kinds (was 18); a
Python validator enforces them in `NativeBridgeActionClient.submit` before
enqueue; `wm native.contracts` lints coverage. C++ bodies remain operator/lab
work — every contracted-but-unimplemented verb returns `not_implemented` until
hardened in `D:\WOW\WM_BridgeLab`, per ADR-0002 and the no-parallel-runner rule.

## Architecture rule (unchanged)

New native capability = a new/expanded `action_kind` body on the existing
`wm_bridge_action_request` bus. No parallel C++ runner. Python owns the
contract and validation; C++ validates scope+policy again and executes. Each
verb stays policy-disabled by default and is proven in the lab before any
status label moves off `not_implemented`.

## C++ hook batches (priority order = feature value)

### Batch 1 — Nemesis / hostile scene (highest product value)
Kinds: `creature_set_name`, `creature_set_subname`, `creature_set_faction`,
`creature_set_health_pct`, `creature_attack_player`, `creature_attack_target`,
`creature_set_react_state`, `creature_yell`.
Unlocks: Nemesis (named escalating elite that remembers and ambushes the
player). Hook surface: extends the existing `creature_*` scoped-ownership path
in `mod-wm-bridge` (already has spawn/despawn/say/cast). Reuses
`wm_bridge_world_object` ownership; no new chassis.

### Batch 2 — Local Legend / rewards-as-recognition
Kinds: `player_add_title`, `player_remove_title`, `player_send_mail`,
`player_send_mail_with_items`, `player_play_sound`.
Unlocks: Local Legend (visible title + rumor-letter mail), reward punctuation.
Hook surface: player-scoped; mail reuses standardized WM-managed item ids.

### Batch 3 — Oath / hidden progress state
Kinds: `wm_counter_set`, `wm_counter_increment`, `wm_counter_clear`,
`quest_complete_objective`, `quest_complete`, `quest_fail`.
Unlocks: Oath/Contract (tracked constraint -> grant/revoke), arc objective
control. Hook surface: WM-owned counter table + the existing quest path that
already does `quest_add`/`quest_remove`.

### Batch 4 — Companions
Kinds: `companion_spawn`, `companion_despawn`, `companion_follow`,
`companion_say`, `companion_emote`, `companion_move_to`, `companion_set_state`,
`companion_wait`, `companion_whisper`, `companion_set_gossip`.
Unlocks: roadmap Companion Pack. Hook surface: a companion-scoped variant of
the proven `creature_*` ownership path; owner-scoped lifetime.

### Batch 5 — Deployables / scene objects
Kinds: `gameobject_spawn`, `gameobject_despawn`, `gameobject_set_state`,
`creature_move_to`, `creature_follow_player`, `creature_stop_movement`,
`area_trigger_marker_set`, `area_trigger_marker_clear`.
Unlocks: Live Scene Director (deployables beyond Bone Lure, marked ground).
Hook surface: GO ownership mirror of `wm_bridge_world_object`.

### Batch 6 — Conversation steering surface
Kinds: `gossip_override_set/clear`, `gossip_option_add/remove`,
`npc_text_override_set/clear`, `player_show_menu`, `player_close_gossip`.
Unlocks: roadmap conversation steering as a *visible* mechanic (still no
freeform command lane — only registered contracts). Highest design risk;
schedule after Batches 1-3 prove the contract→C++ loop.

### Deferred / low priority
`zone_set_weather` + `zone_clear_weather_override` (blocked until a real native
weather executor exists — known limitation), `player_teleport`,
`player_summon_to_location`, `player_set_speed`, `player_set_phase`,
`player_play_movie`, social (`group_*`, `duel_request_hint`,
`guild_message_to_player`), `player_add_xp`, `player_add_achievement_credit`,
`player_create_bound_item`, `player_equip_item`, `creature_set_waypoints`,
`creature_flee`, `creature_evade`. Contract these on demand when a feature
needs them; do not pre-implement C++ speculatively.

## Per-verb implementation gate (every batch)

1. Payload contract exists (`native_bridge_action.json`) and `wm
   native.contracts` is clean.
2. C++ body added to the existing bus dispatch; returns explicit result/error
   JSON; validates scope + policy.
3. Policy seed row stays disabled by default.
4. Proven in BridgeLab with a scoped request id reaching `done`; status moved
   off `not_implemented` only then.
5. `action_kinds.py` `implemented=True` flip + a repo test asserting the
   contract for that verb.

## Verification

- `python -m pytest -q` green (validator + coverage tests).
- `wm native.contracts` exit 0 (no orphan / no implemented-without-contract).
- `wm panel` CONTRACTS line shows the rising implemented/total ratio per lab pass.
