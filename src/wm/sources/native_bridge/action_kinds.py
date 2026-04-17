from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NativeActionKind:
    kind: str
    category: str
    default_risk: str = "low"
    implemented: bool = False
    default_enabled: bool = False
    admin_only: bool = False
    description: str = ""


NATIVE_ACTION_KINDS: tuple[NativeActionKind, ...] = (
    NativeActionKind("player_apply_aura", "player", "medium", implemented=True, description="Apply an aura spell to the scoped player."),
    NativeActionKind("player_remove_aura", "player", "medium", implemented=True, description="Remove an aura spell from the scoped player."),
    NativeActionKind("player_cast_spell", "player", "medium", implemented=True, description="Make the scoped player cast a spell."),
    NativeActionKind("player_set_display_id", "player", "medium", implemented=True, description="Temporarily set the scoped player's display ID."),
    NativeActionKind("player_learn_spell", "player", "medium", implemented=True, description="Teach the scoped player a spell."),
    NativeActionKind("player_unlearn_spell", "player", "medium", implemented=True, description="Remove a learned spell from the scoped player."),
    NativeActionKind("player_add_xp", "player", "medium", description="Grant experience to the scoped player."),
    NativeActionKind("player_add_money", "player", "medium", implemented=True, description="Grant copper to the scoped player."),
    NativeActionKind("player_remove_money", "player", "medium", description="Remove copper from the scoped player."),
    NativeActionKind("player_add_reputation", "player", "medium", implemented=True, description="Adjust faction reputation for the scoped player."),
    NativeActionKind("player_set_phase", "player", "medium", description="Set player phase mask."),
    NativeActionKind("player_clear_phase", "player", "medium", description="Clear WM-applied player phase state."),
    NativeActionKind("player_teleport", "player", "high", description="Teleport the scoped player."),
    NativeActionKind("player_summon_to_location", "player", "high", description="Summon the scoped player to a location."),
    NativeActionKind("player_resurrect", "player", "medium", description="Resurrect the scoped player."),
    NativeActionKind("player_restore_health_power", "player", "low", implemented=True, description="Restore health and power for the scoped player."),
    NativeActionKind("player_set_speed", "player", "medium", description="Temporarily adjust player movement speed."),
    NativeActionKind("player_add_item", "inventory", "medium", implemented=True, description="Add an item to the scoped player."),
    NativeActionKind("player_remove_item", "inventory", "medium", description="Remove an item from the scoped player."),
    NativeActionKind("player_equip_item", "inventory", "medium", description="Equip an item on the scoped player."),
    NativeActionKind("player_create_bound_item", "inventory", "medium", description="Create a soulbound item for the scoped player."),
    NativeActionKind("player_send_mail", "inventory", "medium", description="Send mail to the scoped player."),
    NativeActionKind("player_send_mail_with_items", "inventory", "medium", description="Send mail with attached items."),
    NativeActionKind("player_add_title", "inventory", "low", description="Grant a title to the scoped player."),
    NativeActionKind("player_remove_title", "inventory", "low", description="Remove a title from the scoped player."),
    NativeActionKind("player_add_achievement_credit", "inventory", "medium", description="Grant achievement criteria credit."),
    NativeActionKind("quest_add", "quest", "medium", implemented=True, description="Add a quest to the scoped player."),
    NativeActionKind("quest_remove", "quest", "medium", description="Remove a quest from the scoped player."),
    NativeActionKind("quest_complete_objective", "quest", "medium", description="Complete one quest objective."),
    NativeActionKind("quest_complete", "quest", "medium", description="Force complete a quest for the scoped player."),
    NativeActionKind("quest_fail", "quest", "medium", description="Fail a quest for the scoped player."),
    NativeActionKind("quest_reward", "quest", "high", description="Reward a quest for the scoped player."),
    NativeActionKind("quest_set_explored", "quest", "medium", description="Set explored objective state."),
    NativeActionKind("wm_counter_set", "quest", "low", description="Set a hidden WM progress counter."),
    NativeActionKind("wm_counter_increment", "quest", "low", description="Increment a hidden WM progress counter."),
    NativeActionKind("wm_counter_clear", "quest", "low", description="Clear a hidden WM progress counter."),
    NativeActionKind("creature_spawn", "world_object", "medium", implemented=True, description="Spawn a WM-owned creature."),
    NativeActionKind("creature_despawn", "world_object", "medium", implemented=True, description="Despawn a WM-owned creature."),
    NativeActionKind("creature_set_name", "world_object", "medium", description="Set a WM-owned creature name."),
    NativeActionKind("creature_set_subname", "world_object", "medium", description="Set a WM-owned creature subname."),
    NativeActionKind("creature_set_faction", "world_object", "medium", description="Set a WM-owned creature faction."),
    NativeActionKind("creature_set_npc_flags", "world_object", "medium", description="Set WM-owned creature NPC flags."),
    NativeActionKind("creature_set_display_id", "world_object", "medium", implemented=True, description="Set WM-owned creature display ID."),
    NativeActionKind("creature_set_scale", "world_object", "medium", implemented=True, description="Set WM-owned creature scale."),
    NativeActionKind("creature_set_health_pct", "world_object", "medium", description="Set WM-owned creature health percentage."),
    NativeActionKind("creature_set_phase", "world_object", "medium", description="Set a WM-owned creature phase."),
    NativeActionKind("creature_move_to", "world_object", "medium", description="Move a WM-owned creature."),
    NativeActionKind("creature_follow_player", "world_object", "medium", description="Make a WM-owned creature follow the scoped player."),
    NativeActionKind("creature_stop_movement", "world_object", "low", description="Stop WM-owned creature movement."),
    NativeActionKind("creature_set_waypoints", "world_object", "medium", description="Assign waypoints to a WM-owned creature."),
    NativeActionKind("creature_say", "world_object", "low", implemented=True, description="Make a WM-owned creature say text."),
    NativeActionKind("creature_yell", "world_object", "low", description="Make a WM-owned creature yell text."),
    NativeActionKind("creature_whisper_player", "world_object", "low", description="Make a WM-owned creature whisper the scoped player."),
    NativeActionKind("creature_emote", "world_object", "low", implemented=True, description="Make a WM-owned creature emote."),
    NativeActionKind("creature_cast_spell", "world_object", "medium", implemented=True, description="Make a WM-owned creature cast a spell."),
    NativeActionKind("creature_attack_target", "world_object", "high", description="Make a WM-owned creature attack a target."),
    NativeActionKind("creature_attack_player", "world_object", "high", description="Make a WM-owned creature attack the scoped player."),
    NativeActionKind("creature_flee", "world_object", "medium", description="Make a WM-owned creature flee."),
    NativeActionKind("creature_evade", "world_object", "medium", description="Force a WM-owned creature evade/reset."),
    NativeActionKind("creature_set_react_state", "world_object", "medium", description="Set a WM-owned creature react state."),
    NativeActionKind("gameobject_spawn", "world_object", "medium", description="Spawn a WM-owned gameobject."),
    NativeActionKind("gameobject_despawn", "world_object", "medium", description="Despawn a WM-owned gameobject."),
    NativeActionKind("gameobject_set_state", "world_object", "medium", description="Set a WM-owned gameobject state."),
    NativeActionKind("gossip_override_set", "gossip", "medium", description="Set per-player gossip override content."),
    NativeActionKind("gossip_override_clear", "gossip", "low", description="Clear per-player gossip override content."),
    NativeActionKind("gossip_option_add", "gossip", "medium", description="Add a scoped gossip option."),
    NativeActionKind("gossip_option_remove", "gossip", "low", description="Remove a scoped gossip option."),
    NativeActionKind("npc_text_override_set", "gossip", "medium", description="Set scoped NPC text override."),
    NativeActionKind("npc_text_override_clear", "gossip", "low", description="Clear scoped NPC text override."),
    NativeActionKind("player_show_menu", "gossip", "medium", description="Show a server-side menu to the scoped player."),
    NativeActionKind("player_close_gossip", "gossip", "low", description="Close gossip for the scoped player."),
    NativeActionKind("companion_spawn", "companion", "medium", description="Spawn a WM companion for the scoped player."),
    NativeActionKind("companion_despawn", "companion", "medium", description="Despawn a WM companion."),
    NativeActionKind("companion_set_state", "companion", "low", description="Update WM companion state."),
    NativeActionKind("companion_follow", "companion", "low", description="Make a WM companion follow."),
    NativeActionKind("companion_wait", "companion", "low", description="Make a WM companion wait."),
    NativeActionKind("companion_move_to", "companion", "medium", description="Move a WM companion."),
    NativeActionKind("companion_say", "companion", "low", description="Make a WM companion say text."),
    NativeActionKind("companion_whisper", "companion", "low", description="Make a WM companion whisper the scoped player."),
    NativeActionKind("companion_emote", "companion", "low", description="Make a WM companion emote."),
    NativeActionKind("companion_set_gossip", "companion", "medium", description="Set WM companion gossip."),
    NativeActionKind("zone_set_weather", "environment", "medium", description="Set scoped zone weather override."),
    NativeActionKind("zone_clear_weather_override", "environment", "low", description="Clear scoped zone weather override."),
    NativeActionKind("world_announce_to_player", "environment", "low", implemented=True, description="Send a server announcement to the scoped player."),
    NativeActionKind("player_play_sound", "environment", "low", description="Play a sound ID for the scoped player."),
    NativeActionKind("player_play_movie", "environment", "medium", description="Play a movie/cinematic ID for the scoped player."),
    NativeActionKind("area_trigger_marker_set", "environment", "medium", description="Set a scoped area trigger marker."),
    NativeActionKind("area_trigger_marker_clear", "environment", "low", description="Clear a scoped area trigger marker."),
    NativeActionKind("context_snapshot_request", "environment", "low", implemented=True, default_enabled=True, description="Request an on-demand native context snapshot."),
    NativeActionKind("group_invite_player", "social", "medium", description="Invite the scoped player to a group."),
    NativeActionKind("group_remove_player", "social", "medium", description="Remove the scoped player from a group."),
    NativeActionKind("duel_request_hint", "social", "low", description="Send a duel prompt/hint."),
    NativeActionKind("guild_message_to_player", "social", "low", description="Send scoped guild-style text to a player."),
    NativeActionKind("debug_ping", "debug", "low", implemented=True, default_enabled=True, admin_only=True, description="Return a native bridge health ping."),
    NativeActionKind("debug_echo", "debug", "low", implemented=True, default_enabled=True, admin_only=True, description="Echo payload through the native bridge queue."),
    NativeActionKind("debug_fail", "debug", "low", implemented=True, default_enabled=True, admin_only=True, description="Intentionally fail to test error propagation."),
    NativeActionKind("debug_snapshot_player", "debug", "low", description="Emit a lightweight player snapshot for diagnostics."),
    NativeActionKind("debug_policy_reload", "debug", "low", description="Force native bridge policy/scope reload."),
)


NATIVE_ACTION_KIND_BY_ID: dict[str, NativeActionKind] = {item.kind: item for item in NATIVE_ACTION_KINDS}


def native_action_kind_ids() -> list[str]:
    return [item.kind for item in NATIVE_ACTION_KINDS]


def native_action_policy_seed_rows() -> list[NativeActionKind]:
    return list(NATIVE_ACTION_KINDS)
