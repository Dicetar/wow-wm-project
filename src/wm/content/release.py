from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from wm.character.journey import JOURNEY_PLAN_SCHEMA_VERSION
from wm.character.journey import JourneyPlanError
from wm.character.journey import validate_journey_plan
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.spells.shell_bank import load_spell_shell_bank


REPEATABLE_BOUNTY_SCHEMA = "wm.quest.release.repeatable_bounty.v1"
ONE_SHOT_SCHEMA = "wm.quest.release.one_shot.v1"
STORY_ARC_SCHEMA = "wm.quest.release.story_arc.v1"
STORY_ARC_BRANCH_LOCK_PLAN_SCHEMA = "wm.quest.release.story_arc.branch_lock_plan.v1"
ABILITY_SHELL_POWER_SCHEMA = "wm.ability.release.shell_power.v1"
SCENE_NATIVE_SEQUENCE_SCHEMA = "wm.scene.release.native_sequence.v1"
ITEM_MANAGED_POWER_SCHEMA = "wm.item.release.managed_power.v1"

QUEST_KIND_BY_SCHEMA = {
    REPEATABLE_BOUNTY_SCHEMA: "repeatable_bounty",
    ONE_SHOT_SCHEMA: "one_shot",
    STORY_ARC_SCHEMA: "story_arc",
}
CONTENT_KIND_BY_SCHEMA = {
    ABILITY_SHELL_POWER_SCHEMA: "ability",
    SCENE_NATIVE_SEQUENCE_SCHEMA: "scene",
    ITEM_MANAGED_POWER_SCHEMA: "item",
}

_TOP_LEVEL_KEYS_BY_SCHEMA = {
    REPEATABLE_BOUNTY_SCHEMA: {
        "schema_version",
        "quest_kind",
        "player_guid",
        "slot_policy",
        "repeatable",
        "quest",
        "objective",
        "reward",
        "runtime_sync",
        "notes",
    },
    ONE_SHOT_SCHEMA: {
        "schema_version",
        "quest_kind",
        "player_guid",
        "slot_policy",
        "repeatable",
        "quest",
        "objective",
        "reward",
        "links",
        "runtime_sync",
        "notes",
    },
    STORY_ARC_SCHEMA: {
        "schema_version",
        "quest_kind",
        "player_guid",
        "arc_key",
        "nodes",
        "edges",
        "fork_groups",
        "journey_updates",
        "runtime_sync",
        "notes",
    },
    ABILITY_SHELL_POWER_SCHEMA: {
        "schema_version",
        "content_kind",
        "player_guid",
        "ability_key",
        "ability_type",
        "shell_family",
        "shell_spell_id",
        "slot_policy",
        "behavior_kind",
        "behavior_variant",
        "client_truth",
        "runtime",
        "seed",
        "notes",
    },
    SCENE_NATIVE_SEQUENCE_SCHEMA: {
        "schema_version",
        "content_kind",
        "player_guid",
        "scene_key",
        "scene_type",
        "slot_policy",
        "trigger",
        "steps",
        "cleanup",
        "runtime",
        "notes",
    },
    ITEM_MANAGED_POWER_SCHEMA: {
        "schema_version",
        "content_kind",
        "player_guid",
        "item_key",
        "item_entry",
        "slot_policy",
        "base_item_entry",
        "item_shape",
        "visibility",
        "effects",
        "reward_integration",
        "runtime",
        "notes",
    },
}

_QUEST_KEYS = {
    "quest_id",
    "quest_level",
    "min_level",
    "questgiver_entry",
    "questgiver_name",
    "title",
    "quest_description",
    "objective_text",
    "offer_reward_text",
    "request_items_text",
    "grant_mode",
    "start_npc_entry",
    "end_npc_entry",
    "template_defaults",
}
_OBJECTIVE_KEYS = {
    "kind",
    "target_entry",
    "target_name",
    "kill_count",
    "item_entry",
    "item_name",
    "count",
    "npc_entry",
    "npc_name",
}
_REWARD_KEYS = {
    "kind",
    "money_copper",
    "item_entry",
    "item_name",
    "item_count",
    "item_mode",
    "reward_item_mode",
    "spell_id",
    "spell_display_id",
    "reputation",
    "fresh_visible_reward_ids_required",
}
_NODE_KEYS = {
    "node_key",
    "quest_id",
    "quest_schema",
    "fresh_reserved_required",
    "title",
    "quest",
    "objective",
    "reward",
}
_EDGE_KEYS = {"from", "to", "kind"}
_FORK_GROUP_KEYS = {"group_key", "choice_node_keys", "lock_policy", "exclusive_group_id", "loser_policy"}
_JOURNEY_UPDATE_KEYS = {"stage_key", "branch_key", "conversation_steering", "prompt_queue", "reward_instance"}
_RUNTIME_SYNC_KEYS = {"mode", "quest_commands", "item_commands", "spell_commands", "notes"}
_CLIENT_TRUTH_KEYS = {"client_patch_required", "server_dbc_required", "spellbook_button_required", "notes"}
_ABILITY_RUNTIME_KEYS = {"native_behavior_required", "python_decision_required", "audit_required", "notes"}
_ABILITY_SEED_KEYS = {"stock_seed_spell_id", "seed_template", "seed_only", "notes"}
_SCENE_TRIGGER_KEYS = {
    "kind",
    "source_event_required",
    "max_event_age_seconds",
    "map_id",
    "zone_id",
    "subject_entry",
    "notes",
}
_SCENE_STEP_KEYS = {
    "step_key",
    "native_action_kind",
    "payload",
    "risk_level",
    "delay_seconds",
    "idempotency_suffix",
    "expected_effect",
    "requires_live_proof",
}
_SCENE_CLEANUP_KEYS = {"required", "expires_seconds", "steps", "notes"}
_SCENE_RUNTIME_KEYS = {"native_actions_required", "audit_required", "player_scope_required", "control_scene_required", "notes"}
_ITEM_VISIBILITY_KEYS = {
    "player_visible_state_required",
    "tooltip_required",
    "wearer_aura_spell_id",
    "target_aura_spell_id",
    "client_cache_risk",
    "notes",
}
_ITEM_EFFECT_KEYS = {
    "effect_key",
    "kind",
    "trigger",
    "target",
    "visible_state",
    "native_hook",
    "amount_pct",
    "chance_pct",
    "duration_ms",
    "spell_id",
    "shell_spell_id",
    "notes",
}
_ITEM_REWARD_INTEGRATION_KEYS = {
    "quest_reward_allowed",
    "fresh_quest_required_when_reward_changes",
    "direct_grant_allowed",
    "cleanup_supported",
    "notes",
}
_ITEM_RUNTIME_KEYS = {"native_behavior_required", "python_decision_required", "audit_required", "rollback_required", "notes"}
_ITEM_SHAPE_KEYS = {
    "item_class",
    "inventory_type",
    "armor_subclass",
    "weapon_subclass",
    "quality",
    "binding",
    "required_level",
    "stackable",
    "notes",
}

_CHAIN_FIELDS = {"PrevQuestID", "NextQuestID", "RewardNextQuest", "ExclusiveGroup", "BreadcrumbForQuestId"}
_EDGE_KINDS = {"turn_in_unlocks", "reward_next_quest", "prev_next_link", "breadcrumb", "branch_unlocks"}
_FORK_LOCK_POLICIES = {"first_turn_in_locks_others"}
_ABILITY_SLOT_POLICIES = {"fresh_shell_slot_required", "existing_named_shell", "named_shell_override"}
_SCENE_SLOT_POLICIES = {"no_visible_id_required", "fresh_visible_ids_if_templates"}
_ITEM_SLOT_POLICIES = {"fresh_item_slot_required", "existing_proven_item_slot_extension"}
_SCENE_TYPES = {"area_pressure", "creature_marker", "companion_intervention", "environment_effect", "arc_beat"}
_SCENE_TRIGGER_KINDS = {"manual_operator", "area_pressure", "kill_reaction", "talk_reaction", "quest_reaction", "arc_beat"}
_SCENE_ALLOWED_ACTION_KINDS = {
    "player_chat_message",
    "world_announce_to_player",
    "player_apply_aura",
    "player_remove_aura",
    "player_cast_spell",
    "player_restore_health_power",
    "player_set_display_id",
    "creature_spawn",
    "creature_despawn",
    "creature_say",
    "creature_emote",
    "creature_cast_spell",
    "creature_set_display_id",
    "creature_set_scale",
}
_SCENE_UNSUPPORTED_MESSAGES = {
    "gameobject_spawn": "Gameobject scene releases are blocked until native gameobject_spawn is implemented and live-proven.",
    "gameobject_despawn": "Gameobject scene releases are blocked until native gameobject_despawn is implemented and live-proven.",
    "gameobject_set_state": "Gameobject scene releases are blocked until native gameobject_set_state is implemented and live-proven.",
    "zone_set_weather": "Real weather releases are blocked until zone_set_weather is implemented and live-proven; use visible aura/announcement/actor fallback scenes for now.",
    "zone_clear_weather_override": "Real weather releases are blocked until zone_clear_weather_override is implemented and live-proven.",
}
_ITEM_EFFECT_KINDS = {
    "wearer_aura",
    "target_mark_proc",
    "direct_spell_damage_bonus",
    "companion_target_preference",
    "proc_multiplier",
    "stat_bonus",
    "on_use_scene",
    "random_enchant_consumable",
}
_ITEM_HIDDEN_EFFECT_KINDS = {
    "target_mark_proc",
    "direct_spell_damage_bonus",
    "companion_target_preference",
    "proc_multiplier",
    "stat_bonus",
    "random_enchant_consumable",
}
_ITEM_CLASSES = {
    "armor",
    "weapon",
    "container",
    "consumable",
    "reagent",
    "projectile",
    "trade_goods",
    "generic",
    "recipe",
    "quiver",
    "quest",
    "key",
    "miscellaneous",
    "glyph",
}
_ITEM_INVENTORY_TYPES = {
    "non_equippable",
    "head",
    "neck",
    "shoulders",
    "shirt",
    "chest",
    "waist",
    "legs",
    "feet",
    "wrists",
    "hands",
    "finger",
    "trinket",
    "weapon",
    "shield",
    "ranged",
    "cloak",
    "two_hand_weapon",
    "bag",
    "tabard",
    "robe",
    "main_hand",
    "off_hand",
    "holdable",
    "ammo",
    "thrown",
    "ranged_right",
    "quiver",
    "relic",
}
_ITEM_ARMOR_SUBCLASSES = {"misc", "cloth", "leather", "mail", "plate", "buckler", "shield", "libram", "idol", "totem", "sigil"}
_ITEM_WEAPON_SUBCLASSES = {
    "axe",
    "two_hand_axe",
    "bow",
    "gun",
    "mace",
    "two_hand_mace",
    "polearm",
    "sword",
    "two_hand_sword",
    "staff",
    "fist_weapon",
    "miscellaneous",
    "dagger",
    "thrown",
    "crossbow",
    "wand",
    "fishing_pole",
}
_ITEM_QUALITIES = {"poor", "common", "uncommon", "rare", "epic", "legendary", "artifact", "heirloom"}
_ITEM_BINDINGS = {"none", "on_pickup", "on_equip", "on_use", "quest_item"}
_ABILITY_TYPE_FAMILIES = {
    "targeted_effect_with_projectile": {"unit_target_projectile"},
    "targeted_effect_instant": {"unit_target_effect"},
    "friendly_target_effect": {"unit_target_friendly"},
    "aoe_targeted_ground": {"ground_target_aoe"},
    "aoe_centered_on_target": {"target_centered_aoe"},
    "aoe_centered_on_caster": {"caster_centered_aoe"},
    "self_aura": {"self_aura"},
    "stance_toggle": {"self_aura"},
    "passive": {"passive_aura"},
    "random_targets": {"random_targets"},
    "frontal_cone": {"frontal_cone"},
    "summon_pet": {"summon_pet_compat"},
    "pet_active": {"pet_active_compat"},
    "chain_jump": {"unit_target_projectile", "unit_target_effect"},
    "channeled_target": {"unit_target_projectile", "unit_target_effect"},
    "movement_charge": {"unit_target_projectile", "unit_target_effect", "ground_target_aoe"},
}
_ABILITY_VARIANT_TYPES = {"chain_jump", "channeled_target", "movement_charge"}
_ABILITY_UNSUPPORTED_TYPES = {
    "item_target_enchant": "Use the managed item/on-use/equip pipeline unless a spellbook item-target button is explicitly required.",
    "gameobject_target": "Gameobject shell releases need a future specialized family and implemented gameobject native verbs.",
    "corpse_target": "Corpse-target releases need a future specialized family and concrete product use.",
    "vehicle_control": "Vehicle/control releases are future native runtime work, not a generic shell release.",
    "profession_recipe": "Profession/tradeskill releases need a profession pipeline, not a combat shell.",
}
_ABILITY_ROSTER_ORDER = (
    "targeted_effect_with_projectile",
    "targeted_effect_instant",
    "friendly_target_effect",
    "aoe_targeted_ground",
    "aoe_centered_on_target",
    "aoe_centered_on_caster",
    "self_aura",
    "stance_toggle",
    "passive",
    "random_targets",
    "frontal_cone",
    "summon_pet",
    "pet_active",
    "chain_jump",
    "channeled_target",
    "movement_charge",
    "item_target_enchant",
    "gameobject_target",
    "corpse_target",
    "vehicle_control",
    "profession_recipe",
)
_FORBIDDEN_KEY_PARTS = (
    "freeform",
    "sql",
    "gm_command",
    "gm_commands",
    "freeform_gm",
    "shell_command",
    "shell_commands",
    "llm_mutation",
    "direct_mutation",
    "file_mutation",
    "carrier_spell_id",
    "stock_carrier",
)


@dataclass(slots=True)
class ReleaseIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReleaseValidationResult:
    schema_version: str | None
    quest_kind: str | None
    ok: bool
    issues: list[ReleaseIssue] = field(default_factory=list)
    content_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "content_kind": self.content_kind,
            "quest_kind": self.quest_kind,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class ContentReleaseSpec:
    schema_version: str
    content_kind: str
    player_guid: int
    raw: dict[str, Any]
    quest_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(slots=True)
class ReleasePlanGate:
    gate: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReleasePlan:
    schema_version: str
    content_kind: str
    player_guid: int
    status: str
    gates: list[ReleasePlanGate]
    commands: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "content_kind": self.content_kind,
            "player_guid": self.player_guid,
            "status": self.status,
            "gates": [gate.to_dict() for gate in self.gates],
            "commands": list(self.commands),
            "notes": list(self.notes),
        }


class ContentReleaseSpecError(ValueError):
    pass


def validate_content_release_spec(raw: dict[str, Any]) -> ReleaseValidationResult:
    issues: list[ReleaseIssue] = []
    if not isinstance(raw, dict):
        return ReleaseValidationResult(schema_version=None, quest_kind=None, ok=False, issues=[
            ReleaseIssue(path="", message="Content release spec must be a JSON object.")
        ])

    _collect_forbidden_key_issues(raw, path="", issues=issues)
    schema_version = str(raw.get("schema_version") or "")
    quest_kind = str(raw.get("quest_kind") or "")
    expected_quest_kind = QUEST_KIND_BY_SCHEMA.get(schema_version)
    expected_content_kind = CONTENT_KIND_BY_SCHEMA.get(schema_version)
    if expected_quest_kind is None and expected_content_kind is None:
        issues.append(
            ReleaseIssue(
                path="schema_version",
                message=f"Unsupported content release schema_version `{schema_version}`.",
            )
        )
    elif expected_quest_kind is not None and quest_kind != expected_quest_kind:
        issues.append(
            ReleaseIssue(
                path="quest_kind",
                message=f"quest_kind must be `{expected_quest_kind}` for schema `{schema_version}`.",
            )
        )
    content_kind = str(raw.get("content_kind") or "")
    if expected_content_kind is not None and content_kind != expected_content_kind:
        issues.append(
            ReleaseIssue(
                path="content_kind",
                message=f"content_kind must be `{expected_content_kind}` for schema `{schema_version}`.",
            )
        )

    allowed = _TOP_LEVEL_KEYS_BY_SCHEMA.get(schema_version)
    if allowed is not None:
        _collect_unknown_key_issues(raw, allowed=allowed, path="", issues=issues)

    _require_positive_int(raw, "player_guid", issues=issues)
    if schema_version == REPEATABLE_BOUNTY_SCHEMA:
        _validate_repeatable_bounty(raw, issues=issues)
    elif schema_version == ONE_SHOT_SCHEMA:
        _validate_one_shot(raw, issues=issues)
    elif schema_version == STORY_ARC_SCHEMA:
        _validate_story_arc(raw, issues=issues)
    elif schema_version == ABILITY_SHELL_POWER_SCHEMA:
        _validate_ability_shell_power(raw, issues=issues)
    elif schema_version == SCENE_NATIVE_SEQUENCE_SCHEMA:
        _validate_scene_native_sequence(raw, issues=issues)
    elif schema_version == ITEM_MANAGED_POWER_SCHEMA:
        _validate_item_managed_power(raw, issues=issues)

    return ReleaseValidationResult(
        schema_version=schema_version or None,
        quest_kind=quest_kind or None,
        content_kind=content_kind or expected_content_kind or ("quest" if expected_quest_kind is not None else None),
        ok=not any(issue.severity == "error" for issue in issues),
        issues=issues,
    )


def load_content_release_spec(path: str | Path, *, player_guid: int | None = None) -> ContentReleaseSpec:
    spec_path = Path(path)
    raw = json.loads(spec_path.read_text(encoding="utf-8"))
    if player_guid is not None and isinstance(raw, dict):
        raw = dict(raw)
        raw["player_guid"] = int(player_guid)
    result = validate_content_release_spec(raw)
    if not result.ok:
        rendered = "; ".join(f"{issue.path}: {issue.message}" for issue in result.issues)
        raise ContentReleaseSpecError(rendered)
    assert isinstance(raw, dict)
    return ContentReleaseSpec(
        schema_version=str(raw["schema_version"]),
        content_kind=str(raw.get("content_kind") or result.content_kind or "quest"),
        player_guid=int(raw["player_guid"]),
        raw=dict(raw),
        quest_kind=(str(raw["quest_kind"]) if raw.get("quest_kind") not in (None, "") else None),
    )


def compile_scene_release_to_control_scene(spec: ContentReleaseSpec | dict[str, Any]) -> dict[str, Any]:
    raw = spec.raw if isinstance(spec, ContentReleaseSpec) else dict(spec)
    result = validate_content_release_spec(raw)
    if not result.ok:
        rendered = "; ".join(f"{issue.path}: {issue.message}" for issue in result.issues)
        raise ContentReleaseSpecError(rendered)
    if raw.get("schema_version") != SCENE_NATIVE_SEQUENCE_SCHEMA:
        raise ContentReleaseSpecError("Only wm.scene.release.native_sequence.v1 specs can emit control.scene.v1 JSON.")

    steps: list[dict[str, Any]] = []
    for item in list(raw.get("steps") or []) + list((raw.get("cleanup") or {}).get("steps") or []):
        assert isinstance(item, dict)
        compiled = {
            "native_action_kind": item["native_action_kind"],
            "payload": dict(item.get("payload") or {}),
            "risk_level": item.get("risk_level") or "low",
            "idempotency_suffix": item["idempotency_suffix"],
            "expected_effect": item.get("expected_effect") or f"Executes {item['native_action_kind']}.",
        }
        if "delay_seconds" in item:
            compiled["delay_seconds"] = item["delay_seconds"]
        steps.append(compiled)

    return {
        "id": str(raw["scene_key"]),
        "schema_version": "control.scene.v1",
        "description": str(raw.get("notes") or f"Compiled from {SCENE_NATIVE_SEQUENCE_SCHEMA}."),
        "steps": steps,
    }


def compile_story_arc_release_to_journey_plan(spec: ContentReleaseSpec | dict[str, Any]) -> dict[str, Any]:
    raw = spec.raw if isinstance(spec, ContentReleaseSpec) else dict(spec)
    result = validate_content_release_spec(raw)
    if not result.ok:
        rendered = "; ".join(f"{issue.path}: {issue.message}" for issue in result.issues)
        raise ContentReleaseSpecError(rendered)
    if raw.get("schema_version") != STORY_ARC_SCHEMA:
        raise ContentReleaseSpecError("Only wm.quest.release.story_arc.v1 specs can emit journey plans.")

    journey_updates = dict(raw.get("journey_updates") or {})
    nodes = [node for node in raw.get("nodes") or [] if isinstance(node, dict)]
    arc_key = str(raw["arc_key"])
    stage_key = str(journey_updates.get("stage_key") or (nodes[0].get("node_key") if nodes else "") or "arc_published")
    summary = f"Story arc release `{arc_key}` with {len(nodes)} linked quest node(s)."
    plan: dict[str, Any] = {
        "schema_version": JOURNEY_PLAN_SCHEMA_VERSION,
        "player_guid": int(raw["player_guid"]),
        "arc_states": [
            {
                "arc_key": arc_key,
                "stage_key": stage_key,
                "status": "active",
                "branch_key": journey_updates.get("branch_key"),
                "summary": summary,
            }
        ],
        "metadata": {
            "source_schema_version": STORY_ARC_SCHEMA,
            "arc_key": arc_key,
            "node_keys": [str(node.get("node_key")) for node in nodes],
            "edges": list(raw.get("edges") or []),
            "fork_groups": list(raw.get("fork_groups") or []),
            "release_notes": list(raw.get("notes") or []),
        },
    }
    if journey_updates.get("conversation_steering"):
        plan["conversation_steering"] = list(journey_updates.get("conversation_steering") or [])
    if journey_updates.get("prompt_queue"):
        plan["prompt_queue"] = list(journey_updates.get("prompt_queue") or [])
    if isinstance(journey_updates.get("reward_instance"), dict) and journey_updates["reward_instance"]:
        plan["reward_instances"] = [dict(journey_updates["reward_instance"])]
    try:
        validate_journey_plan(plan)
    except JourneyPlanError as exc:
        raise ContentReleaseSpecError(f"Story arc journey plan is not valid: {exc}") from exc
    return plan


def compile_story_arc_release_to_branch_lock_plan(spec: ContentReleaseSpec | dict[str, Any]) -> dict[str, Any]:
    raw = spec.raw if isinstance(spec, ContentReleaseSpec) else dict(spec)
    result = validate_content_release_spec(raw)
    if not result.ok:
        rendered = "; ".join(f"{issue.path}: {issue.message}" for issue in result.issues)
        raise ContentReleaseSpecError(rendered)
    if raw.get("schema_version") != STORY_ARC_SCHEMA:
        raise ContentReleaseSpecError("Only wm.quest.release.story_arc.v1 specs can emit branch-lock plans.")

    node_by_key = {
        str(node.get("node_key")): node
        for node in raw.get("nodes") or []
        if isinstance(node, dict) and str(node.get("node_key") or "")
    }
    branch_key = str((raw.get("journey_updates") or {}).get("branch_key") or "")
    fork_groups = []
    missing_quest_ids: set[str] = set()
    for group in raw.get("fork_groups") or []:
        if not isinstance(group, dict):
            continue
        choices = [str(choice) for choice in group.get("choice_node_keys") or []]
        choice_plans = []
        for winner in choices:
            winner_quest_id = _int_value((node_by_key.get(winner) or {}).get("quest_id"))
            if winner_quest_id <= 0:
                missing_quest_ids.add(winner)
            loser_actions = []
            for loser in choices:
                if loser == winner:
                    continue
                loser_quest_id = _int_value((node_by_key.get(loser) or {}).get("quest_id"))
                if loser_quest_id <= 0:
                    missing_quest_ids.add(loser)
                    loser_actions.append({"node_key": loser, "quest_id": None, "status": "needs_quest_id"})
                    continue
                loser_actions.append(
                    {
                        "node_key": loser,
                        "quest_id": loser_quest_id,
                        "native_action_kind": "quest_remove",
                        "payload": {
                            "quest_id": loser_quest_id,
                            "remove_rewarded": False,
                            "admin_override": False,
                        },
                        "requires_live_proof": True,
                    }
                )
            choice_plans.append(
                {
                    "winner_node_key": winner,
                    "winner_quest_id": winner_quest_id if winner_quest_id > 0 else None,
                    "trigger_event": "quest_rewarded",
                    "record_branch_key": f"{branch_key}:{winner}" if branch_key else winner,
                    "loser_actions": loser_actions,
                }
            )
        fork_groups.append(
            {
                "group_key": str(group.get("group_key") or ""),
                "lock_policy": str(group.get("lock_policy") or ""),
                "choices": choice_plans,
            }
        )

    return {
        "schema_version": STORY_ARC_BRANCH_LOCK_PLAN_SCHEMA,
        "source_schema_version": STORY_ARC_SCHEMA,
        "player_guid": int(raw["player_guid"]),
        "arc_key": str(raw["arc_key"]),
        "status": "ready" if not missing_quest_ids else "needs_quest_ids",
        "missing_quest_id_node_keys": sorted(missing_quest_ids),
        "fork_groups": fork_groups,
        "notes": [
            "On first completed choice, record the chosen branch in character journey state before removing sibling active quests.",
            "Use quest_remove only for WM-managed quest IDs after dry-run confirms scope and policy; quest_fail is not implemented.",
            "A branch-lock plan is not an apply command and must still be routed through the native action queue with audit.",
        ],
    }


def build_content_release_plan(spec: ContentReleaseSpec | dict[str, Any]) -> ReleasePlan:
    raw = spec.raw if isinstance(spec, ContentReleaseSpec) else dict(spec)
    result = validate_content_release_spec(raw)
    if not result.ok:
        rendered = "; ".join(f"{issue.path}: {issue.message}" for issue in result.issues)
        raise ContentReleaseSpecError(rendered)

    schema_version = str(raw["schema_version"])
    content_kind = str(raw.get("content_kind") or result.content_kind or "quest")
    player_guid = int(raw["player_guid"])
    gates = [
        ReleasePlanGate("schema", "ready", f"{schema_version} validated."),
        ReleasePlanGate("id_reservation", "required", _release_plan_id_detail(raw)),
        ReleasePlanGate("preflight", "required", "Check live DB schema, active player scope, current slot state, and stale accepted/rewarded content."),
        ReleasePlanGate("dry_run", "required", "Render exact publisher output or typed native action sequence before apply."),
        ReleasePlanGate("apply", "blocked_until_dry_run", "Apply only through the owned publisher or native action queue."),
        ReleasePlanGate("runtime_sync", "required", _release_plan_runtime_detail(raw)),
        ReleasePlanGate("live_proof", "required", "Player-facing behavior must be observed in BridgeLab before status becomes WORKING."),
        ReleasePlanGate("status", "partial_until_live", "Repo validation is not enough for player-facing release status."),
    ]
    commands = _release_plan_commands(raw)
    notes = _release_plan_notes(raw)
    return ReleasePlan(
        schema_version=schema_version,
        content_kind=content_kind,
        player_guid=player_guid,
        status="PLAN_READY",
        gates=gates,
        commands=commands,
        notes=notes,
    )


def build_content_release_packet(spec: ContentReleaseSpec | dict[str, Any]) -> dict[str, Any]:
    raw = spec.raw if isinstance(spec, ContentReleaseSpec) else dict(spec)
    result = validate_content_release_spec(raw)
    if not result.ok:
        rendered = "; ".join(f"{issue.path}: {issue.message}" for issue in result.issues)
        raise ContentReleaseSpecError(rendered)

    schema_version = str(raw["schema_version"])
    artifacts: list[dict[str, Any]] = []
    if schema_version == SCENE_NATIVE_SEQUENCE_SCHEMA:
        artifacts.append(
            {
                "artifact_kind": "control_scene",
                "write_hint": "compiled-control-scene.json",
                "payload": compile_scene_release_to_control_scene(raw),
            }
        )
    elif schema_version == STORY_ARC_SCHEMA:
        artifacts.extend(
            [
                {
                    "artifact_kind": "journey_plan",
                    "write_hint": "compiled-journey-plan.json",
                    "payload": compile_story_arc_release_to_journey_plan(raw),
                },
                {
                    "artifact_kind": "branch_lock_plan",
                    "write_hint": "compiled-branch-lock-plan.json",
                    "payload": compile_story_arc_release_to_branch_lock_plan(raw),
                },
            ]
        )
    elif schema_version == ABILITY_SHELL_POWER_SCHEMA:
        artifacts.append(
            {
                "artifact_kind": "ability_shell_roster_entry",
                "write_hint": "ability-shell-roster-entry.json",
                "payload": _ability_roster_entry_for_spec(raw),
            }
        )
    elif schema_version == ITEM_MANAGED_POWER_SCHEMA:
        artifacts.append(
            {
                "artifact_kind": "managed_item_power_contract",
                "write_hint": "managed-item-power-contract.json",
                "payload": _managed_item_power_contract(raw),
            }
        )

    plan = build_content_release_plan(raw)
    return {
        "schema_version": "wm.content_release_packet.v1",
        "source_schema_version": schema_version,
        "content_kind": str(raw.get("content_kind") or ("quest" if schema_version in QUEST_KIND_BY_SCHEMA else "")),
        "quest_kind": raw.get("quest_kind"),
        "player_guid": int(raw["player_guid"]),
        "validation": result.to_dict(),
        "plan": plan.to_dict(),
        "artifacts": artifacts,
        "live_proof_checklist": _release_live_proof_checklist(raw),
        "status": "PACKET_READY",
    }


def render_content_release_packet_summary(packet: dict[str, Any]) -> str:
    lines = [
        f"schema_version: {packet.get('schema_version')}",
        f"source_schema_version: {packet.get('source_schema_version')}",
        f"content_kind: {packet.get('content_kind')}",
        f"quest_kind: {packet.get('quest_kind')}",
        f"player_guid: {packet.get('player_guid')}",
        f"status: {packet.get('status')}",
        "artifacts:",
    ]
    artifacts = packet.get("artifacts") or []
    if artifacts:
        lines.extend(f"- {artifact.get('artifact_kind')} -> {artifact.get('write_hint')}" for artifact in artifacts)
    else:
        lines.append("- none")
    lines.append("live_proof_checklist:")
    checklist = packet.get("live_proof_checklist") or []
    if checklist:
        lines.extend(f"- {item}" for item in checklist)
    else:
        lines.append("- none")
    return "\n".join(lines)


def write_content_release_packet(
    spec: ContentReleaseSpec | dict[str, Any],
    output_dir: str | Path,
    *,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    packet = build_content_release_packet(spec)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written_files: list[dict[str, Any]] = []

    def write_json_file(filename: str, payload: dict[str, Any], *, artifact_kind: str) -> None:
        target = destination / filename
        if target.exists() and not allow_overwrite:
            raise ContentReleaseSpecError(f"Refusing to overwrite existing packet artifact: {target}")
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written_files.append(
            {
                "artifact_kind": artifact_kind,
                "path": str(target),
            }
        )

    write_json_file("release_packet.json", packet, artifact_kind="release_packet")
    for artifact in packet.get("artifacts") or []:
        payload = artifact.get("payload")
        if not isinstance(payload, dict):
            continue
        write_json_file(
            str(artifact.get("write_hint") or f"{artifact.get('artifact_kind')}.json"),
            payload,
            artifact_kind=str(artifact.get("artifact_kind") or "artifact"),
        )

    return {
        "schema_version": "wm.content_release_packet_write.v1",
        "status": "WRITTEN",
        "output_dir": str(destination),
        "file_count": len(written_files),
        "files": written_files,
    }


def render_content_release_packet_write_summary(result: dict[str, Any]) -> str:
    lines = [
        f"schema_version: {result.get('schema_version')}",
        f"status: {result.get('status')}",
        f"output_dir: {result.get('output_dir')}",
        f"file_count: {result.get('file_count')}",
        "files:",
    ]
    files = result.get("files") or []
    if files:
        lines.extend(f"- {item.get('artifact_kind')} | {item.get('path')}" for item in files)
    else:
        lines.append("- none")
    return "\n".join(lines)


def _ability_roster_entry_for_spec(raw: dict[str, Any]) -> dict[str, Any]:
    ability_type = str(raw.get("ability_type") or "")
    for entry in build_ability_shell_roster()["entries"]:
        if entry["ability_type"] == ability_type:
            return dict(entry)
    return {
        "ability_type": ability_type,
        "status": "unknown",
        "shell_families": [],
        "missing_family_ids": [],
        "notes": [f"No roster entry exists for ability_type `{ability_type}`."],
    }


def _managed_item_power_contract(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "wm.item.release.managed_power.contract.v1",
        "item_key": str(raw["item_key"]),
        "item_entry": int(raw["item_entry"]),
        "slot_policy": str(raw["slot_policy"]),
        "item_shape": dict(raw.get("item_shape") or {}),
        "visibility": dict(raw.get("visibility") or {}),
        "effect_keys": [str(effect.get("effect_key")) for effect in raw.get("effects") or [] if isinstance(effect, dict)],
        "hidden_effect_keys": [
            str(effect.get("effect_key"))
            for effect in raw.get("effects") or []
            if isinstance(effect, dict) and str(effect.get("kind") or "") in _ITEM_HIDDEN_EFFECT_KINDS
        ],
        "reward_integration": dict(raw.get("reward_integration") or {}),
        "runtime": dict(raw.get("runtime") or {}),
    }


def _release_live_proof_checklist(raw: dict[str, Any]) -> list[str]:
    schema_version = str(raw.get("schema_version") or "")
    if schema_version == REPEATABLE_BOUNTY_SCHEMA:
        return [
            "Scoped player can accept or receive the repeatable bounty.",
            "Objective progress updates from real play and completion/reward suppresses duplicates.",
            "Cooldown/regrant behavior is observed before status becomes WORKING.",
        ]
    if schema_version == ONE_SHOT_SCHEMA:
        return [
            "Scoped player sees the standalone quest with the intended text and objective.",
            "Quest can be completed and rewarded once.",
            "No links or follow-up quests appear from this release.",
        ]
    if schema_version == STORY_ARC_SCHEMA:
        return [
            "Each quest node uses a fresh visible quest ID and appears in the intended order.",
            "Journey arc state records the active stage and branch key.",
            "For forks, first completed choice records the winning branch and locks/removes sibling choices through audited typed actions.",
        ]
    if schema_version == ABILITY_SHELL_POWER_SCHEMA:
        return [
            "Spellbook/action-bar presentation matches the selected shell family.",
            "The ability casts with the intended target shape, range, cooldown, visual, and effect.",
            "Grant and revoke paths are audited and do not use stock spell IDs as permanent carriers.",
        ]
    if schema_version == ITEM_MANAGED_POWER_SCHEMA:
        return [
            "Item tooltip and visible wearer/target state are visible to the player.",
            "Hidden native effects only run while the visible state is active.",
            "Reward/direct grant and rollback/cleanup paths are verified for the scoped player.",
        ]
    if schema_version == SCENE_NATIVE_SEQUENCE_SCHEMA:
        return [
            "Every scene step produces the expected visible/auditable effect for the scoped player.",
            "Spawned actors are WM-owned and follow-up actions resolve only owned objects.",
            "Cleanup/despawn runs and audit links source, request, result, and cleanup.",
        ]
    return ["Player-facing behavior must be live-proven before status becomes WORKING."]


def _release_plan_id_detail(raw: dict[str, Any]) -> str:
    schema_version = str(raw.get("schema_version") or "")
    if schema_version in {REPEATABLE_BOUNTY_SCHEMA, ONE_SHOT_SCHEMA}:
        return f"Quest slot policy: {raw.get('slot_policy')}; failed visible quest IDs must be retired."
    if schema_version == STORY_ARC_SCHEMA:
        return "Each story arc node requires a fresh quest ID; branch losers need journey state and safe quest removal/failure handling."
    if schema_version == ABILITY_SHELL_POWER_SCHEMA:
        shell_id = raw.get("shell_spell_id")
        if shell_id not in (None, ""):
            return f"Shell spell {shell_id} must remain in family {raw.get('shell_family')} and use stock spells as seed data only."
        return f"Reserve a fresh shell slot from family {raw.get('shell_family')} before apply."
    if schema_version == ITEM_MANAGED_POWER_SCHEMA:
        return f"Item entry {raw.get('item_entry')} uses slot policy {raw.get('slot_policy')}; reward-panel changes require fresh quest IDs."
    if schema_version == SCENE_NATIVE_SEQUENCE_SCHEMA:
        return "Temporary scene actors use WM-owned world-object rows; permanent creature/gameobject IDs require a separate publisher."
    return "Fresh visible IDs are required for any player-facing content identity."


def _release_plan_runtime_detail(raw: dict[str, Any]) -> str:
    schema_version = str(raw.get("schema_version") or "")
    if schema_version in {REPEATABLE_BOUNTY_SCHEMA, ONE_SHOT_SCHEMA, STORY_ARC_SCHEMA}:
        return "Reload quest_template/addon and starter/ender tables or restart worldserver when reload safety is unknown."
    if schema_version == ABILITY_SHELL_POWER_SCHEMA:
        return "Stage server DBC, rebuild/install client patch when spellbook/action-bar truth is required, then restart worldserver."
    if schema_version == ITEM_MANAGED_POWER_SCHEMA:
        return "Reload item_template if proven safe; otherwise restart worldserver and retest client cache/tooltip behavior."
    if schema_version == SCENE_NATIVE_SEQUENCE_SCHEMA:
        return "No DB reload for pure native scenes; ensure action policies/player scope are enabled before apply."
    return "Choose the narrowest safe reload/restart path before live proof."


def _release_plan_commands(raw: dict[str, Any]) -> list[str]:
    schema_version = str(raw.get("schema_version") or "")
    if schema_version == SCENE_NATIVE_SEQUENCE_SCHEMA:
        return [
            "python -m wm.content.release <scene-spec.json> --emit-control-scene",
            "python -m wm.control.scene_play --scene <compiled-control-scene.json> --player-guid <guid> --mode dry-run --summary",
            "python -m wm.control.scene_play --scene <compiled-control-scene.json> --player-guid <guid> --mode apply --confirm-live-apply --summary",
        ]
    if schema_version == ITEM_MANAGED_POWER_SCHEMA:
        return [
            "python -m wm.items.live_publish --draft-json <item-draft.json> --mode dry-run --summary",
            "python -m wm.content.playcycle item-effect --scenario-json <scenario.json> --mode verify --summary",
        ]
    if schema_version == ABILITY_SHELL_POWER_SCHEMA:
        return [
            "python -m wm.spells.server_dbc materialize --summary",
            "python -m wm.spells.client_patch build --summary",
            "python -m wm.content.release <ability-spec.json> --summary",
        ]
    if schema_version == STORY_ARC_SCHEMA:
        return [
            "python -m wm.content.release <story-arc-spec.json> --emit-journey-plan",
            "python -m wm.content.release <story-arc-spec.json> --emit-branch-lock-plan",
            "python -m wm.character.journey apply --plan-json <compiled-journey-plan.json> --mode dry-run --summary",
            "python -m wm.arcs.factory <arc-spec.json> --mode dry-run --summary",
            "python -m wm.content.playcycle item-effect --scenario-json <reward-scenario.json> --mode verify --summary",
        ]
    if schema_version == REPEATABLE_BOUNTY_SCHEMA:
        return ["python -m wm.quests.bounty <bounty-spec.json> --mode dry-run --summary"]
    if schema_version == ONE_SHOT_SCHEMA:
        return ["python -m wm.quests.publish <one-shot-spec.json> --mode dry-run --summary"]
    return []


def _release_plan_notes(raw: dict[str, Any]) -> list[str]:
    schema_version = str(raw.get("schema_version") or "")
    notes = [
        "Do not add freeform SQL, GM commands, shell commands, or direct LLM mutation fields.",
        "If visible content ships wrong, retire the visible ID and release a fresh one.",
    ]
    if schema_version == ITEM_MANAGED_POWER_SCHEMA:
        notes.append("Hidden item effects must be gated by the visible aura/tooltip state described in the spec.")
    if schema_version == SCENE_NATIVE_SEQUENCE_SCHEMA:
        notes.append("Gameobject and real weather actions remain blocked until native executors are implemented and live-proven.")
    if schema_version == STORY_ARC_SCHEMA:
        notes.append("Forks require journey branch records; do not rely only on quest-template linking.")
    return notes


def build_ability_shell_roster() -> dict[str, Any]:
    bank = load_spell_shell_bank()
    entries: list[dict[str, Any]] = []
    for ability_type in _ABILITY_ROSTER_ORDER:
        if ability_type in _ABILITY_UNSUPPORTED_TYPES:
            entries.append(
                {
                    "ability_type": ability_type,
                    "status": "future_blocked",
                    "shell_families": [],
                    "missing_family_ids": [],
                    "notes": [_ABILITY_UNSUPPORTED_TYPES[ability_type]],
                }
            )
            continue
        family_ids = sorted(_ABILITY_TYPE_FAMILIES.get(ability_type, set()))
        families = []
        missing = []
        for family_id in family_ids:
            family = bank.family_by_id(family_id)
            if family is None:
                missing.append(family_id)
                continue
            families.append(
                {
                    "family_id": family.family_id,
                    "family_kind": family.family_kind,
                    "slot_range_start": family.slot_range_start,
                    "slot_range_end": family.slot_range_end,
                    "slot_count": family.slot_count,
                    "targeting": family.targeting,
                    "seed_template": family.patch_seed_template,
                }
            )
        if missing:
            status = "missing_shell_family"
        elif ability_type in _ABILITY_VARIANT_TYPES:
            status = "behavior_variant_ready"
        elif any(family["family_kind"] == "compatibility" for family in families):
            status = "compatibility_ready"
        else:
            status = "ready"
        entries.append(
            {
                "ability_type": ability_type,
                "status": status,
                "shell_families": families,
                "missing_family_ids": missing,
                "notes": _ability_roster_notes(ability_type, status),
            }
        )
    return {
        "schema_version": "wm.ability_shell_roster.v1",
        "shell_bank_schema_version": bank.schema_version,
        "client_patch_required": bank.client_patch_required,
        "ready_count": sum(1 for entry in entries if str(entry["status"]).endswith("ready")),
        "future_blocked_count": sum(1 for entry in entries if entry["status"] == "future_blocked"),
        "entries": entries,
    }


def render_ability_shell_roster_summary(roster: dict[str, Any]) -> str:
    lines = [
        f"schema_version: {roster.get('schema_version')}",
        f"shell_bank_schema_version: {roster.get('shell_bank_schema_version')}",
        f"client_patch_required: {str(bool(roster.get('client_patch_required'))).lower()}",
        f"ready_count: {roster.get('ready_count')}",
        f"future_blocked_count: {roster.get('future_blocked_count')}",
        "ability_types:",
    ]
    for entry in roster.get("entries") or []:
        families = ", ".join(
            f"{family['family_id']}[{family['slot_range_start']}-{family['slot_range_end']}]"
            for family in entry.get("shell_families") or []
        )
        if not families:
            families = "none"
        lines.append(f"- {entry.get('ability_type')} | {entry.get('status')} | {families}")
    return "\n".join(lines)


def _ability_roster_notes(ability_type: str, status: str) -> list[str]:
    if status == "behavior_variant_ready":
        return [
            "Use an existing shell family for client targeting/presentation and bind specialized behavior in native runtime.",
        ]
    if status == "compatibility_ready":
        return [
            "Compatibility family is ready for the existing lane; add a generic family only when multiple new visible buttons need it.",
        ]
    if status == "ready":
        return ["Use stock spells as seed data only; WM shell IDs remain the permanent player-facing carrier."]
    return []


def build_scene_action_roster() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for action_kind in sorted(NATIVE_ACTION_KIND_BY_ID):
        native = NATIVE_ACTION_KIND_BY_ID[action_kind]
        status = _scene_action_status(action_kind)
        entries.append(
            {
                "native_action_kind": action_kind,
                "category": native.category,
                "default_risk": native.default_risk,
                "implemented": native.implemented,
                "default_enabled": native.default_enabled,
                "release_allowed": action_kind in _SCENE_ALLOWED_ACTION_KINDS,
                "status": status,
                "description": native.description,
                "notes": _scene_action_notes(action_kind, status),
            }
        )
    return {
        "schema_version": "wm.scene_action_roster.v1",
        "ready_count": sum(1 for entry in entries if entry["status"] == "scene_ready"),
        "blocked_future_count": sum(1 for entry in entries if entry["status"] == "blocked_future"),
        "entries": entries,
    }


def render_scene_action_roster_summary(roster: dict[str, Any]) -> str:
    lines = [
        f"schema_version: {roster.get('schema_version')}",
        f"ready_count: {roster.get('ready_count')}",
        f"blocked_future_count: {roster.get('blocked_future_count')}",
        "scene_actions:",
    ]
    for entry in roster.get("entries") or []:
        if entry.get("status") not in {"scene_ready", "blocked_future"}:
            continue
        lines.append(
            "- "
            f"{entry.get('native_action_kind')} | "
            f"{entry.get('status')} | "
            f"implemented={str(bool(entry.get('implemented'))).lower()} | "
            f"risk={entry.get('default_risk')}"
        )
    return "\n".join(lines)


def _scene_action_status(action_kind: str) -> str:
    native = NATIVE_ACTION_KIND_BY_ID[action_kind]
    if action_kind in _SCENE_UNSUPPORTED_MESSAGES:
        return "blocked_future"
    if action_kind in _SCENE_ALLOWED_ACTION_KINDS:
        return "scene_ready" if native.implemented else "registered_not_implemented"
    if native.category in {"world_object", "environment"} and not native.implemented:
        return "registered_not_implemented"
    return "not_scene_release_allowed"


def _scene_action_notes(action_kind: str, status: str) -> list[str]:
    if action_kind in _SCENE_UNSUPPORTED_MESSAGES:
        return [_SCENE_UNSUPPORTED_MESSAGES[action_kind]]
    if status == "scene_ready":
        return ["Allowed in native scene releases; policy/scope/live proof are still required before WORKING status."]
    if status == "registered_not_implemented":
        return ["Registered in the native action catalog but not ready for scene releases."]
    return []


def audit_content_release_tree(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    entries: list[dict[str, Any]] = []
    if not root_path.is_dir():
        return {
            "schema_version": "wm.content_release_audit.v1",
            "root": str(root_path),
            "spec_count": 0,
            "ok_count": 0,
            "broken_count": 1,
            "entries": [
                {
                    "path": str(root_path),
                    "ok": False,
                    "schema_version": None,
                    "content_kind": None,
                    "quest_kind": None,
                    "issue_count": 1,
                    "issues": [
                        {
                            "path": "root",
                            "message": "Audit root must be an existing directory.",
                            "severity": "error",
                        }
                    ],
                    "plan_status": None,
                }
            ],
        }
    for path in sorted(root_path.rglob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entries.append(
                {
                    "path": str(path),
                    "ok": False,
                    "schema_version": None,
                    "content_kind": None,
                    "quest_kind": None,
                    "issue_count": 1,
                    "issues": [
                        {
                            "path": "",
                            "message": f"Could not read JSON spec: {exc}",
                            "severity": "error",
                        }
                    ],
                    "plan_status": None,
                }
            )
            continue
        result = validate_content_release_spec(raw if isinstance(raw, dict) else {})
        entry = {
            "path": str(path),
            "ok": result.ok,
            "schema_version": result.schema_version,
            "content_kind": result.content_kind,
            "quest_kind": result.quest_kind,
            "issue_count": len(result.issues),
            "issues": [issue.to_dict() for issue in result.issues],
            "plan_status": None,
        }
        if result.ok and isinstance(raw, dict):
            try:
                entry["plan_status"] = build_content_release_plan(raw).status
            except ContentReleaseSpecError as exc:
                entry["ok"] = False
                entry["issue_count"] = int(entry["issue_count"]) + 1
                entry["issues"] = [
                    *entry["issues"],
                    {"path": "plan", "message": str(exc), "severity": "error"},
                ]
        entries.append(entry)
    return {
        "schema_version": "wm.content_release_audit.v1",
        "root": str(root_path),
        "spec_count": len(entries),
        "ok_count": sum(1 for entry in entries if entry["ok"]),
        "broken_count": sum(1 for entry in entries if not entry["ok"]),
        "entries": entries,
    }


def render_content_release_audit_summary(audit: dict[str, Any]) -> str:
    lines = [
        f"schema_version: {audit.get('schema_version')}",
        f"root: {audit.get('root')}",
        f"spec_count: {audit.get('spec_count')}",
        f"ok_count: {audit.get('ok_count')}",
        f"broken_count: {audit.get('broken_count')}",
        "specs:",
    ]
    for entry in audit.get("entries") or []:
        lines.append(
            "- "
            f"{entry.get('path')} | "
            f"ok={str(bool(entry.get('ok'))).lower()} | "
            f"{entry.get('schema_version')} | "
            f"plan={entry.get('plan_status')}"
        )
        if not entry.get("ok"):
            for issue in entry.get("issues") or []:
                lines.append(f"  issue: {issue.get('path')} | {issue.get('message')}")
    if not audit.get("entries"):
        lines.append("- none")
    return "\n".join(lines)


def _validate_repeatable_bounty(raw: dict[str, Any], *, issues: list[ReleaseIssue]) -> None:
    if raw.get("repeatable") is not True:
        issues.append(ReleaseIssue(path="repeatable", message="Repeatable bounty specs must set repeatable=true."))
    if str(raw.get("slot_policy") or "") not in {"fresh_reserved_or_existing_active_repeatable", "fresh_reserved_required"}:
        issues.append(
            ReleaseIssue(
                path="slot_policy",
                message="Repeatable bounty slot_policy must be fresh_reserved_or_existing_active_repeatable or fresh_reserved_required.",
            )
        )
    quest = _dict_or_issue(raw.get("quest"), "quest", issues=issues)
    objective = _dict_or_issue(raw.get("objective"), "objective", issues=issues)
    reward = _dict_or_issue(raw.get("reward", {}), "reward", issues=issues, required=False)
    _validate_object_keys(quest, allowed=_QUEST_KEYS, path="quest", issues=issues)
    _validate_object_keys(objective, allowed=_OBJECTIVE_KEYS, path="objective", issues=issues)
    _validate_object_keys(reward, allowed=_REWARD_KEYS, path="reward", issues=issues)
    _validate_runtime_sync(raw.get("runtime_sync"), issues=issues)
    _require_template_flag(quest, path="quest.template_defaults.SpecialFlags", flag=1, issues=issues)
    _require_objective_kind(objective, expected="kill", path="objective.kind", issues=issues)
    _require_positive_int(objective, "target_entry", path="objective.target_entry", issues=issues)
    _require_positive_int(objective, "kill_count", path="objective.kill_count", issues=issues)
    _validate_level_pair(quest, issues=issues)


def _validate_one_shot(raw: dict[str, Any], *, issues: list[ReleaseIssue]) -> None:
    if raw.get("repeatable") is not False:
        issues.append(ReleaseIssue(path="repeatable", message="One-shot quest specs must set repeatable=false."))
    if str(raw.get("slot_policy") or "") != "fresh_reserved_required":
        issues.append(ReleaseIssue(path="slot_policy", message="One-shot quest specs require slot_policy=fresh_reserved_required."))
    quest = _dict_or_issue(raw.get("quest"), "quest", issues=issues)
    objective = _dict_or_issue(raw.get("objective"), "objective", issues=issues)
    reward = _dict_or_issue(raw.get("reward", {}), "reward", issues=issues, required=False)
    _validate_object_keys(quest, allowed=_QUEST_KEYS, path="quest", issues=issues)
    _validate_object_keys(objective, allowed=_OBJECTIVE_KEYS, path="objective", issues=issues)
    _validate_object_keys(reward, allowed=_REWARD_KEYS, path="reward", issues=issues)
    _validate_runtime_sync(raw.get("runtime_sync"), issues=issues)
    links = raw.get("links", [])
    if links not in (None, []) and not (isinstance(links, list) and len(links) == 0):
        issues.append(ReleaseIssue(path="links", message="One-shot quests must not declare links; use story_arc for linked quests."))
    template_defaults = _template_defaults(quest)
    if _int_value(template_defaults.get("SpecialFlags")) & 1:
        issues.append(ReleaseIssue(path="quest.template_defaults.SpecialFlags", message="One-shot quests must not set repeatable SpecialFlags bit 1."))
    for field_name in sorted(_CHAIN_FIELDS):
        if field_name in template_defaults and _int_value(template_defaults.get(field_name)) != 0:
            issues.append(
                ReleaseIssue(
                    path=f"quest.template_defaults.{field_name}",
                    message="One-shot quests must not use quest-chain fields; use story_arc.",
                )
            )
    _validate_level_pair(quest, issues=issues)


def _validate_story_arc(raw: dict[str, Any], *, issues: list[ReleaseIssue]) -> None:
    if raw.get("arc_key") in (None, ""):
        issues.append(ReleaseIssue(path="arc_key", message="Story arc specs require arc_key."))
    nodes = _list_or_issue(raw.get("nodes"), "nodes", issues=issues)
    edges = _list_or_issue(raw.get("edges"), "edges", issues=issues)
    fork_groups = _list_or_issue(raw.get("fork_groups", []), "fork_groups", issues=issues, required=False)
    journey_updates = _dict_or_issue(raw.get("journey_updates", {}), "journey_updates", issues=issues, required=False)
    _validate_object_keys(journey_updates, allowed=_JOURNEY_UPDATE_KEYS, path="journey_updates", issues=issues)
    _validate_runtime_sync(raw.get("runtime_sync"), issues=issues)

    if len(nodes) < 2:
        issues.append(ReleaseIssue(path="nodes", message="Story arcs must contain at least two quest nodes."))
    if not edges:
        issues.append(ReleaseIssue(path="edges", message="Story arcs must contain at least one edge between quest nodes."))

    node_keys: set[str] = set()
    for index, node in enumerate(nodes):
        path = f"nodes[{index}]"
        if not isinstance(node, dict):
            issues.append(ReleaseIssue(path=path, message="Story arc nodes must be objects."))
            continue
        _validate_object_keys(node, allowed=_NODE_KEYS, path=path, issues=issues)
        node_key = str(node.get("node_key") or "")
        if not node_key:
            issues.append(ReleaseIssue(path=f"{path}.node_key", message="Story arc nodes require node_key."))
        elif node_key in node_keys:
            issues.append(ReleaseIssue(path=f"{path}.node_key", message=f"Duplicate story arc node_key `{node_key}`."))
        else:
            node_keys.add(node_key)
        quest_schema = str(node.get("quest_schema") or "")
        if quest_schema not in {ONE_SHOT_SCHEMA, "one_shot"}:
            issues.append(ReleaseIssue(path=f"{path}.quest_schema", message="Story arc nodes must use one-shot quest schemas."))
        if node.get("fresh_reserved_required") is not True:
            issues.append(ReleaseIssue(path=f"{path}.fresh_reserved_required", message="Story arc quest nodes require fresh reserved quest IDs."))

    for index, edge in enumerate(edges):
        path = f"edges[{index}]"
        if not isinstance(edge, dict):
            issues.append(ReleaseIssue(path=path, message="Story arc edges must be objects."))
            continue
        _validate_object_keys(edge, allowed=_EDGE_KEYS, path=path, issues=issues)
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source not in node_keys:
            issues.append(ReleaseIssue(path=f"{path}.from", message=f"Unknown source node `{source}`."))
        if target not in node_keys:
            issues.append(ReleaseIssue(path=f"{path}.to", message=f"Unknown target node `{target}`."))
        if source and source == target:
            issues.append(ReleaseIssue(path=path, message="Story arc edges must not point a node to itself."))
        if str(edge.get("kind") or "") not in _EDGE_KINDS:
            issues.append(ReleaseIssue(path=f"{path}.kind", message=f"Unsupported story arc edge kind `{edge.get('kind')}`."))

    for index, group in enumerate(fork_groups):
        path = f"fork_groups[{index}]"
        if not isinstance(group, dict):
            issues.append(ReleaseIssue(path=path, message="Story arc fork groups must be objects."))
            continue
        _validate_object_keys(group, allowed=_FORK_GROUP_KEYS, path=path, issues=issues)
        choices = group.get("choice_node_keys")
        if not isinstance(choices, list) or len(choices) < 2:
            issues.append(ReleaseIssue(path=f"{path}.choice_node_keys", message="Fork groups require at least two choice nodes."))
            continue
        normalized_choices = [str(choice) for choice in choices]
        if len(set(normalized_choices)) != len(normalized_choices):
            issues.append(ReleaseIssue(path=f"{path}.choice_node_keys", message="Fork choice nodes must be unique."))
        for choice in normalized_choices:
            if choice not in node_keys:
                issues.append(ReleaseIssue(path=f"{path}.choice_node_keys", message=f"Unknown fork choice node `{choice}`."))
        if str(group.get("lock_policy") or "") not in _FORK_LOCK_POLICIES:
            issues.append(
                ReleaseIssue(
                    path=f"{path}.lock_policy",
                    message="Fork groups must use lock_policy=first_turn_in_locks_others.",
                )
            )
        if not str(journey_updates.get("branch_key") or ""):
            issues.append(
                ReleaseIssue(
                    path="journey_updates.branch_key",
                    message="Forked story arcs must record a branch_key so the first completed branch can lock sibling choices.",
                )
            )


def _validate_ability_shell_power(raw: dict[str, Any], *, issues: list[ReleaseIssue]) -> None:
    for key in ("ability_key", "ability_type", "shell_family", "slot_policy", "behavior_kind"):
        if raw.get(key) in (None, ""):
            issues.append(ReleaseIssue(path=key, message=f"{key} is required for ability shell releases."))

    ability_type = str(raw.get("ability_type") or "")
    shell_family = str(raw.get("shell_family") or "")
    allowed_families = _ABILITY_TYPE_FAMILIES.get(ability_type)
    if ability_type in _ABILITY_UNSUPPORTED_TYPES:
        issues.append(ReleaseIssue(path="ability_type", message=_ABILITY_UNSUPPORTED_TYPES[ability_type]))
    elif allowed_families is None:
        issues.append(ReleaseIssue(path="ability_type", message=f"Unsupported ability_type `{ability_type}`."))
    elif shell_family not in allowed_families:
        choices = ", ".join(sorted(allowed_families))
        issues.append(ReleaseIssue(path="shell_family", message=f"ability_type `{ability_type}` requires shell_family in: {choices}."))

    if ability_type in _ABILITY_VARIANT_TYPES and raw.get("behavior_variant") is not True:
        issues.append(
            ReleaseIssue(
                path="behavior_variant",
                message=f"ability_type `{ability_type}` is a behavior variant over an existing shell family and must set behavior_variant=true.",
            )
        )

    if str(raw.get("slot_policy") or "") not in _ABILITY_SLOT_POLICIES:
        issues.append(
            ReleaseIssue(
                path="slot_policy",
                message=f"slot_policy must be one of: {', '.join(sorted(_ABILITY_SLOT_POLICIES))}.",
            )
        )

    client_truth = _dict_or_issue(raw.get("client_truth"), "client_truth", issues=issues)
    runtime = _dict_or_issue(raw.get("runtime"), "runtime", issues=issues)
    seed = _dict_or_issue(raw.get("seed", {}), "seed", issues=issues, required=False)
    _validate_object_keys(client_truth, allowed=_CLIENT_TRUTH_KEYS, path="client_truth", issues=issues)
    _validate_object_keys(runtime, allowed=_ABILITY_RUNTIME_KEYS, path="runtime", issues=issues)
    _validate_object_keys(seed, allowed=_ABILITY_SEED_KEYS, path="seed", issues=issues)

    if client_truth.get("client_patch_required") is not True:
        issues.append(
            ReleaseIssue(
                path="client_truth.client_patch_required",
                message="Shell-backed abilities must explicitly require client patch truth.",
            )
        )
    for key in ("server_dbc_required", "spellbook_button_required"):
        if key in client_truth and not isinstance(client_truth.get(key), bool):
            issues.append(ReleaseIssue(path=f"client_truth.{key}", message=f"{key} must be boolean."))
    if runtime.get("native_behavior_required") is not True:
        issues.append(
            ReleaseIssue(
                path="runtime.native_behavior_required",
                message="Shell-backed abilities must explicitly require native behavior or native runtime ownership.",
            )
        )
    if seed and seed.get("stock_seed_spell_id") not in (None, "") and seed.get("seed_only") is not True:
        issues.append(
            ReleaseIssue(
                path="seed.seed_only",
                message="Stock spell IDs may be used only as seed/template/visual data, never as permanent carriers.",
            )
        )

    _validate_shell_family_and_id(raw=raw, shell_family=shell_family, issues=issues)


def _validate_shell_family_and_id(*, raw: dict[str, Any], shell_family: str, issues: list[ReleaseIssue]) -> None:
    try:
        bank = load_spell_shell_bank()
    except Exception as exc:  # pragma: no cover - defensive path for broken local contracts
        issues.append(ReleaseIssue(path="shell_family", message=f"Could not load spell shell bank: {exc}"))
        return
    if shell_family and bank.family_by_id(shell_family) is None:
        issues.append(ReleaseIssue(path="shell_family", message=f"Unknown shell_family `{shell_family}` in shell bank."))
    if raw.get("shell_spell_id") in (None, ""):
        return
    try:
        shell_spell_id = int(raw["shell_spell_id"])
    except (TypeError, ValueError):
        issues.append(ReleaseIssue(path="shell_spell_id", message="shell_spell_id must be an integer when provided."))
        return
    family = bank.family_for_spell(shell_spell_id)
    if family is None:
        issues.append(ReleaseIssue(path="shell_spell_id", message="shell_spell_id is not inside a known shell-bank family."))
    elif shell_family and family.family_id != shell_family:
        issues.append(
            ReleaseIssue(
                path="shell_spell_id",
                message=f"shell_spell_id {shell_spell_id} belongs to `{family.family_id}`, not `{shell_family}`.",
            )
        )


def _validate_item_managed_power(raw: dict[str, Any], *, issues: list[ReleaseIssue]) -> None:
    for key in ("item_key", "slot_policy"):
        if raw.get(key) in (None, ""):
            issues.append(ReleaseIssue(path=key, message=f"{key} is required for managed item power releases."))
    _require_positive_int(raw, "item_entry", path="item_entry", issues=issues)
    slot_policy = str(raw.get("slot_policy") or "")
    if slot_policy not in _ITEM_SLOT_POLICIES:
        issues.append(
            ReleaseIssue(
                path="slot_policy",
                message=f"slot_policy must be one of: {', '.join(sorted(_ITEM_SLOT_POLICIES))}.",
            )
        )
    if slot_policy == "fresh_item_slot_required":
        _require_positive_int(raw, "base_item_entry", path="base_item_entry", issues=issues)

    visibility = _dict_or_issue(raw.get("visibility"), "visibility", issues=issues)
    reward_integration = _dict_or_issue(raw.get("reward_integration"), "reward_integration", issues=issues)
    runtime = _dict_or_issue(raw.get("runtime"), "runtime", issues=issues)
    item_shape = _dict_or_issue(raw.get("item_shape"), "item_shape", issues=issues, required=False)
    effects = _list_or_issue(raw.get("effects"), "effects", issues=issues)

    _validate_object_keys(visibility, allowed=_ITEM_VISIBILITY_KEYS, path="visibility", issues=issues)
    _validate_object_keys(reward_integration, allowed=_ITEM_REWARD_INTEGRATION_KEYS, path="reward_integration", issues=issues)
    _validate_object_keys(runtime, allowed=_ITEM_RUNTIME_KEYS, path="runtime", issues=issues)
    _validate_item_shape(item_shape, issues=issues)

    if visibility.get("player_visible_state_required") is not True:
        issues.append(
            ReleaseIssue(
                path="visibility.player_visible_state_required",
                message="Managed item powers must have player-visible state.",
            )
        )
    if visibility.get("tooltip_required") is not True:
        issues.append(ReleaseIssue(path="visibility.tooltip_required", message="Managed item powers must require tooltip text."))
    if not any(_int_value(visibility.get(key)) > 0 for key in ("wearer_aura_spell_id", "target_aura_spell_id")):
        issues.append(
            ReleaseIssue(
                path="visibility",
                message="Managed item powers need a visible wearer or target aura spell id.",
            )
        )

    if runtime.get("native_behavior_required") is not True:
        issues.append(
            ReleaseIssue(
                path="runtime.native_behavior_required",
                message="Managed item powers must explicitly require native behavior ownership.",
            )
        )
    if runtime.get("audit_required") is not True:
        issues.append(ReleaseIssue(path="runtime.audit_required", message="Managed item powers must require audit."))
    if runtime.get("rollback_required") is not True:
        issues.append(ReleaseIssue(path="runtime.rollback_required", message="Managed item powers must require rollback."))

    if reward_integration.get("fresh_quest_required_when_reward_changes") is not True:
        issues.append(
            ReleaseIssue(
                path="reward_integration.fresh_quest_required_when_reward_changes",
                message="Changing visible quest rewards must require a fresh quest ID.",
            )
        )
    for key in ("quest_reward_allowed", "direct_grant_allowed", "cleanup_supported"):
        if key in reward_integration and not isinstance(reward_integration.get(key), bool):
            issues.append(ReleaseIssue(path=f"reward_integration.{key}", message=f"{key} must be boolean."))

    effect_keys: set[str] = set()
    if not effects:
        issues.append(ReleaseIssue(path="effects", message="Managed item power specs require at least one effect."))
    for index, effect in enumerate(effects):
        path = f"effects[{index}]"
        if not isinstance(effect, dict):
            issues.append(ReleaseIssue(path=path, message="Item effects must be objects."))
            continue
        _validate_object_keys(effect, allowed=_ITEM_EFFECT_KEYS, path=path, issues=issues)
        effect_key = str(effect.get("effect_key") or "")
        if not effect_key:
            issues.append(ReleaseIssue(path=f"{path}.effect_key", message="Item effects require effect_key."))
        elif effect_key in effect_keys:
            issues.append(ReleaseIssue(path=f"{path}.effect_key", message=f"Duplicate item effect_key `{effect_key}`."))
        else:
            effect_keys.add(effect_key)
        kind = str(effect.get("kind") or "")
        if kind not in _ITEM_EFFECT_KINDS:
            issues.append(
                ReleaseIssue(
                    path=f"{path}.kind",
                    message=f"kind must be one of: {', '.join(sorted(_ITEM_EFFECT_KINDS))}.",
                )
            )
        if kind in _ITEM_HIDDEN_EFFECT_KINDS:
            if str(effect.get("visible_state") or "").strip() == "":
                issues.append(
                    ReleaseIssue(
                        path=f"{path}.visible_state",
                        message="Hidden item effects must name the visible state that gates them.",
                    )
                )
            if effect.get("native_hook") is not True:
                issues.append(
                    ReleaseIssue(
                        path=f"{path}.native_hook",
                        message="Hidden item effects must be owned by an explicit native hook.",
                    )
                )
        if "amount_pct" in effect:
            _validate_positive_number(effect.get("amount_pct"), path=f"{path}.amount_pct", issues=issues)
        if "chance_pct" in effect:
            _validate_positive_number(effect.get("chance_pct"), path=f"{path}.chance_pct", issues=issues)
        if "duration_ms" in effect:
            _require_positive_int(effect, "duration_ms", path=f"{path}.duration_ms", issues=issues)
        if "spell_id" in effect:
            _require_positive_int(effect, "spell_id", path=f"{path}.spell_id", issues=issues)
        if "shell_spell_id" in effect:
            _require_positive_int(effect, "shell_spell_id", path=f"{path}.shell_spell_id", issues=issues)


def _validate_item_shape(item_shape: dict[str, Any], *, issues: list[ReleaseIssue]) -> None:
    if not item_shape:
        return
    _validate_object_keys(item_shape, allowed=_ITEM_SHAPE_KEYS, path="item_shape", issues=issues)
    _validate_choice(item_shape, "item_class", allowed=_ITEM_CLASSES, path="item_shape.item_class", issues=issues)
    _validate_choice(item_shape, "inventory_type", allowed=_ITEM_INVENTORY_TYPES, path="item_shape.inventory_type", issues=issues)
    _validate_choice(item_shape, "armor_subclass", allowed=_ITEM_ARMOR_SUBCLASSES, path="item_shape.armor_subclass", issues=issues)
    _validate_choice(item_shape, "weapon_subclass", allowed=_ITEM_WEAPON_SUBCLASSES, path="item_shape.weapon_subclass", issues=issues)
    _validate_choice(item_shape, "quality", allowed=_ITEM_QUALITIES, path="item_shape.quality", issues=issues)
    _validate_choice(item_shape, "binding", allowed=_ITEM_BINDINGS, path="item_shape.binding", issues=issues)
    for key in ("required_level", "stackable"):
        if key in item_shape and item_shape.get(key) not in (None, ""):
            _require_positive_int(item_shape, key, path=f"item_shape.{key}", issues=issues)


def _validate_scene_native_sequence(raw: dict[str, Any], *, issues: list[ReleaseIssue]) -> None:
    for key in ("scene_key", "scene_type", "slot_policy"):
        if raw.get(key) in (None, ""):
            issues.append(ReleaseIssue(path=key, message=f"{key} is required for scene releases."))

    scene_type = str(raw.get("scene_type") or "")
    if scene_type and scene_type not in _SCENE_TYPES:
        issues.append(
            ReleaseIssue(
                path="scene_type",
                message=f"scene_type must be one of: {', '.join(sorted(_SCENE_TYPES))}.",
            )
        )
    if str(raw.get("slot_policy") or "") not in _SCENE_SLOT_POLICIES:
        issues.append(
            ReleaseIssue(
                path="slot_policy",
                message=f"slot_policy must be one of: {', '.join(sorted(_SCENE_SLOT_POLICIES))}.",
            )
        )

    trigger = _dict_or_issue(raw.get("trigger"), "trigger", issues=issues)
    runtime = _dict_or_issue(raw.get("runtime"), "runtime", issues=issues)
    cleanup = _dict_or_issue(raw.get("cleanup", {}), "cleanup", issues=issues, required=False)
    steps = _list_or_issue(raw.get("steps"), "steps", issues=issues)

    _validate_object_keys(trigger, allowed=_SCENE_TRIGGER_KEYS, path="trigger", issues=issues)
    _validate_object_keys(runtime, allowed=_SCENE_RUNTIME_KEYS, path="runtime", issues=issues)
    _validate_object_keys(cleanup, allowed=_SCENE_CLEANUP_KEYS, path="cleanup", issues=issues)

    if str(trigger.get("kind") or "") not in _SCENE_TRIGGER_KINDS:
        issues.append(
            ReleaseIssue(
                path="trigger.kind",
                message=f"trigger.kind must be one of: {', '.join(sorted(_SCENE_TRIGGER_KINDS))}.",
            )
        )
    if trigger.get("source_event_required") is not True and str(trigger.get("kind") or "") != "manual_operator":
        issues.append(
            ReleaseIssue(
                path="trigger.source_event_required",
                message="Event-driven scenes must set source_event_required=true; use manual_operator only for manual lab scenes.",
            )
        )
    if "max_event_age_seconds" in trigger:
        _require_positive_int(trigger, "max_event_age_seconds", path="trigger.max_event_age_seconds", issues=issues)

    if runtime.get("native_actions_required") is not True:
        issues.append(
            ReleaseIssue(
                path="runtime.native_actions_required",
                message="Scene releases must execute through typed native actions.",
            )
        )
    if runtime.get("audit_required") is not True:
        issues.append(ReleaseIssue(path="runtime.audit_required", message="Scene releases must require audit."))
    if runtime.get("player_scope_required") is not True:
        issues.append(
            ReleaseIssue(
                path="runtime.player_scope_required",
                message="Scene releases must require scoped player execution.",
            )
        )

    step_keys: set[str] = set()
    action_kinds: list[str] = []
    _validate_scene_steps(steps, parent_path="steps", step_keys=step_keys, action_kinds=action_kinds, issues=issues)

    cleanup_steps = cleanup.get("steps", [])
    if "steps" in cleanup and cleanup_steps not in (None, ""):
        if not isinstance(cleanup_steps, list):
            issues.append(ReleaseIssue(path="cleanup.steps", message="cleanup.steps must be a list when provided."))
        else:
            _validate_scene_steps(
                cleanup_steps,
                parent_path="cleanup.steps",
                step_keys=step_keys,
                action_kinds=action_kinds,
                issues=issues,
            )

    has_spawn = "creature_spawn" in action_kinds
    has_despawn = "creature_despawn" in action_kinds
    if has_spawn:
        if cleanup.get("required") is not True:
            issues.append(
                ReleaseIssue(
                    path="cleanup.required",
                    message="Scenes that spawn WM-owned creatures must set cleanup.required=true.",
                )
            )
        if not has_despawn:
            issues.append(
                ReleaseIssue(
                    path="cleanup.steps",
                    message="Scenes that spawn WM-owned creatures must include a creature_despawn step.",
                )
            )
        if "expires_seconds" in cleanup:
            _require_positive_int(cleanup, "expires_seconds", path="cleanup.expires_seconds", issues=issues)
    elif cleanup.get("required") not in (None, False):
        issues.append(
            ReleaseIssue(
                path="cleanup.required",
                message="cleanup.required=true is reserved for scenes with explicit owned-object cleanup.",
            )
        )


def _validate_scene_steps(
    steps: list[Any],
    *,
    parent_path: str,
    step_keys: set[str],
    action_kinds: list[str],
    issues: list[ReleaseIssue],
) -> None:
    if not steps:
        issues.append(ReleaseIssue(path=parent_path, message="Scene releases require at least one step."))
        return
    if len(steps) > 12:
        issues.append(ReleaseIssue(path=parent_path, message="Scene releases are capped at 12 steps per release."))
    for index, step in enumerate(steps):
        path = f"{parent_path}[{index}]"
        if not isinstance(step, dict):
            issues.append(ReleaseIssue(path=path, message="Scene release steps must be objects."))
            continue
        _validate_object_keys(step, allowed=_SCENE_STEP_KEYS, path=path, issues=issues)
        step_key = str(step.get("step_key") or "")
        if not step_key:
            issues.append(ReleaseIssue(path=f"{path}.step_key", message="Scene steps require step_key."))
        elif step_key in step_keys:
            issues.append(ReleaseIssue(path=f"{path}.step_key", message=f"Duplicate scene step_key `{step_key}`."))
        else:
            step_keys.add(step_key)

        action_kind = str(step.get("native_action_kind") or "")
        _validate_scene_action_kind(action_kind, path=f"{path}.native_action_kind", issues=issues)
        if action_kind:
            action_kinds.append(action_kind)

        payload = _dict_or_issue(step.get("payload", {}), f"{path}.payload", issues=issues, required=False)
        risk_level = str(step.get("risk_level") or "")
        if risk_level not in {"low", "medium", "high"}:
            issues.append(ReleaseIssue(path=f"{path}.risk_level", message="risk_level must be low, medium, or high."))
        if step.get("idempotency_suffix") in (None, ""):
            issues.append(
                ReleaseIssue(
                    path=f"{path}.idempotency_suffix",
                    message="Scene steps require a stable idempotency_suffix.",
                )
            )
        if "delay_seconds" in step:
            _validate_non_negative_number(step.get("delay_seconds"), path=f"{path}.delay_seconds", issues=issues)
        if step.get("requires_live_proof") is not True:
            issues.append(
                ReleaseIssue(
                    path=f"{path}.requires_live_proof",
                    message="Scene steps must require live proof before release status can become WORKING.",
                )
            )
        _validate_scene_payload_contract(action_kind=action_kind, payload=payload, path=f"{path}.payload", issues=issues)


def _validate_scene_action_kind(action_kind: str, *, path: str, issues: list[ReleaseIssue]) -> None:
    if not action_kind:
        issues.append(ReleaseIssue(path=path, message="native_action_kind is required."))
        return
    native = NATIVE_ACTION_KIND_BY_ID.get(action_kind)
    if native is None:
        issues.append(ReleaseIssue(path=path, message=f"Unknown native action kind `{action_kind}`."))
        return
    if action_kind in _SCENE_UNSUPPORTED_MESSAGES:
        issues.append(ReleaseIssue(path=path, message=_SCENE_UNSUPPORTED_MESSAGES[action_kind]))
        return
    if not native.implemented:
        issues.append(ReleaseIssue(path=path, message=f"Native action kind `{action_kind}` is registered but not implemented."))
        return
    if action_kind not in _SCENE_ALLOWED_ACTION_KINDS:
        issues.append(
            ReleaseIssue(
                path=path,
                message=f"Native action kind `{action_kind}` is not allowed in scene releases.",
            )
        )


def _validate_scene_payload_contract(
    *,
    action_kind: str,
    payload: dict[str, Any],
    path: str,
    issues: list[ReleaseIssue],
) -> None:
    if action_kind == "player_chat_message":
        if not (str(payload.get("message") or "").strip() or str(payload.get("text") or "").strip()):
            issues.append(
                ReleaseIssue(
                    path=path,
                    message="player_chat_message payload needs message or text.",
                )
            )
    elif action_kind == "world_announce_to_player":
        _require_non_empty_string(payload, "message", path=f"{path}.message", issues=issues)
    elif action_kind in {"player_apply_aura", "player_remove_aura"}:
        _require_positive_int(payload, "spell_id", path=f"{path}.spell_id", issues=issues)
    elif action_kind == "player_cast_spell":
        _require_positive_int(payload, "spell_id", path=f"{path}.spell_id", issues=issues)
        _require_non_empty_string(payload, "target", path=f"{path}.target", issues=issues)
    elif action_kind == "player_restore_health_power":
        if "health_percent" not in payload and "power_percent" not in payload:
            issues.append(
                ReleaseIssue(
                    path=path,
                    message="player_restore_health_power payload needs health_percent or power_percent.",
                )
            )
    elif action_kind == "player_set_display_id":
        _require_positive_int(payload, "display_id", path=f"{path}.display_id", issues=issues)
    elif action_kind == "creature_spawn":
        _require_positive_int(payload, "creature_entry", path=f"{path}.creature_entry", issues=issues)
        _require_non_empty_string(payload, "arc_key", path=f"{path}.arc_key", issues=issues)
        if "duration_ms" in payload:
            _require_positive_int(payload, "duration_ms", path=f"{path}.duration_ms", issues=issues)
    elif action_kind in {"creature_despawn", "creature_say", "creature_emote", "creature_cast_spell", "creature_set_display_id", "creature_set_scale"}:
        _require_non_empty_string(payload, "arc_key", path=f"{path}.arc_key", issues=issues)
        if action_kind in {"creature_say", "creature_emote"}:
            _require_non_empty_string(payload, "text", path=f"{path}.text", issues=issues)
        elif action_kind == "creature_cast_spell":
            _require_positive_int(payload, "spell_id", path=f"{path}.spell_id", issues=issues)
            _require_non_empty_string(payload, "target", path=f"{path}.target", issues=issues)
        elif action_kind == "creature_set_display_id":
            _require_positive_int(payload, "display_id", path=f"{path}.display_id", issues=issues)
        elif action_kind == "creature_set_scale":
            _validate_positive_number(payload.get("scale"), path=f"{path}.scale", issues=issues)


def _collect_forbidden_key_issues(value: Any, *, path: str, issues: list[ReleaseIssue]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _FORBIDDEN_KEY_PARTS):
                issues.append(
                    ReleaseIssue(
                        path=f"{path}.{key}" if path else str(key),
                        message="Forbidden freeform mutation-style release field.",
                    )
                )
            _collect_forbidden_key_issues(nested, path=f"{path}.{key}" if path else str(key), issues=issues)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _collect_forbidden_key_issues(nested, path=f"{path}[{index}]", issues=issues)


def _collect_unknown_key_issues(value: dict[str, Any], *, allowed: set[str], path: str, issues: list[ReleaseIssue]) -> None:
    unknown = sorted(set(value) - allowed)
    for key in unknown:
        issues.append(ReleaseIssue(path=f"{path}.{key}" if path else str(key), message="Unsupported release field."))


def _validate_object_keys(value: dict[str, Any], *, allowed: set[str], path: str, issues: list[ReleaseIssue]) -> None:
    if value:
        _collect_unknown_key_issues(value, allowed=allowed, path=path, issues=issues)


def _validate_choice(value: dict[str, Any], key: str, *, allowed: set[str], path: str, issues: list[ReleaseIssue]) -> None:
    if key not in value or value.get(key) in (None, ""):
        return
    choice = str(value.get(key))
    if choice not in allowed:
        issues.append(ReleaseIssue(path=path, message=f"Field must be one of: {', '.join(sorted(allowed))}."))


def _validate_runtime_sync(value: Any, *, issues: list[ReleaseIssue]) -> None:
    if value in (None, ""):
        return
    if not isinstance(value, dict):
        issues.append(ReleaseIssue(path="runtime_sync", message="runtime_sync must be an object when provided."))
        return
    _collect_unknown_key_issues(value, allowed=_RUNTIME_SYNC_KEYS, path="runtime_sync", issues=issues)


def _dict_or_issue(value: Any, path: str, *, issues: list[ReleaseIssue], required: bool = True) -> dict[str, Any]:
    if value in (None, ""):
        if required:
            issues.append(ReleaseIssue(path=path, message=f"{path} is required."))
        return {}
    if not isinstance(value, dict):
        issues.append(ReleaseIssue(path=path, message=f"{path} must be an object."))
        return {}
    return dict(value)


def _list_or_issue(value: Any, path: str, *, issues: list[ReleaseIssue], required: bool = True) -> list[Any]:
    if value in (None, ""):
        if required:
            issues.append(ReleaseIssue(path=path, message=f"{path} is required."))
        return []
    if not isinstance(value, list):
        issues.append(ReleaseIssue(path=path, message=f"{path} must be a list."))
        return []
    return list(value)


def _template_defaults(quest: dict[str, Any]) -> dict[str, Any]:
    value = quest.get("template_defaults") if isinstance(quest, dict) else {}
    return dict(value) if isinstance(value, dict) else {}


def _require_template_flag(quest: dict[str, Any], *, path: str, flag: int, issues: list[ReleaseIssue]) -> None:
    template_defaults = _template_defaults(quest)
    if not (_int_value(template_defaults.get("SpecialFlags")) & int(flag)):
        issues.append(ReleaseIssue(path=path, message=f"Required SpecialFlags bit {int(flag)} is not set."))


def _require_objective_kind(objective: dict[str, Any], *, expected: str, path: str, issues: list[ReleaseIssue]) -> None:
    if str(objective.get("kind") or "") != expected:
        issues.append(ReleaseIssue(path=path, message=f"Objective kind must be `{expected}`."))


def _require_positive_int(value: dict[str, Any], key: str, *, issues: list[ReleaseIssue], path: str | None = None) -> None:
    issue_path = path or key
    try:
        parsed = int(value.get(key))
    except (TypeError, ValueError):
        issues.append(ReleaseIssue(path=issue_path, message="Field must be a positive integer."))
        return
    if parsed <= 0:
        issues.append(ReleaseIssue(path=issue_path, message="Field must be a positive integer."))


def _require_non_empty_string(value: dict[str, Any], key: str, *, path: str, issues: list[ReleaseIssue]) -> None:
    if str(value.get(key) or "").strip() == "":
        issues.append(ReleaseIssue(path=path, message="Field must be a non-empty string."))


def _validate_non_negative_number(value: Any, *, path: str, issues: list[ReleaseIssue]) -> None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        issues.append(ReleaseIssue(path=path, message="Field must be a non-negative number."))
        return
    if parsed < 0:
        issues.append(ReleaseIssue(path=path, message="Field must be a non-negative number."))


def _validate_positive_number(value: Any, *, path: str, issues: list[ReleaseIssue]) -> None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        issues.append(ReleaseIssue(path=path, message="Field must be a positive number."))
        return
    if parsed <= 0:
        issues.append(ReleaseIssue(path=path, message="Field must be a positive number."))


def _validate_level_pair(quest: dict[str, Any], *, issues: list[ReleaseIssue]) -> None:
    if "quest_level" in quest:
        _require_positive_int(quest, "quest_level", path="quest.quest_level", issues=issues)
    if "min_level" in quest:
        _require_positive_int(quest, "min_level", path="quest.min_level", issues=issues)
    quest_level = _int_value(quest.get("quest_level"))
    min_level = _int_value(quest.get("min_level"))
    if quest_level and min_level and min_level > quest_level:
        issues.append(ReleaseIssue(path="quest.min_level", message="min_level must not exceed quest_level."))


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def render_validation_summary(result: ReleaseValidationResult) -> str:
    lines = [
        f"schema_version: {result.schema_version}",
        f"content_kind: {result.content_kind}",
        f"quest_kind: {result.quest_kind}",
        f"ok: {str(result.ok).lower()}",
        "issues:",
    ]
    if not result.issues:
        lines.append("- none")
    else:
        lines.extend(f"- {issue.path} | {issue.severity} | {issue.message}" for issue in result.issues)
    return "\n".join(lines)


def render_release_plan_summary(plan: ReleasePlan) -> str:
    lines = [
        f"schema_version: {plan.schema_version}",
        f"content_kind: {plan.content_kind}",
        f"player_guid: {plan.player_guid}",
        f"status: {plan.status}",
        "gates:",
    ]
    lines.extend(f"- {gate.gate} | {gate.status} | {gate.detail}" for gate in plan.gates)
    lines.append("commands:")
    if plan.commands:
        lines.extend(f"- {command}" for command in plan.commands)
    else:
        lines.append("- none")
    lines.append("notes:")
    if plan.notes:
        lines.extend(f"- {note}" for note in plan.notes)
    else:
        lines.append("- none")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.content.release")
    parser.add_argument("spec_json", type=Path, nargs="?")
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--ability-roster", action="store_true")
    parser.add_argument("--scene-action-roster", action="store_true")
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--force", action="store_true", help="Allow --write-packet-dir to overwrite existing packet files.")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--emit-control-scene", action="store_true")
    output_group.add_argument("--emit-journey-plan", action="store_true")
    output_group.add_argument("--emit-branch-lock-plan", action="store_true")
    output_group.add_argument("--plan", action="store_true")
    output_group.add_argument("--packet", action="store_true")
    output_group.add_argument("--write-packet-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.ability_roster:
        roster = build_ability_shell_roster()
        if args.summary:
            print(render_ability_shell_roster_summary(roster))
        else:
            print(json.dumps(roster, indent=2, ensure_ascii=False))
        return 0
    if args.scene_action_roster:
        roster = build_scene_action_roster()
        if args.summary:
            print(render_scene_action_roster_summary(roster))
        else:
            print(json.dumps(roster, indent=2, ensure_ascii=False))
        return 0
    if args.audit_dir is not None:
        audit = audit_content_release_tree(args.audit_dir)
        if args.summary:
            print(render_content_release_audit_summary(audit))
        else:
            print(json.dumps(audit, indent=2, ensure_ascii=False))
        return 0 if int(audit["broken_count"]) == 0 else 2
    if args.spec_json is None:
        parser.error("spec_json is required unless --ability-roster, --scene-action-roster, or --audit-dir is used.")
    raw = json.loads(args.spec_json.read_text(encoding="utf-8"))
    if args.player_guid is not None and isinstance(raw, dict):
        raw = dict(raw)
        raw["player_guid"] = int(args.player_guid)
    result = validate_content_release_spec(raw)
    if args.emit_control_scene:
        if not result.ok:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return 2
        try:
            print(json.dumps(compile_scene_release_to_control_scene(raw), indent=2, ensure_ascii=False))
        except ContentReleaseSpecError as exc:
            print(str(exc))
            return 2
        return 0
    if args.emit_journey_plan:
        if not result.ok:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return 2
        try:
            print(json.dumps(compile_story_arc_release_to_journey_plan(raw), indent=2, ensure_ascii=False))
        except ContentReleaseSpecError as exc:
            print(str(exc))
            return 2
        return 0
    if args.emit_branch_lock_plan:
        if not result.ok:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return 2
        try:
            print(json.dumps(compile_story_arc_release_to_branch_lock_plan(raw), indent=2, ensure_ascii=False))
        except ContentReleaseSpecError as exc:
            print(str(exc))
            return 2
        return 0
    if args.plan:
        if not result.ok:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return 2
        try:
            plan = build_content_release_plan(raw)
        except ContentReleaseSpecError as exc:
            print(str(exc))
            return 2
        if args.summary:
            print(render_release_plan_summary(plan))
        else:
            print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
        return 0
    if args.packet:
        if not result.ok:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return 2
        try:
            packet = build_content_release_packet(raw)
        except ContentReleaseSpecError as exc:
            print(str(exc))
            return 2
        if args.summary:
            print(render_content_release_packet_summary(packet))
        else:
            print(json.dumps(packet, indent=2, ensure_ascii=False))
        return 0
    if args.write_packet_dir is not None:
        if not result.ok:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return 2
        try:
            write_result = write_content_release_packet(
                raw,
                args.write_packet_dir,
                allow_overwrite=bool(args.force),
            )
        except ContentReleaseSpecError as exc:
            print(str(exc))
            return 2
        if args.summary:
            print(render_content_release_packet_write_summary(write_result))
        else:
            print(json.dumps(write_result, indent=2, ensure_ascii=False))
        return 0
    if args.summary:
        print(render_validation_summary(result))
    else:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
