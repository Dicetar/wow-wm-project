from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any

from wm.content.release import ABILITY_SHELL_POWER_SCHEMA
from wm.content.release import ITEM_MANAGED_POWER_SCHEMA
from wm.content.release import REPEATABLE_BOUNTY_SCHEMA
from wm.content.release import SCENE_NATIVE_SEQUENCE_SCHEMA
from wm.content.release import STORY_ARC_SCHEMA
from wm.content.release import ContentReleaseSpecError
from wm.content.release import build_content_release_packet
from wm.content.release import validate_content_release_spec
from wm.content.release import write_content_release_packet


RELEASE_CANDIDATE_PACK_SCHEMA = "wm.release_candidate_pack.v1"


@dataclass(slots=True)
class ReleaseCandidate:
    candidate_key: str
    lane: str
    status: str
    score: int
    rationale: str
    release_spec: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    packet_status: str | None = None
    blockers: list[str] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_release_candidate_pack(
    context_pack: dict[str, Any],
    *,
    limit: int = 8,
    reserved_item_entry: int | None = None,
    base_item_entry: int | None = None,
    wearer_aura_spell_id: int = 132,
    target_aura_spell_id: int = 770,
) -> dict[str, Any]:
    generation = _generation_input(context_pack)
    player_guid = _player_guid(context_pack, generation)
    target = _target(context_pack, generation)
    target_entry = _positive_int(target.get("entry")) or 0
    target_name = str(target.get("name") or f"Target {target_entry}")
    target_slug = _slug(target_name)
    journey_eligibility = _journey_eligibility(generation)
    history = dict(generation.get("history") or {})
    trigger = dict(generation.get("trigger") or {})
    steering_text = _steering_text(generation)

    candidates = [
        _ready_candidate(
            lane="repeatable_bounty",
            candidate_key=f"{target_slug}_repeatable_bounty",
            score=70 + min(_positive_int(history.get("kill_count")) or 0, 10),
            rationale="Repeatable bounty is the lowest-risk release lane for a known hostile target.",
            spec=_repeatable_bounty_spec(
                player_guid=player_guid,
                target_entry=target_entry,
                target_name=target_name,
                history=history,
            ),
        ),
        _story_arc_candidate(
            player_guid=player_guid,
            target_slug=target_slug,
            target_name=target_name,
            target_entry=target_entry,
            journey_eligibility=journey_eligibility,
        ),
        _ready_candidate(
            lane="shell_ability",
            candidate_key=f"{target_slug}_targeted_projectile_power",
            score=82 if _contains_any(steering_text, {"power", "spell", "visible", "wild"}) else 62,
            rationale="Targeted projectile uses a ready shell family and keeps stock spell IDs as seed data only.",
            spec=_targeted_projectile_ability_spec(
                player_guid=player_guid,
                target_slug=target_slug,
                target_name=target_name,
            ),
        ),
        _ready_candidate(
            lane="native_scene",
            candidate_key=f"{target_slug}_area_pressure_scene",
            score=78 if trigger.get("event_type") in {"kill", "combat", "damage"} else 64,
            rationale="Area-pressure scene uses implemented player aura/restore/announcement verbs and no world-object cleanup.",
            spec=_area_pressure_scene_spec(
                player_guid=player_guid,
                target_slug=target_slug,
                target_name=target_name,
            ),
        ),
        _managed_item_power_candidate(
            player_guid=player_guid,
            target_slug=target_slug,
            target_name=target_name,
            reserved_item_entry=reserved_item_entry,
            base_item_entry=base_item_entry,
            wearer_aura_spell_id=wearer_aura_spell_id,
            target_aura_spell_id=target_aura_spell_id,
        ),
    ]

    ordered = sorted(candidates, key=lambda item: (-item.score, item.candidate_key))[: max(1, int(limit))]
    return {
        "schema_version": RELEASE_CANDIDATE_PACK_SCHEMA,
        "status": "READY" if any(candidate.status == "ready" for candidate in ordered) else "BLOCKED",
        "player_guid": player_guid,
        "target": {
            "entry": target_entry,
            "name": target_name,
            "slug": target_slug,
        },
        "journey": {
            "ready_for_arc_factory": bool(journey_eligibility.get("ready_for_arc_factory")),
            "blocked_reasons": list(journey_eligibility.get("blocked_reasons") or []),
            "active_arc_keys": list(journey_eligibility.get("active_arc_keys") or []),
            "unlock_refs": list(journey_eligibility.get("unlock_refs") or []),
            "reward_refs": list(journey_eligibility.get("reward_refs") or []),
        },
        "candidate_count": len(ordered),
        "candidates": [candidate.to_dict() for candidate in ordered],
        "notes": [
            "This pack is deterministic and non-mutating.",
            "LLM or operator edits must stay inside the emitted release schemas and rerun wm.content.release validation.",
        ],
    }


def render_release_candidate_pack_summary(pack: dict[str, Any]) -> str:
    target = pack.get("target") or {}
    lines = [
        f"schema_version: {pack.get('schema_version')}",
        f"status: {pack.get('status')}",
        f"player_guid: {pack.get('player_guid')}",
        f"target: {target.get('entry')} {target.get('name')}",
        f"candidate_count: {pack.get('candidate_count')}",
        "candidates:",
    ]
    for candidate in pack.get("candidates") or []:
        lines.append(
            "- "
            f"{candidate.get('candidate_key')} | "
            f"{candidate.get('lane')} | "
            f"{candidate.get('status')} | "
            f"score={candidate.get('score')}"
        )
        blockers = candidate.get("blockers") or []
        if blockers:
            lines.append(f"  blockers: {', '.join(str(item) for item in blockers)}")
    return "\n".join(lines)


def write_release_candidate_pack(
    context_pack: dict[str, Any],
    output_dir: str | Path,
    *,
    limit: int = 8,
    allow_overwrite: bool = False,
    reserved_item_entry: int | None = None,
    base_item_entry: int | None = None,
    wearer_aura_spell_id: int = 132,
    target_aura_spell_id: int = 770,
    write_packets: bool = False,
    write_test_manifest: bool = False,
) -> dict[str, Any]:
    pack = build_release_candidate_pack(
        context_pack,
        limit=limit,
        reserved_item_entry=reserved_item_entry,
        base_item_entry=base_item_entry,
        wearer_aura_spell_id=wearer_aura_spell_id,
        target_aura_spell_id=target_aura_spell_id,
    )
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written_files: list[dict[str, Any]] = []
    packet_writes: list[dict[str, Any]] = []
    candidate_artifacts: list[dict[str, Any]] = []

    def write_json(filename: str, payload: dict[str, Any], *, artifact_kind: str, candidate_key: str | None = None) -> None:
        target = destination / filename
        if target.exists() and not allow_overwrite:
            raise ValueError(f"Refusing to overwrite existing release-candidate file: {target}")
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        item = {"artifact_kind": artifact_kind, "path": str(target)}
        if candidate_key is not None:
            item["candidate_key"] = candidate_key
        written_files.append(item)

    write_json("release_candidate_pack.json", pack, artifact_kind="release_candidate_pack")
    for candidate in pack.get("candidates") or []:
        if candidate.get("status") != "ready" or not isinstance(candidate.get("release_spec"), dict):
            continue
        candidate_key = str(candidate["candidate_key"])
        spec_filename = f"{candidate_key}.release.json"
        spec_path = destination / spec_filename
        write_json(
            spec_filename,
            candidate["release_spec"],
            artifact_kind="release_spec",
            candidate_key=candidate_key,
        )
        artifact_entry: dict[str, Any] = {
            "candidate_key": candidate_key,
            "lane": str(candidate.get("lane") or ""),
            "release_spec_path": str(spec_path),
            "packet_dir": None,
            "packet_files": [],
        }
        if write_packets:
            packet_dir = destination / f"{candidate_key}.packet"
            packet_result = write_content_release_packet(
                candidate["release_spec"],
                packet_dir,
                allow_overwrite=allow_overwrite,
            )
            packet_writes.append({"candidate_key": candidate_key, **packet_result})
            artifact_entry["packet_dir"] = str(packet_dir)
            artifact_entry["packet_files"] = [str(item.get("path")) for item in packet_result.get("files") or []]
            for item in packet_result.get("files") or []:
                written_files.append(
                    {
                        "artifact_kind": f"release_packet:{item.get('artifact_kind')}",
                        "candidate_key": candidate_key,
                        "path": str(item.get("path")),
                    }
                )
        candidate_artifacts.append(artifact_entry)

    if write_test_manifest:
        manifest = build_release_test_manifest(pack, candidate_artifacts)
        write_json(
            "release_test_manifest.json",
            manifest,
            artifact_kind="release_test_manifest",
        )

    return {
        "schema_version": "wm.release_candidate_pack_write.v1",
        "status": "WRITTEN",
        "output_dir": str(destination),
        "file_count": len(written_files),
        "files": written_files,
        "packet_write_count": len(packet_writes),
        "packet_writes": packet_writes,
        "test_manifest_written": bool(write_test_manifest),
    }


def render_release_candidate_pack_write_summary(result: dict[str, Any]) -> str:
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


def build_release_test_manifest(pack: dict[str, Any], candidate_artifacts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    artifacts_by_key = {
        str(item.get("candidate_key")): dict(item)
        for item in (candidate_artifacts or [])
        if item.get("candidate_key") not in (None, "")
    }
    entries: list[dict[str, Any]] = []
    for candidate in pack.get("candidates") or []:
        if candidate.get("status") != "ready" or not isinstance(candidate.get("release_spec"), dict):
            continue
        candidate_key = str(candidate.get("candidate_key") or "")
        artifact = artifacts_by_key.get(candidate_key, {})
        release_spec_path = str(artifact.get("release_spec_path") or f"{candidate_key}.release.json")
        packet_dir = artifact.get("packet_dir")
        packet = build_content_release_packet(candidate["release_spec"])
        entries.append(
            {
                "candidate_key": candidate_key,
                "lane": str(candidate.get("lane") or ""),
                "packet_status": str(candidate.get("packet_status") or ""),
                "release_spec_path": release_spec_path,
                "packet_dir": packet_dir,
                "packet_files": list(artifact.get("packet_files") or []),
                "dry_run_commands": _candidate_test_commands(
                    candidate=candidate,
                    release_spec_path=release_spec_path,
                    packet_dir=str(packet_dir) if packet_dir else None,
                    player_guid=int(pack.get("player_guid") or 0),
                ),
                "live_proof_checklist": list(packet.get("live_proof_checklist") or []),
                "status_after_repo_tests": "PARTIAL_UNTIL_LIVE_PROOF",
            }
        )
    return {
        "schema_version": "wm.release_candidate_test_manifest.v1",
        "status": "TEST_READY" if entries else "NO_READY_CANDIDATES",
        "player_guid": int(pack.get("player_guid") or 0),
        "target": dict(pack.get("target") or {}),
        "candidate_count": len(entries),
        "preflight_commands": [
            "git status --short --branch",
            "$env:PYTHONPATH='src'",
            "$env:WM_WORLD_DB_HOST='127.0.0.1'",
            "$env:WM_WORLD_DB_PORT='33307'",
            "$env:WM_CHAR_DB_HOST='127.0.0.1'",
            "$env:WM_CHAR_DB_PORT='33307'",
            "python -m pytest -q tests/test_content_release.py tests/test_release_candidate_pack.py",
        ],
        "candidates": entries,
        "live_test_rules": [
            "Provide the scoped player GUID explicitly (e.g. via the context pack).",
            "Do not apply specs with fresh visible IDs until the custom ID ledger/reserved slot state is checked.",
            "After repo or DB proof, leave status PARTIAL until the player sees the quest, item, ability, scene, or effect in-game.",
        ],
    }


def _candidate_test_commands(
    *,
    candidate: dict[str, Any],
    release_spec_path: str,
    packet_dir: str | None,
    player_guid: int,
) -> list[str]:
    commands = [
        f"python -m wm.content.release {release_spec_path} --summary",
        f"python -m wm.content.release {release_spec_path} --packet --summary",
    ]
    if packet_dir is None:
        commands.append(f"python -m wm.content.release {release_spec_path} --write-packet-dir <packet-dir> --summary")
    lane = str(candidate.get("lane") or "")
    if lane == "story_arc":
        if packet_dir:
            commands.append(
                f"python -m wm.character.journey apply --plan-json {packet_dir}\\compiled-journey-plan.json --mode dry-run --summary"
            )
        else:
            commands.append(f"python -m wm.content.release {release_spec_path} --emit-journey-plan")
            commands.append(f"python -m wm.content.release {release_spec_path} --emit-branch-lock-plan")
    elif lane == "native_scene":
        if packet_dir:
            commands.append(
                f"python -m wm.control.scene_play --scene {packet_dir}\\compiled-control-scene.json --player-guid {player_guid} --mode dry-run --summary"
            )
        else:
            commands.append(f"python -m wm.content.release {release_spec_path} --emit-control-scene")
    elif lane == "shell_ability":
        commands.append("python -m wm.content.release --ability-roster --summary")
    elif lane == "managed_item_power":
        commands.append("python -m wm.content.release <fresh-quest-or-item-playcycle-spec.json> --plan --summary")
    return commands


def _ready_candidate(*, lane: str, candidate_key: str, score: int, rationale: str, spec: dict[str, Any]) -> ReleaseCandidate:
    validation = validate_content_release_spec(spec).to_dict()
    if not validation.get("ok"):
        return ReleaseCandidate(
            candidate_key=candidate_key,
            lane=lane,
            status="broken",
            score=0,
            rationale=rationale,
            release_spec=spec,
            validation=validation,
            blockers=["generated_spec_failed_validation"],
        )
    packet = build_content_release_packet(spec)
    return ReleaseCandidate(
        candidate_key=candidate_key,
        lane=lane,
        status="ready",
        score=int(score),
        rationale=rationale,
        release_spec=spec,
        validation=validation,
        packet_status=str(packet.get("status") or ""),
        next_commands=[
            "python -m wm.content.release <candidate-spec.json> --packet --summary",
            "python -m wm.content.release <candidate-spec.json> --write-packet-dir <packet-dir> --summary",
        ],
    )


def _story_arc_candidate(
    *,
    player_guid: int,
    target_slug: str,
    target_name: str,
    target_entry: int,
    journey_eligibility: dict[str, Any],
) -> ReleaseCandidate:
    spec = _story_arc_spec(
        player_guid=player_guid,
        target_slug=target_slug,
        target_name=target_name,
        target_entry=target_entry,
    )
    if not bool(journey_eligibility.get("ready_for_arc_factory")):
        return ReleaseCandidate(
            candidate_key=f"{target_slug}_choice_arc",
            lane="story_arc",
            status="blocked_by_journey",
            score=30,
            rationale="Story arcs require a ready character journey spine before release.",
            release_spec=spec,
            validation=validate_content_release_spec(spec).to_dict(),
            blockers=list(journey_eligibility.get("blocked_reasons") or ["journey_not_ready"]),
            next_commands=["python -m wm.character.journey inspect --player-guid <guid> --summary"],
        )
    return _ready_candidate(
        lane="story_arc",
        candidate_key=f"{target_slug}_choice_arc",
        score=88,
        rationale="Journey spine is ready, so a linked choice arc can be drafted from this target context.",
        spec=spec,
    )


def _managed_item_power_candidate(
    *,
    player_guid: int,
    target_slug: str,
    target_name: str,
    reserved_item_entry: int | None,
    base_item_entry: int | None,
    wearer_aura_spell_id: int,
    target_aura_spell_id: int,
) -> ReleaseCandidate:
    item_entry = _positive_int(reserved_item_entry)
    base_entry = _positive_int(base_item_entry)
    wearer_aura_id = _positive_int(wearer_aura_spell_id) or 132
    target_aura_id = _positive_int(target_aura_spell_id) or 770
    if item_entry is None or base_entry is None:
        blockers: list[str] = []
        if item_entry is None:
            blockers.append("fresh_item_entry_required")
        if base_entry is None:
            blockers.append("base_item_entry_required")
        return ReleaseCandidate(
            lane="managed_item_power",
            candidate_key=f"{target_slug}_managed_item_power",
            status="blocked_needs_id_reservation",
            score=58,
            rationale="Managed item powers are a roadmap priority, but the pack must not invent visible item IDs.",
            blockers=blockers,
            next_commands=[
                "Reserve a fresh managed item slot and choose a known-good base item row.",
                "python -m wm.candidates.release_pack --context-pack-json <context-pack.json> --reserved-item-entry <fresh-item-entry> --base-item-entry <base-item-entry> --summary",
            ],
        )
    return _ready_candidate(
        lane="managed_item_power",
        candidate_key=f"{target_slug}_managed_item_power",
        score=86,
        rationale="A fresh item entry and base row were supplied, so a visible managed item-power release spec can be drafted safely.",
        spec=_managed_item_power_spec(
            player_guid=player_guid,
            target_slug=target_slug,
            target_name=target_name,
            item_entry=item_entry,
            base_item_entry=base_entry,
            wearer_aura_spell_id=wearer_aura_id,
            target_aura_spell_id=target_aura_id,
        ),
    )


def _repeatable_bounty_spec(*, player_guid: int, target_entry: int, target_name: str, history: dict[str, Any]) -> dict[str, Any]:
    kill_count = max(3, min(8, (_positive_int(history.get("kill_count")) or 3) + 2))
    return {
        "schema_version": REPEATABLE_BOUNTY_SCHEMA,
        "quest_kind": "repeatable_bounty",
        "player_guid": int(player_guid),
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
            "target_entry": int(target_entry),
            "target_name": target_name,
            "kill_count": kill_count,
        },
        "reward": {
            "kind": "money_item_spell_reputation_or_none",
            "fresh_visible_reward_ids_required": True,
        },
        "notes": ["Generated release-candidate bounty; inspect target level/NPC before apply."],
    }


def _story_arc_spec(*, player_guid: int, target_slug: str, target_name: str, target_entry: int) -> dict[str, Any]:
    arc_key = f"{target_slug}_choice_arc_v1"
    return {
        "schema_version": STORY_ARC_SCHEMA,
        "quest_kind": "story_arc",
        "player_guid": int(player_guid),
        "arc_key": arc_key,
        "nodes": [
            {"node_key": "start", "quest_schema": "wm.quest.release.one_shot.v1", "fresh_reserved_required": True},
            {"node_key": "power_choice", "quest_schema": "wm.quest.release.one_shot.v1", "fresh_reserved_required": True},
            {"node_key": "scene_choice", "quest_schema": "wm.quest.release.one_shot.v1", "fresh_reserved_required": True},
        ],
        "edges": [
            {"from": "start", "to": "power_choice", "kind": "branch_unlocks"},
            {"from": "start", "to": "scene_choice", "kind": "branch_unlocks"},
        ],
        "fork_groups": [
            {
                "group_key": "choose_first_reward",
                "choice_node_keys": ["power_choice", "scene_choice"],
                "lock_policy": "first_turn_in_locks_others",
            }
        ],
        "journey_updates": {
            "stage_key": f"{target_slug}_choice_offered",
            "branch_key": f"{target_slug}_pending_choice",
            "conversation_steering": [
                {
                    "steering_key": f"{target_slug}_release_candidate",
                    "body": f"Explore a personal arc around {target_name} ({target_entry}) with a power or scene branch.",
                    "priority": 40,
                    "source": "release_candidate_pack",
                }
            ],
        },
        "runtime_sync": {"mode": "auto"},
        "notes": ["Generated release-candidate story arc; allocate fresh quest IDs before publish."],
    }


def _targeted_projectile_ability_spec(*, player_guid: int, target_slug: str, target_name: str) -> dict[str, Any]:
    return {
        "schema_version": ABILITY_SHELL_POWER_SCHEMA,
        "content_kind": "ability",
        "player_guid": int(player_guid),
        "ability_key": f"{target_slug}_projectile_power_v1",
        "ability_type": "targeted_effect_with_projectile",
        "shell_family": "unit_target_projectile",
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
            "seed_template": "wm_unit_target_projectile",
            "seed_only": True,
        },
        "notes": [f"Generated release-candidate projectile inspired by {target_name} context."],
    }


def _area_pressure_scene_spec(*, player_guid: int, target_slug: str, target_name: str) -> dict[str, Any]:
    return {
        "schema_version": SCENE_NATIVE_SEQUENCE_SCHEMA,
        "content_kind": "scene",
        "player_guid": int(player_guid),
        "scene_key": f"{target_slug}_area_pressure_scene_v1",
        "scene_type": "area_pressure",
        "slot_policy": "no_visible_id_required",
        "trigger": {
            "kind": "area_pressure",
            "source_event_required": True,
            "max_event_age_seconds": 600,
            "notes": "Use a fresh native/event-spine trigger row.",
        },
        "runtime": {
            "native_actions_required": True,
            "audit_required": True,
            "player_scope_required": True,
            "control_scene_required": True,
        },
        "steps": [
            {
                "step_key": "restore",
                "native_action_kind": "player_restore_health_power",
                "payload": {"health_percent": 20, "power_percent": 15, "power_type": "active"},
                "risk_level": "low",
                "idempotency_suffix": "restore",
                "expected_effect": f"The scoped player gets a small survival pulse during {target_name} pressure.",
                "requires_live_proof": True,
            },
            {
                "step_key": "announce",
                "native_action_kind": "world_announce_to_player",
                "payload": {"message": f"WM pressure spike near {target_name}: hold the line."},
                "risk_level": "low",
                "idempotency_suffix": "announce",
                "expected_effect": "The scoped player sees a local WM scene message.",
                "requires_live_proof": True,
            },
        ],
        "cleanup": {"required": False},
        "notes": ["Generated release-candidate scene using implemented native verbs only."],
    }


def _managed_item_power_spec(
    *,
    player_guid: int,
    target_slug: str,
    target_name: str,
    item_entry: int,
    base_item_entry: int,
    wearer_aura_spell_id: int,
    target_aura_spell_id: int,
) -> dict[str, Any]:
    return {
        "schema_version": ITEM_MANAGED_POWER_SCHEMA,
        "content_kind": "item",
        "player_guid": int(player_guid),
        "item_key": f"{target_slug}_managed_power_v1",
        "item_entry": int(item_entry),
        "slot_policy": "fresh_item_slot_required",
        "base_item_entry": int(base_item_entry),
        "visibility": {
            "player_visible_state_required": True,
            "tooltip_required": True,
            "wearer_aura_spell_id": int(wearer_aura_spell_id),
            "target_aura_spell_id": int(target_aura_spell_id),
            "client_cache_risk": "fresh_item_slot",
        },
        "runtime": {
            "native_behavior_required": True,
            "python_decision_required": True,
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
                "effect_key": "wearer_state",
                "kind": "wearer_aura",
                "trigger": "equipped",
                "target": "self",
                "spell_id": int(wearer_aura_spell_id),
            },
            {
                "effect_key": "target_mark_proc",
                "kind": "target_mark_proc",
                "trigger": "weapon_or_wand_hit",
                "target": "enemy",
                "visible_state": f"target aura {int(target_aura_spell_id)} from the item wearer",
                "native_hook": True,
                "chance_pct": 10,
                "duration_ms": 10000,
                "spell_id": int(target_aura_spell_id),
            },
        ],
        "notes": [
            f"Generated release-candidate managed item power inspired by {target_name} context.",
            "The supplied item entry must already be reserved as a fresh WM item slot before publish.",
        ],
    }


def _generation_input(context_pack: dict[str, Any]) -> dict[str, Any]:
    if isinstance(context_pack.get("generation_input"), dict):
        return dict(context_pack["generation_input"])
    return dict(context_pack)


def _player_guid(context_pack: dict[str, Any], generation: dict[str, Any]) -> int:
    player = generation.get("player") if isinstance(generation.get("player"), dict) else {}
    guid = _positive_int(player.get("guid") or generation.get("player_guid") or context_pack.get("player_guid"))
    if guid is None:
        raise ValueError("scoped player_guid is required")
    return guid


def _target(context_pack: dict[str, Any], generation: dict[str, Any]) -> dict[str, Any]:
    target = generation.get("target") if isinstance(generation.get("target"), dict) else {}
    profile = context_pack.get("target_profile") if isinstance(context_pack.get("target_profile"), dict) else {}
    return {**profile, **target}


def _journey_eligibility(generation: dict[str, Any]) -> dict[str, Any]:
    journey = generation.get("journey") if isinstance(generation.get("journey"), dict) else {}
    eligibility = journey.get("eligibility") if isinstance(journey.get("eligibility"), dict) else {}
    return dict(eligibility)


def _steering_text(generation: dict[str, Any]) -> str:
    journey = generation.get("journey") if isinstance(generation.get("journey"), dict) else {}
    steering = journey.get("steering") if isinstance(journey.get("steering"), list) else []
    return " ".join(str(item.get("body") or "") for item in steering if isinstance(item, dict)).lower()


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return text or "target"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.candidates.release_pack")
    parser.add_argument("--context-pack-json", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--write-candidates-dir", type=Path)
    parser.add_argument("--write-packets", action="store_true")
    parser.add_argument("--write-test-manifest", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reserved-item-entry", type=int)
    parser.add_argument("--base-item-entry", type=int)
    parser.add_argument("--wearer-aura-spell-id", type=int, default=132)
    parser.add_argument("--target-aura-spell-id", type=int, default=770)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    raw = json.loads(args.context_pack_json.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise SystemExit("Context pack JSON must be an object.")
    if args.write_packets and args.write_candidates_dir is None:
        print("--write-packets requires --write-candidates-dir.")
        return 2
    if args.write_test_manifest and args.write_candidates_dir is None:
        print("--write-test-manifest requires --write-candidates-dir.")
        return 2
    if args.write_candidates_dir is not None:
        try:
            result = write_release_candidate_pack(
                raw,
                args.write_candidates_dir,
                limit=int(args.limit),
                allow_overwrite=bool(args.force),
                reserved_item_entry=args.reserved_item_entry,
                base_item_entry=args.base_item_entry,
                wearer_aura_spell_id=int(args.wearer_aura_spell_id),
                target_aura_spell_id=int(args.target_aura_spell_id),
                write_packets=bool(args.write_packets),
                write_test_manifest=bool(args.write_test_manifest),
            )
        except (ContentReleaseSpecError, ValueError) as exc:
            print(str(exc))
            return 2
        if args.summary:
            print(render_release_candidate_pack_write_summary(result))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    pack = build_release_candidate_pack(
        raw,
        limit=int(args.limit),
        reserved_item_entry=args.reserved_item_entry,
        base_item_entry=args.base_item_entry,
        wearer_aura_spell_id=int(args.wearer_aura_spell_id),
        target_aura_spell_id=int(args.target_aura_spell_id),
    )
    if args.summary:
        print(render_release_candidate_pack_summary(pack))
    else:
        print(json.dumps(pack, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
