from __future__ import annotations

import json
from pathlib import Path
import unittest

from wm.character.journey import JOURNEY_PLAN_SCHEMA_VERSION
from wm.character.journey import validate_journey_plan
from wm.content.release import ONE_SHOT_SCHEMA
from wm.content.release import REPEATABLE_BOUNTY_SCHEMA
from wm.content.release import SCENE_NATIVE_SEQUENCE_SCHEMA
from wm.content.release import STORY_ARC_SCHEMA
from wm.content.release import STORY_ARC_BRANCH_LOCK_PLAN_SCHEMA
from wm.content.release import ABILITY_SHELL_POWER_SCHEMA
from wm.content.release import ContentReleaseSpecError
from wm.content.release import ITEM_MANAGED_POWER_SCHEMA
from wm.content.release import audit_content_release_tree
from wm.content.release import build_content_release_plan
from wm.content.release import build_content_release_packet
from wm.content.release import build_ability_shell_roster
from wm.content.release import build_scene_action_roster
from wm.content.release import compile_story_arc_release_to_branch_lock_plan
from wm.content.release import compile_story_arc_release_to_journey_plan
from wm.content.release import compile_scene_release_to_control_scene
from wm.content.release import load_content_release_spec
from wm.content.release import render_ability_shell_roster_summary
from wm.content.release import render_content_release_audit_summary
from wm.content.release import render_content_release_packet_summary
from wm.content.release import render_content_release_packet_write_summary
from wm.content.release import render_release_plan_summary
from wm.content.release import render_scene_action_roster_summary
from wm.content.release import validate_content_release_spec
from wm.content.release import write_content_release_packet


class ContentReleaseSpecTests(unittest.TestCase):
    def test_repository_content_release_examples_validate(self) -> None:
        for path in sorted(Path("control/examples/content_releases").rglob("*.json")):
            loaded = load_content_release_spec(path)
            result = validate_content_release_spec(loaded.to_dict())
            self.assertTrue(result.ok, f"{path}: {result.to_dict()}")

    def test_content_release_tree_audit_summarizes_examples(self) -> None:
        audit = audit_content_release_tree(Path("control/examples/content_releases"))
        summary = render_content_release_audit_summary(audit)

        self.assertGreaterEqual(audit["spec_count"], 1)
        self.assertEqual(audit["broken_count"], 0)
        self.assertEqual(audit["ok_count"], audit["spec_count"])
        self.assertIn("wm.content_release_audit.v1", summary)
        self.assertIn("plan=PLAN_READY", summary)

    def test_content_release_tree_audit_reports_invalid_specs(self) -> None:
        temp_path = Path(".pytest-tmp") / "content-release-audit" / "bad.json"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        bad = _one_shot()
        bad["reward"]["freeform_sql"] = "UPDATE quest_template SET RewardItem1=1"
        temp_path.write_text(json.dumps(bad), encoding="utf-8")

        audit = audit_content_release_tree(temp_path.parent)

        self.assertEqual(audit["spec_count"], 1)
        self.assertEqual(audit["broken_count"], 1)
        self.assertEqual(audit["entries"][0]["issues"][0]["path"], "reward.freeform_sql")

    def test_content_release_tree_audit_rejects_missing_root(self) -> None:
        audit = audit_content_release_tree(Path(".pytest-tmp") / "missing-content-release-root")

        self.assertEqual(audit["spec_count"], 0)
        self.assertEqual(audit["broken_count"], 1)
        self.assertEqual(audit["entries"][0]["issues"][0]["path"], "root")

    def test_repeatable_bounty_requires_repeatable_special_flag(self) -> None:
        spec = _repeatable_bounty()
        result = validate_content_release_spec(spec)

        self.assertTrue(result.ok, result.to_dict())

        spec["quest"]["template_defaults"]["SpecialFlags"] = 0
        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("quest.template_defaults.SpecialFlags", _issue_paths(result))

    def test_one_shot_rejects_links_and_chain_fields(self) -> None:
        spec = _one_shot()
        result = validate_content_release_spec(spec)

        self.assertTrue(result.ok, result.to_dict())

        spec["links"] = [{"to": "next"}]
        spec["quest"]["template_defaults"]["NextQuestID"] = 910201
        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("links", _issue_paths(result))
        self.assertIn("quest.template_defaults.NextQuestID", _issue_paths(result))

    def test_story_arc_accepts_linked_fork_and_requires_branch_record(self) -> None:
        spec = _story_arc()
        result = validate_content_release_spec(spec)

        self.assertTrue(result.ok, result.to_dict())

        spec["journey_updates"].pop("branch_key")
        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("journey_updates.branch_key", _issue_paths(result))

    def test_story_arc_rejects_unknown_edge_and_repeatable_node_schema(self) -> None:
        spec = _story_arc()
        spec["nodes"][1]["quest_schema"] = REPEATABLE_BOUNTY_SCHEMA
        spec["edges"][0]["to"] = "missing"

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("nodes[1].quest_schema", _issue_paths(result))
        self.assertIn("edges[0].to", _issue_paths(result))

    def test_story_arc_compiles_to_journey_plan(self) -> None:
        plan = compile_story_arc_release_to_journey_plan(_story_arc())

        self.assertEqual(plan["schema_version"], JOURNEY_PLAN_SCHEMA_VERSION)
        self.assertEqual(plan["arc_states"][0]["arc_key"], "jecia_choice_arc_v1")
        self.assertEqual(plan["arc_states"][0]["branch_key"], "pending_choice")
        self.assertEqual(plan["metadata"]["node_keys"], ["start", "choice_a", "choice_b"])
        validate_journey_plan(plan)

    def test_story_arc_branch_lock_plan_names_winner_and_loser_actions(self) -> None:
        spec = _story_arc()
        spec["nodes"][1]["quest_id"] = 910201
        spec["nodes"][2]["quest_id"] = 910202

        plan = compile_story_arc_release_to_branch_lock_plan(spec)

        self.assertEqual(plan["schema_version"], STORY_ARC_BRANCH_LOCK_PLAN_SCHEMA)
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["missing_quest_id_node_keys"], [])
        first_choice = plan["fork_groups"][0]["choices"][0]
        self.assertEqual(first_choice["winner_node_key"], "choice_a")
        self.assertEqual(first_choice["winner_quest_id"], 910201)
        self.assertEqual(first_choice["record_branch_key"], "pending_choice:choice_a")
        self.assertEqual(first_choice["loser_actions"][0]["native_action_kind"], "quest_remove")
        self.assertEqual(first_choice["loser_actions"][0]["payload"]["quest_id"], 910202)

    def test_story_arc_packet_includes_journey_branch_lock_and_proof(self) -> None:
        packet = build_content_release_packet(_story_arc())
        summary = render_content_release_packet_summary(packet)

        self.assertEqual(packet["schema_version"], "wm.content_release_packet.v1")
        self.assertEqual(packet["status"], "PACKET_READY")
        self.assertEqual([artifact["artifact_kind"] for artifact in packet["artifacts"]], [
            "journey_plan",
            "branch_lock_plan",
        ])
        self.assertIn("first completed choice", "\n".join(packet["live_proof_checklist"]))
        self.assertIn("journey_plan -> compiled-journey-plan.json", summary)

    def test_rejects_forbidden_mutation_fields(self) -> None:
        spec = _one_shot()
        spec["reward"]["freeform_sql"] = "UPDATE quest_template SET RewardItem1=1"

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("reward.freeform_sql", _issue_paths(result))

    def test_ability_release_requires_matching_shell_family(self) -> None:
        spec = _ability()
        result = validate_content_release_spec(spec)

        self.assertTrue(result.ok, result.to_dict())

        spec["shell_family"] = "ground_target_aoe"
        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("shell_family", _issue_paths(result))

    def test_ability_release_rejects_stock_seed_as_carrier(self) -> None:
        spec = _ability()
        spec["seed"]["seed_only"] = False

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("seed.seed_only", _issue_paths(result))

    def test_ability_release_validates_shell_spell_id_family(self) -> None:
        spec = _ability()
        spec["shell_spell_id"] = 946400

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("shell_spell_id", _issue_paths(result))

    def test_ability_release_rejects_future_specialized_types(self) -> None:
        spec = _ability()
        spec["ability_type"] = "gameobject_target"
        spec["shell_family"] = "unit_target_effect"

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("ability_type", _issue_paths(result))

    def test_ability_shell_roster_reports_ready_variants_and_blocked_types(self) -> None:
        roster = build_ability_shell_roster()
        entries = {entry["ability_type"]: entry for entry in roster["entries"]}
        summary = render_ability_shell_roster_summary(roster)

        self.assertEqual(roster["schema_version"], "wm.ability_shell_roster.v1")
        self.assertEqual(entries["targeted_effect_with_projectile"]["status"], "ready")
        self.assertEqual(entries["targeted_effect_with_projectile"]["shell_families"][0]["family_id"], "unit_target_projectile")
        self.assertEqual(entries["chain_jump"]["status"], "behavior_variant_ready")
        self.assertEqual(entries["summon_pet"]["status"], "compatibility_ready")
        self.assertEqual(entries["gameobject_target"]["status"], "future_blocked")
        self.assertIn("targeted_effect_with_projectile | ready", summary)

    def test_ability_packet_includes_matching_roster_entry(self) -> None:
        packet = build_content_release_packet(_ability())

        self.assertEqual(packet["artifacts"][0]["artifact_kind"], "ability_shell_roster_entry")
        self.assertEqual(packet["artifacts"][0]["payload"]["ability_type"], "targeted_effect_with_projectile")
        self.assertEqual(packet["artifacts"][0]["payload"]["status"], "ready")
        self.assertIn("Spellbook/action-bar presentation", packet["live_proof_checklist"][0])

    def test_scene_release_accepts_typed_native_sequence_with_owned_cleanup(self) -> None:
        spec = _scene()

        result = validate_content_release_spec(spec)

        self.assertTrue(result.ok, result.to_dict())

    def test_scene_release_requires_cleanup_for_owned_creature_spawn(self) -> None:
        spec = _scene()
        spec["cleanup"] = {"required": False}

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("cleanup.required", _issue_paths(result))
        self.assertIn("cleanup.steps", _issue_paths(result))

    def test_scene_release_rejects_weather_until_native_executor_exists(self) -> None:
        spec = _scene()
        spec["steps"] = [
            {
                "step_key": "storm",
                "native_action_kind": "zone_set_weather",
                "payload": {"weather_type": "rain", "grade": 1.0},
                "risk_level": "medium",
                "idempotency_suffix": "storm",
                "requires_live_proof": True,
            }
        ]
        spec["cleanup"] = {"required": False}

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("steps[0].native_action_kind", _issue_paths(result))

    def test_scene_release_rejects_debug_or_reward_actions(self) -> None:
        spec = _scene()
        spec["steps"][0]["native_action_kind"] = "debug_ping"

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("steps[0].native_action_kind", _issue_paths(result))

    def test_scene_action_roster_reports_ready_and_blocked_verbs(self) -> None:
        roster = build_scene_action_roster()
        entries = {entry["native_action_kind"]: entry for entry in roster["entries"]}
        summary = render_scene_action_roster_summary(roster)

        self.assertEqual(roster["schema_version"], "wm.scene_action_roster.v1")
        self.assertEqual(entries["creature_spawn"]["status"], "scene_ready")
        self.assertEqual(entries["world_announce_to_player"]["status"], "scene_ready")
        self.assertEqual(entries["zone_set_weather"]["status"], "blocked_future")
        self.assertEqual(entries["gameobject_spawn"]["status"], "blocked_future")
        self.assertEqual(entries["debug_ping"]["status"], "not_scene_release_allowed")
        self.assertIn("zone_set_weather | blocked_future", summary)

    def test_scene_release_compiles_to_control_scene(self) -> None:
        compiled = compile_scene_release_to_control_scene(_scene())

        self.assertEqual(compiled["schema_version"], "control.scene.v1")
        self.assertEqual(compiled["id"], "template_creature_marker_scene")
        self.assertEqual([step["native_action_kind"] for step in compiled["steps"]], [
            "creature_spawn",
            "creature_say",
            "creature_despawn",
        ])
        self.assertEqual(compiled["steps"][0]["idempotency_suffix"], "spawn")

    def test_scene_packet_includes_control_scene_artifact(self) -> None:
        packet = build_content_release_packet(_scene())

        self.assertEqual(packet["artifacts"][0]["artifact_kind"], "control_scene")
        self.assertEqual(packet["artifacts"][0]["payload"]["schema_version"], "control.scene.v1")
        self.assertTrue(any("Cleanup/despawn runs" in item for item in packet["live_proof_checklist"]))

    def test_packet_writer_emits_packet_and_artifact_files_without_overwrite(self) -> None:
        output_dir = Path(".pytest-tmp") / "content-release-packet-writer"
        result = write_content_release_packet(_scene(), output_dir, allow_overwrite=True)
        summary = render_content_release_packet_write_summary(result)

        self.assertEqual(result["schema_version"], "wm.content_release_packet_write.v1")
        self.assertEqual(result["status"], "WRITTEN")
        self.assertEqual(result["file_count"], 2)
        self.assertTrue((output_dir / "release_packet.json").exists())
        self.assertTrue((output_dir / "compiled-control-scene.json").exists())
        self.assertIn("release_packet", summary)

        with self.assertRaises(ContentReleaseSpecError):
            write_content_release_packet(_scene(), output_dir)

    def test_scene_release_plan_names_control_scene_workflow(self) -> None:
        plan = build_content_release_plan(_scene())
        summary = render_release_plan_summary(plan)

        self.assertEqual(plan.status, "PLAN_READY")
        self.assertIn("python -m wm.content.release <scene-spec.json> --emit-control-scene", plan.commands)
        self.assertIn("live_proof | required", summary)
        self.assertIn("Gameobject and real weather actions remain blocked", summary)

    def test_item_power_release_requires_visible_state_and_native_hooks(self) -> None:
        spec = _item_power()
        result = validate_content_release_spec(spec)

        self.assertTrue(result.ok, result.to_dict())

        spec["visibility"]["target_aura_spell_id"] = None
        spec["visibility"]["wearer_aura_spell_id"] = None
        spec["effects"][1]["visible_state"] = ""
        spec["effects"][1]["native_hook"] = False
        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("visibility", _issue_paths(result))
        self.assertIn("effects[1].visible_state", _issue_paths(result))
        self.assertIn("effects[1].native_hook", _issue_paths(result))

    def test_item_power_release_requires_fresh_quest_when_reward_changes(self) -> None:
        spec = _item_power()
        spec["reward_integration"]["fresh_quest_required_when_reward_changes"] = False

        result = validate_content_release_spec(spec)

        self.assertFalse(result.ok)
        self.assertIn("reward_integration.fresh_quest_required_when_reward_changes", _issue_paths(result))

    def test_item_packet_includes_managed_power_contract(self) -> None:
        packet = build_content_release_packet(_item_power())

        self.assertEqual(packet["artifacts"][0]["artifact_kind"], "managed_item_power_contract")
        self.assertEqual(packet["artifacts"][0]["payload"]["item_entry"], 910006)
        self.assertEqual(packet["artifacts"][0]["payload"]["hidden_effect_keys"], [
            "target_mark_proc",
            "spell_focus",
        ])
        self.assertIn("Hidden native effects", "\n".join(packet["live_proof_checklist"]))

    def test_item_power_release_plan_names_item_and_reward_gates(self) -> None:
        plan = build_content_release_plan(_item_power())

        gate_details = "\n".join(gate.detail for gate in plan.gates)
        self.assertEqual(plan.content_kind, "item")
        self.assertIn("Item entry 910006", gate_details)
        self.assertIn("reward-panel changes require fresh quest IDs", gate_details)
        self.assertIn("python -m wm.items.live_publish --draft-json <item-draft.json> --mode dry-run --summary", plan.commands)
        self.assertTrue(any("Hidden item effects must be gated" in note for note in plan.notes))

    def test_load_spec_applies_player_override_and_raises_for_invalid_specs(self) -> None:
        temp_path = Path(".pytest-tmp") / "content-release-one-shot.json"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(_one_shot()), encoding="utf-8")

        loaded = load_content_release_spec(temp_path, player_guid=777)

        self.assertEqual(loaded.player_guid, 777)
        self.assertEqual(loaded.schema_version, ONE_SHOT_SCHEMA)
        self.assertEqual(loaded.quest_kind, "one_shot")

        invalid = _one_shot()
        invalid["links"] = [{"to": "not_allowed"}]
        temp_path.write_text(json.dumps(invalid), encoding="utf-8")
        with self.assertRaises(ContentReleaseSpecError):
            load_content_release_spec(temp_path)


def _issue_paths(result) -> set[str]:
    return {issue.path for issue in result.issues}


def _repeatable_bounty() -> dict:
    return {
        "schema_version": REPEATABLE_BOUNTY_SCHEMA,
        "quest_kind": "repeatable_bounty",
        "player_guid": 5406,
        "slot_policy": "fresh_reserved_or_existing_active_repeatable",
        "repeatable": True,
        "quest": {
            "quest_level": 70,
            "min_level": 68,
            "grant_mode": "npc_start",
            "template_defaults": {"SpecialFlags": 1},
        },
        "objective": {
            "kind": "kill",
            "target_entry": 21059,
            "target_name": "Enraged Water Spirit",
            "kill_count": 6,
        },
        "reward": {
            "kind": "item",
            "item_entry": 910013,
            "item_count": 1,
            "fresh_visible_reward_ids_required": True,
        },
    }


def _one_shot() -> dict:
    return {
        "schema_version": ONE_SHOT_SCHEMA,
        "quest_kind": "one_shot",
        "player_guid": 5406,
        "slot_policy": "fresh_reserved_required",
        "repeatable": False,
        "quest": {
            "quest_level": 70,
            "min_level": 68,
            "grant_mode": "npc_start",
            "template_defaults": {"SpecialFlags": 0},
        },
        "objective": {
            "kind": "talk",
            "npc_entry": 21027,
            "npc_name": "Earthmender Wilda",
            "count": 1,
        },
        "reward": {
            "kind": "none",
            "fresh_visible_reward_ids_required": True,
        },
        "links": [],
    }


def _story_arc() -> dict:
    return {
        "schema_version": STORY_ARC_SCHEMA,
        "quest_kind": "story_arc",
        "player_guid": 5406,
        "arc_key": "jecia_choice_arc_v1",
        "nodes": [
            {
                "node_key": "start",
                "quest_schema": ONE_SHOT_SCHEMA,
                "fresh_reserved_required": True,
            },
            {
                "node_key": "choice_a",
                "quest_schema": ONE_SHOT_SCHEMA,
                "fresh_reserved_required": True,
            },
            {
                "node_key": "choice_b",
                "quest_schema": ONE_SHOT_SCHEMA,
                "fresh_reserved_required": True,
            },
        ],
        "edges": [
            {"from": "start", "to": "choice_a", "kind": "branch_unlocks"},
            {"from": "start", "to": "choice_b", "kind": "branch_unlocks"},
        ],
        "fork_groups": [
            {
                "group_key": "choose_first_wins",
                "choice_node_keys": ["choice_a", "choice_b"],
                "lock_policy": "first_turn_in_locks_others",
            }
        ],
        "journey_updates": {
            "stage_key": "choice_offered",
            "branch_key": "pending_choice",
        },
    }


def _ability() -> dict:
    return {
        "schema_version": ABILITY_SHELL_POWER_SCHEMA,
        "content_kind": "ability",
        "player_guid": 5406,
        "ability_key": "template_shadow_projectile",
        "ability_type": "targeted_effect_with_projectile",
        "shell_family": "unit_target_projectile",
        "shell_spell_id": 946000,
        "slot_policy": "fresh_shell_slot_required",
        "behavior_kind": "generic_projectile",
        "client_truth": {
            "client_patch_required": True,
            "server_dbc_required": True,
            "spellbook_button_required": True,
        },
        "runtime": {
            "native_behavior_required": True,
            "python_decision_required": True,
            "audit_required": True,
        },
        "seed": {
            "stock_seed_spell_id": 133,
            "seed_only": True,
        },
    }


def _scene() -> dict:
    return {
        "schema_version": SCENE_NATIVE_SEQUENCE_SCHEMA,
        "content_kind": "scene",
        "player_guid": 5406,
        "scene_key": "template_creature_marker_scene",
        "scene_type": "creature_marker",
        "slot_policy": "no_visible_id_required",
        "trigger": {
            "kind": "manual_operator",
            "source_event_required": False,
        },
        "runtime": {
            "native_actions_required": True,
            "audit_required": True,
            "player_scope_required": True,
            "control_scene_required": True,
        },
        "steps": [
            {
                "step_key": "spawn",
                "native_action_kind": "creature_spawn",
                "payload": {
                    "creature_entry": 920101,
                    "arc_key": "scene:{scene_id}:{player_guid}:{run_key}",
                    "duration_ms": 15000,
                    "distance": 4.0,
                },
                "risk_level": "medium",
                "idempotency_suffix": "spawn",
                "expected_effect": "A temporary WM-owned marker appears near the scoped player.",
                "requires_live_proof": True,
            },
            {
                "step_key": "say",
                "native_action_kind": "creature_say",
                "payload": {
                    "arc_key": "scene:{scene_id}:{player_guid}:{run_key}",
                    "text": "Marker established.",
                },
                "risk_level": "low",
                "idempotency_suffix": "say",
                "requires_live_proof": True,
            },
        ],
        "cleanup": {
            "required": True,
            "expires_seconds": 30,
            "steps": [
                {
                    "step_key": "despawn",
                    "native_action_kind": "creature_despawn",
                    "payload": {
                        "arc_key": "scene:{scene_id}:{player_guid}:{run_key}",
                    },
                    "risk_level": "medium",
                    "idempotency_suffix": "despawn",
                    "requires_live_proof": True,
                }
            ],
        },
    }


def _item_power() -> dict:
    return {
        "schema_version": ITEM_MANAGED_POWER_SCHEMA,
        "content_kind": "item",
        "player_guid": 5406,
        "item_key": "template_night_watchers_lens_power",
        "item_entry": 910006,
        "slot_policy": "existing_proven_item_slot_extension",
        "visibility": {
            "player_visible_state_required": True,
            "tooltip_required": True,
            "wearer_aura_spell_id": 132,
            "target_aura_spell_id": 770,
            "client_cache_risk": "existing_live_item_slot",
        },
        "runtime": {
            "native_behavior_required": True,
            "python_decision_required": False,
            "audit_required": True,
            "rollback_required": True,
        },
        "reward_integration": {
            "quest_reward_allowed": True,
            "fresh_quest_required_when_reward_changes": True,
            "direct_grant_allowed": True,
            "cleanup_supported": True,
        },
        "effects": [
            {
                "effect_key": "wearer_marker",
                "kind": "wearer_aura",
                "trigger": "equipped",
                "target": "self",
                "spell_id": 132,
            },
            {
                "effect_key": "target_mark_proc",
                "kind": "target_mark_proc",
                "trigger": "weapon_or_wand_hit",
                "target": "enemy",
                "visible_state": "target aura 770 from the Lens wearer",
                "native_hook": True,
                "chance_pct": 10,
                "duration_ms": 10000,
                "spell_id": 770,
            },
            {
                "effect_key": "spell_focus",
                "kind": "direct_spell_damage_bonus",
                "trigger": "non_wand_direct_spell_damage",
                "target": "marked_enemy",
                "visible_state": "target aura 770 from the Lens wearer",
                "native_hook": True,
                "amount_pct": 15,
            },
        ],
    }
