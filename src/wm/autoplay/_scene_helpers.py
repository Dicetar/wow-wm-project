from __future__ import annotations

import json
from typing import Any


def _schema_from_proposal(proposal: Any) -> str:
    payload = getattr(proposal, "payload", {}) or {}
    if isinstance(payload, dict) and payload.get("schema_version"):
        return str(payload["schema_version"])
    kind = getattr(getattr(proposal, "kind", None), "value", "")
    return {
        "quest": "wm.quest.release.repeatable_bounty.v1",
        "item": "wm.item.release.managed_power.v1",
        "spell": "wm.spell.release.managed_spell.v1",
        "ability": "wm.ability.release.shell_power.v1",
        "scene": "wm.scene.release.native_sequence.v1",
        "action": "control.proposal.v1",
    }.get(str(kind), "unknown")


def _risk_from_proposal(proposal: Any) -> str:
    payload = getattr(proposal, "payload", {}) or {}
    if isinstance(payload, dict):
        risk = payload.get("risk")
        if isinstance(risk, dict) and risk.get("level"):
            return str(risk["level"])
        if isinstance(risk, str):
            return risk
        steps = payload.get("steps")
        if isinstance(steps, list):
            risks = [str(step.get("risk_level") or "low") for step in steps if isinstance(step, dict)]
            if "high" in risks:
                return "high"
            if "medium" in risks:
                return "medium"
    return "low"


def _source_event_at(proposal: Any) -> str | None:
    provenance = getattr(proposal, "provenance", {}) or {}
    if isinstance(provenance, dict):
        return provenance.get("source_event_at") or provenance.get("occurred_at")
    return None


def _rollback_available(gate: Any, lane: str) -> bool:
    rollbacks = getattr(gate, "_rollbacks", {})
    return lane not in {"quest", "item", "spell"} or lane in rollbacks


def _dry_run_pending(gate: Any, proposal_id: int) -> Any:
    if hasattr(gate, "dry_run"):
        return gate.dry_run(int(proposal_id))
    return gate.approve(int(proposal_id), mode="dry-run")


def _result_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    payload = {key: getattr(result, key) for key in ("ok", "detail", "error") if hasattr(result, key)}
    if payload:
        return payload
    try:
        return json.loads(json.dumps(result, default=str))
    except TypeError:
        return {"value": str(result)}


def _scene_cleanup_status(steps: list[dict[str, Any]]) -> dict[str, Any]:
    spawn_steps = [
        step for step in steps
        if isinstance(step, dict) and str(step.get("native_action_kind") or "") == "creature_spawn"
    ]
    despawn_steps = [
        step for step in steps
        if isinstance(step, dict) and str(step.get("native_action_kind") or "") == "creature_despawn"
    ]
    temporary_spawns = [
        step for step in spawn_steps
        if isinstance(step.get("payload"), dict) and step["payload"].get("duration_ms") not in (None, "")
    ]
    if not spawn_steps:
        status = "not_required"
    elif len(temporary_spawns) == len(spawn_steps):
        status = "temporary_spawn"
    elif despawn_steps:
        status = "despawn_step_planned"
    else:
        status = "missing"
    return {
        "status": status,
        "spawn_count": len(spawn_steps),
        "temporary_spawn_count": len(temporary_spawns),
        "despawn_step_count": len(despawn_steps),
    }


def _compact_store_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key in {"at", "reason", "kind", "detail"}}


def _compact_chat_world_context(context: dict[str, Any]) -> dict[str, Any]:
    events = context.get("events") if isinstance(context.get("events"), dict) else {}
    database = context.get("database") if isinstance(context.get("database"), dict) else {}
    native = context.get("native_bridge") if isinstance(context.get("native_bridge"), dict) else {}
    session_context = context.get("session_context_pack") if isinstance(context.get("session_context_pack"), dict) else {}
    return {
        "schema_version": context.get("schema_version"),
        "speaker": context.get("speaker"),
        "source_event": context.get("source_event"),
        "online_character_count": len(database.get("online_characters") or []),
        "recent_global_event_count": len(events.get("recent_global") or []),
        "recent_speaker_event_count": len(events.get("recent_for_speaker") or []),
        "recent_wm_chat_count": len(events.get("recent_wm_chat") or []),
        "recent_native_action_count": len(native.get("recent_actions") or []),
        "has_native_context_snapshot": bool(native.get("latest_context_snapshot")),
        "session_context_status": session_context.get("status"),
        "notes": context.get("notes") or [],
        "world_read": context.get("world_read"),
    }
