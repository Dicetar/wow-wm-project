from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.adapters import DBPollingAdapter
from wm.events.content import DeterministicContentFactory
from wm.events.executor import ReactionExecutor
from wm.events.planner import DeterministicReactionPlanner
from wm.events.projector import JournalProjector
from wm.events.rules import DeterministicRuleEngine
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the end-to-end WM event spine.")
    parser.add_argument("--adapter", choices=["db"], default="db")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--questgiver-entry", type=int)
    parser.add_argument("--confirm-live-apply", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    _apply_settings_overrides(args=args, settings=settings)
    _validate_run_arguments(args=args, settings=settings)
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)

    adapter = DBPollingAdapter(
        client=client,
        settings=settings,
        store=store,
        batch_size=args.batch_size,
        player_guid_filter=args.player_guid,
    )
    projector = JournalProjector(store=store)
    engine = DeterministicRuleEngine(client=client, settings=settings, store=store)
    planner = DeterministicReactionPlanner(
        content_factory=DeterministicContentFactory(client=client, settings=settings),
    )
    executor = ReactionExecutor(client=client, settings=settings, store=store)

    polled_events = adapter.poll()
    record_result = store.record(polled_events)
    if adapter.last_cursor_value is not None:
        store.set_cursor(adapter_name=adapter.name, cursor_key=adapter.cursor_key, cursor_value=adapter.last_cursor_value)

    projection_events = store.list_unprojected_observed_events(limit=args.batch_size)
    projection_results = [projector.apply(event) for event in projection_events]

    evaluation_events = store.list_unevaluated_observed_events(limit=args.batch_size)
    evaluations = [engine.evaluate(event) for event in evaluation_events]

    derived_events = []
    opportunities = []
    for evaluation in evaluations:
        derived_events.extend(evaluation.derived_events)
        opportunities.extend(evaluation.opportunities)
    if derived_events:
        store.record(derived_events)

    plans = [planner.plan(opportunity) for opportunity in opportunities]
    _validate_apply_plan_scope(mode=args.mode, plans=plans)
    execution_results = [executor.execute(plan=plan, mode=args.mode) for plan in plans]

    payload = {
        "adapter": adapter.name,
        "mode": args.mode,
        "player_guid_filter": args.player_guid,
        "questgiver_entry": settings.event_default_questgiver_entry,
        "confirm_live_apply": args.confirm_live_apply,
        "polled_count": len(polled_events),
        "recorded_count": len(record_result.recorded),
        "projected_count": sum(1 for result in projection_results if result.status == "projected"),
        "derived_event_count": len(derived_events),
        "opportunity_count": len(opportunities),
        "plan_count": len(plans),
        "execution_count": len(execution_results),
        "executions": [result.to_dict() for result in execution_results],
    }
    _emit_output(payload=payload, summary=args.summary, output_json=args.output_json)
    return 0


def _emit_output(*, payload: dict[str, object], summary: bool, output_json: Path | None) -> None:
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(raw, encoding="utf-8")
    if summary:
        print(
            f"adapter={payload['adapter']} mode={payload['mode']} player_guid={payload['player_guid_filter']} "
            f"questgiver={payload['questgiver_entry']} polled={payload['polled_count']} "
            f"recorded={payload['recorded_count']} projected={payload['projected_count']} "
            f"derived={payload['derived_event_count']} opportunities={payload['opportunity_count']} "
            f"plans={payload['plan_count']} executions={payload['execution_count']}"
        )
        for line in _build_execution_summary_lines(payload):
            print(line)
    else:
        print(raw)


def _apply_settings_overrides(*, args: argparse.Namespace, settings: Settings) -> None:
    if args.questgiver_entry is not None:
        settings.event_default_questgiver_entry = int(args.questgiver_entry)


def _validate_run_arguments(*, args: argparse.Namespace, settings: Settings) -> None:
    if args.mode != "apply":
        return
    if not args.confirm_live_apply:
        raise SystemExit("Apply mode requires --confirm-live-apply.")
    if args.player_guid is None:
        raise SystemExit("Apply mode requires --player-guid to scope the run to one player.")
    if settings.event_default_questgiver_entry is None:
        raise SystemExit("Apply mode requires --questgiver-entry or WM_EVENT_DEFAULT_QUESTGIVER_ENTRY.")


def _validate_apply_plan_scope(*, mode: str, plans: list[object]) -> None:
    if mode != "apply":
        return
    if len(plans) > 1:
        raise SystemExit(
            f"Apply mode produced {len(plans)} plans. Narrow the run with --player-guid / --batch-size or rerun in dry-run mode."
        )


def _build_execution_summary_lines(payload: dict[str, object]) -> list[str]:
    lines: list[str] = []
    executions = payload.get("executions")
    if not isinstance(executions, list):
        return lines
    for index, execution in enumerate(executions, start=1):
        if not isinstance(execution, dict):
            continue
        plan = execution.get("plan")
        if not isinstance(plan, dict):
            continue
        rule_type = str(plan.get("rule_type") or "")
        player_guid = plan.get("player_guid")
        subject = plan.get("subject") if isinstance(plan.get("subject"), dict) else {}
        actions = plan.get("actions") if isinstance(plan.get("actions"), list) else []
        action_labels = [_render_action_label(action) for action in actions if isinstance(action, dict)]
        lines.append(
            f"plan[{index}] rule={rule_type} player={player_guid} "
            f"subject={subject.get('subject_type')}:{subject.get('subject_entry')} "
            f"actions={', '.join(action_labels) if action_labels else '(none)'}"
        )
        step_lines = _render_step_summary_lines(execution)
        lines.extend(step_lines)
    return lines


def _render_action_label(action: dict[str, object]) -> str:
    kind = str(action.get("kind") or "")
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    if kind == "quest_publish":
        return f"quest_publish:{payload.get('quest_id')}"
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
        elif kind == "announcement":
            lines.append(f"  step announcement status={status}")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
