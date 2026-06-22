from __future__ import annotations

from typing import Any

from wm.autoplay._publish_payloads import _entry_from_payload
from wm.autoplay._publish_payloads import _item_publish_payload_from_release
from wm.autoplay._publish_payloads import _quest_publish_payload_from_release
from wm.autoplay._publish_payloads import _spell_publish_payload_from_release
from wm.config import Settings


def _runtime_proposals_from_draft(record: dict[str, Any]) -> list[Any]:
    lane = str(record.get("lane") or "")
    payload = record.get("parsed_json") if isinstance(record.get("parsed_json"), dict) else {}
    if lane == "action":
        return [_runtime_action_proposal(record=record, payload=payload)]
    if lane == "scene":
        return _runtime_scene_proposals(record=record, payload=payload)
    raise ValueError(f"Unsupported autoplay runtime lane: {lane}")


def _runtime_work_from_draft(*, record: dict[str, Any], settings: Settings) -> dict[str, Any]:
    lane = str(record.get("lane") or "")
    if lane in {"scene", "action"}:
        return {"kind": "control", "proposals": _runtime_proposals_from_draft(record)}
    if lane in {"quest", "item", "spell"}:
        return {"kind": "plan", "plan": _runtime_publish_plan_from_draft(record=record, settings=settings)}
    if lane == "ability":
        return {"kind": "maintenance", "reason": "shell_ability_dbc_publish_requires_safe_window_and_shell_template_driver"}
    raise ValueError(f"Unsupported autoplay runtime lane: {lane}")


def _execute_runtime_work(*, runtime: dict[str, Any], coordinator: Any, mode: str) -> list[Any]:
    if runtime.get("kind") == "control":
        return [
            coordinator.execute(proposal=proposal, mode=mode, confirm_live_apply=(mode == "apply"))
            for proposal in runtime.get("proposals", [])
        ]
    if runtime.get("kind") == "plan":
        plan = runtime["plan"]
        executor = getattr(coordinator, "executor")
        return [executor.preview(plan=plan)] if mode == "dry-run" else [executor.execute(plan=plan, mode="apply")]
    raise ValueError(f"Unsupported runtime work kind: {runtime.get('kind')}")


def _runtime_results_ok(results: list[Any], *, expected: str) -> bool:
    if not results:
        return False
    allowed = {"dry-run": {"dry-run", "preview"}, "applied": {"applied"}}[expected]
    return all(str(getattr(result, "status", "")) in allowed for result in results)


def _runtime_idempotency_keys(runtime: dict[str, Any]) -> list[str]:
    if runtime.get("kind") == "control":
        return [
            str(proposal.idempotency_key)
            for proposal in runtime.get("proposals", [])
            if getattr(proposal, "idempotency_key", None)
        ]
    if runtime.get("kind") == "plan":
        return [str(getattr(runtime["plan"], "plan_key", ""))]
    return []


def _runtime_rollback_available(lane: str) -> bool:
    return lane in {"quest", "item", "spell", "scene", "action"}


def _runtime_publish_plan_from_draft(*, record: dict[str, Any], settings: Settings) -> Any:
    from wm.db.mysql_cli import MysqlCliClient
    from wm.events.models import PlannedAction, ReactionPlan, SubjectRef
    from wm.reserved.db_allocator import ReservedSlotDbAllocator

    payload = dict(record.get("parsed_json") if isinstance(record.get("parsed_json"), dict) else {})
    lane = str(record.get("lane") or "")
    player_guid = int(record.get("player_guid") or payload.get("player_guid") or 0)
    if player_guid <= 0:
        raise ValueError(f"{lane} draft is missing player_guid")
    opportunity = record.get("opportunity") if isinstance(record.get("opportunity"), dict) else {}
    source_event = opportunity.get("source_event") if isinstance(opportunity.get("source_event"), dict) else {}
    subject = SubjectRef(
        subject_type=str(source_event.get("subject_type") or lane),
        subject_entry=int(source_event.get("subject_entry") or _entry_from_payload(payload, lane) or 0),
    )
    allocator = ReservedSlotDbAllocator(client=MysqlCliClient(), settings=settings)
    actions: list[Any] = []
    if lane == "quest":
        quest_payload = _quest_publish_payload_from_release(payload, record=record, allocator=allocator)
        actions.append(PlannedAction(kind="quest_publish", payload=quest_payload, description="Autoplay publishes an LLM-authored repeatable bounty."))
        if str(quest_payload.get("grant_mode") or "") == "direct_grant":
            actions.append(PlannedAction(
                kind="quest_grant",
                payload={
                    "quest_id": int(quest_payload["quest_id"]),
                    "player_guid": player_guid,
                    "quest": {"id": int(quest_payload["quest_id"]), "title": quest_payload.get("title")},
                    "player": {"guid": player_guid},
                    "subject": {
                        "type": subject.subject_type,
                        "entry": subject.subject_entry,
                        "name": (quest_payload.get("objective") or {}).get("target_name"),
                    },
                    "turn_in_npc": {
                        "entry": quest_payload.get("end_npc_entry") or quest_payload.get("questgiver_entry"),
                        "name": quest_payload.get("questgiver_name"),
                    },
                },
                description="Autoplay grants the newly published quest to the active character.",
            ))
    elif lane == "item":
        actions.append(PlannedAction(kind="item_publish", payload=_item_publish_payload_from_release(payload, record=record, allocator=allocator), description="Autoplay publishes an LLM-authored managed item."))
    elif lane == "spell":
        actions.append(PlannedAction(kind="spell_publish", payload=_spell_publish_payload_from_release(payload, record=record, allocator=allocator), description="Autoplay publishes an LLM-authored managed spell."))
    else:
        raise ValueError(f"Unsupported publish lane: {lane}")
    return ReactionPlan(
        plan_key=f"autoplay:{lane}:{record.get('draft_id')}",
        opportunity_type=f"autoplay_{lane}_publish",
        rule_type=f"autoplay_{lane}",
        player_guid=player_guid,
        subject=subject,
        actions=actions,
        metadata={
            "autoplay_draft_id": record.get("draft_id"),
            "autoplay_schema_version": record.get("schema_version"),
            "source_event_key": opportunity.get("source_event_key"),
        },
    )


def _runtime_action_proposal(*, record: dict[str, Any], payload: dict[str, Any]) -> Any:
    from wm.control.models import ControlProposal

    original_source_event = payload.get("source_event") if isinstance(payload.get("source_event"), dict) else None
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    runtime_payload = dict(payload)
    runtime_payload["source_event"] = None
    runtime_payload["idempotency_key"] = str(
        runtime_payload.get("idempotency_key")
        or f"autoplay:action:{record.get('draft_id') or record.get('created_at') or 'draft'}"
    )
    runtime_payload["author"] = {
        "kind": "manual_admin",
        "name": "wm.autoplay",
        "manual_reason": "policy-approved autoplay LLM action draft",
    }
    runtime_payload["metadata"] = {
        **metadata,
        "autoplay_draft_id": record.get("draft_id"),
        "autoplay_lane": record.get("lane"),
        "autoplay_schema_version": record.get("schema_version"),
        "autoplay_source_event": original_source_event,
        "autoplay_original_author": payload.get("author"),
    }
    return ControlProposal.model_validate(runtime_payload)


def _runtime_scene_proposals(*, record: dict[str, Any], payload: dict[str, Any]) -> list[Any]:
    from wm.content.release import compile_scene_release_to_control_scene
    from wm.control.models import ControlProposal
    from wm.control.scene_play import build_scene_proposal, ControlScene, SceneStep

    compiled = compile_scene_release_to_control_scene(payload)
    scene = ControlScene(
        scene_id=str(compiled["id"]),
        description=str(compiled.get("description") or ""),
        steps=[
            SceneStep(
                native_action_kind=str(item["native_action_kind"]),
                payload=dict(item.get("payload") or {}),
                risk_level=str(item.get("risk_level") or "low"),
                delay_seconds=float(item.get("delay_seconds") or 0),
                idempotency_suffix=str(item.get("idempotency_suffix") or index),
                expected_effect=str(item.get("expected_effect") or ""),
            )
            for index, item in enumerate(compiled.get("steps") or [])
            if isinstance(item, dict)
        ],
    )
    if not scene.steps:
        raise ValueError("scene draft compiled without steps")
    player_guid = int(payload.get("player_guid") or record.get("player_guid") or 0)
    if player_guid <= 0:
        raise ValueError("scene draft is missing player_guid")
    run_key = str(record.get("draft_id") or payload.get("scene_key") or "autoplay")
    proposals = []
    for index, step in enumerate(scene.steps):
        proposal = build_scene_proposal(
            scene=scene,
            step=step,
            index=index,
            player_guid=player_guid,
            player_name=None,
            run_key=run_key,
            manual_reason="policy-approved autoplay LLM scene draft",
        )
        proposal_payload = proposal.model_dump(mode="json")
        proposal_payload["metadata"] = {
            **proposal_payload.get("metadata", {}),
            "autoplay_draft_id": record.get("draft_id"),
            "autoplay_lane": record.get("lane"),
            "autoplay_schema_version": record.get("schema_version"),
            "autoplay_source_event": (record.get("opportunity") or {}).get("source_event")
            if isinstance(record.get("opportunity"), dict) else None,
        }
        proposals.append(ControlProposal.model_validate(proposal_payload))
    return proposals
