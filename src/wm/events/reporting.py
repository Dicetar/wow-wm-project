from __future__ import annotations

from typing import Any


def build_execution_summary_lines(executions: list[object]) -> list[str]:
    lines: list[str] = []
    for index, execution in enumerate(executions, start=1):
        execution_dict = _to_dict(execution)
        if execution_dict is None:
            continue
        plan = execution_dict.get("plan")
        if not isinstance(plan, dict):
            continue
        rule_type = str(plan.get("rule_type") or "")
        player_guid = plan.get("player_guid")
        subject = plan.get("subject") if isinstance(plan.get("subject"), dict) else {}
        actions = plan.get("actions") if isinstance(plan.get("actions"), list) else []
        action_labels = [render_action_label(action) for action in actions if isinstance(action, dict)]
        lines.append(
            f"plan[{index}] rule={rule_type} player={player_guid} "
            f"subject={subject.get('subject_type')}:{subject.get('subject_entry')} "
            f"actions={', '.join(action_labels) if action_labels else '(none)'}"
        )
        lines.extend(_render_step_summary_lines(execution_dict))
    return lines


def build_suppressed_opportunity_lines(opportunities: list[object]) -> list[str]:
    lines: list[str] = []
    for index, opportunity in enumerate(opportunities, start=1):
        payload = _to_dict(opportunity)
        if payload is None:
            continue
        subject = payload.get("subject") if isinstance(payload.get("subject"), dict) else {}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        lines.append(
            f"suppressed[{index}] rule={payload.get('rule_type')} player={payload.get('player_guid')} "
            f"subject={subject.get('subject_type')}:{subject.get('subject_entry')} "
            f"reason={metadata.get('suppression_reason')}"
        )
    return lines


def render_action_label(action: dict[str, Any]) -> str:
    kind = str(action.get("kind") or "")
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    if kind == "quest_publish":
        return f"quest_publish:{payload.get('quest_id')}"
    if kind == "quest_grant":
        return f"quest_grant:{payload.get('quest_id')}"
    if kind == "item_publish":
        return f"item_publish:{payload.get('item_entry')}"
    if kind == "spell_publish":
        return f"spell_publish:{payload.get('spell_entry')}"
    if kind == "announcement":
        text = str(payload.get("text") or "").strip()
        short = text if len(text) <= 60 else text[:57] + "..."
        return f"announcement:{short}"
    return kind


def _render_step_summary_lines(execution: dict[str, object]) -> list[str]:
    lines: list[str] = []
    steps = execution.get("steps")
    if not isinstance(steps, list):
        return lines
    for step in steps:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "")
        status = str(step.get("status") or "")
        details = step.get("details") if isinstance(step.get("details"), dict) else {}
        if kind == "quest_publish":
            draft = details.get("draft") if isinstance(details.get("draft"), dict) else {}
            preflight = details.get("preflight") if isinstance(details.get("preflight"), dict) else {}
            dry_run_notes = details.get("dry_run_notes") if isinstance(details.get("dry_run_notes"), list) else []
            lines.append(
                f"  step quest_publish status={status} quest_id={draft.get('quest_id')} title={draft.get('title')}"
            )
            if preflight:
                lines.append(
                    f"  step quest_publish preflight_ok={preflight.get('ok')} "
                    f"dry_run_ready={details.get('dry_run_ready')}"
                )
            for note in dry_run_notes:
                lines.append(f"  note {note}")
        elif kind == "quest_grant":
            runtime_result = details.get("runtime_result") if isinstance(details.get("runtime_result"), dict) else {}
            lines.append(
                f"  step quest_grant status={status} quest_id={details.get('quest_id')} "
                f"player={details.get('player_name') or details.get('player_guid')}"
            )
            lines.append(
                f"  step quest_grant dry_run_ready={details.get('dry_run_ready')} "
                f"command={details.get('command_preview')}"
            )
            if runtime_result:
                lines.append(
                    f"  step quest_grant runtime_ok={runtime_result.get('ok')} "
                    f"fault={runtime_result.get('fault_string') or runtime_result.get('fault_code') or ''}"
                )
        elif kind in {"item_publish", "spell_publish"}:
            lines.append(f"  step {kind} status={status}")
        elif kind == "announcement":
            lines.append(f"  step announcement status={status}")
        elif kind == "noop":
            lines.append(f"  step noop status={status}")
    return lines


def _to_dict(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, dict):
            return payload
    return None
