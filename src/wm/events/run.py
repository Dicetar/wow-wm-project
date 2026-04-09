from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.adapters import ADAPTER_CHOICES
from wm.events.adapters import build_event_adapter
from wm.events.content import DeterministicContentFactory
from wm.events.executor import ReactionExecutor
from wm.events.planner import DeterministicReactionPlanner
from wm.events.projector import JournalProjector
from wm.events.reporting import build_execution_summary_lines
from wm.events.rules import DeterministicRuleEngine
from wm.events.store import EventStore
from wm.reactive.state import ReactiveQuestRuntimeSynchronizer
from wm.reactive.store import ReactiveQuestStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the end-to-end WM event spine.")
    parser.add_argument("--adapter", choices=ADAPTER_CHOICES, default="db")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--batch-size", type=int)
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
    payload = execute_event_spine(
        settings=settings,
        adapter_name=args.adapter,
        mode=args.mode,
        player_guid=args.player_guid,
        batch_size=args.batch_size,
    )
    payload["confirm_live_apply"] = args.confirm_live_apply
    _emit_output(payload=payload, summary=args.summary, output_json=args.output_json)
    return 0


def execute_event_spine(
    *,
    settings: Settings,
    adapter_name: str,
    mode: str,
    player_guid: int | None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    reactive_store = ReactiveQuestStore(client=client, settings=settings)
    resolved_batch_size = _resolve_batch_size(
        adapter_name=adapter_name,
        requested_batch_size=batch_size,
        settings=settings,
    )

    adapter = build_event_adapter(
        adapter_name=adapter_name,
        client=client,
        settings=settings,
        store=store,
        reactive_store=reactive_store,
        batch_size=resolved_batch_size,
        player_guid_filter=player_guid,
    )
    projector = JournalProjector(store=store)
    runtime_synchronizer = ReactiveQuestRuntimeSynchronizer(store=store, reactive_store=reactive_store)
    engine = DeterministicRuleEngine(
        client=client,
        settings=settings,
        store=store,
        reactive_store=reactive_store,
    )
    planner = DeterministicReactionPlanner(
        content_factory=DeterministicContentFactory(client=client, settings=settings),
    )
    executor = ReactionExecutor(
        client=client,
        settings=settings,
        store=store,
        reactive_store=reactive_store,
    )

    polled_events = adapter.poll()
    record_result = store.record(polled_events)
    runtime_sync_result = runtime_synchronizer.poll(player_guid=player_guid, preview=False)
    runtime_record_result = store.record(runtime_sync_result.observed_transitions)
    if adapter.last_cursor_value is not None:
        store.set_cursor(adapter_name=adapter.name, cursor_key=adapter.cursor_key, cursor_value=adapter.last_cursor_value)

    projection_events = store.list_unprojected_observed_events(limit=resolved_batch_size)
    projection_results = [projector.apply(event) for event in projection_events]

    evaluation_events = store.list_unevaluated_observed_events(limit=resolved_batch_size)
    evaluations = [engine._evaluate(event, preview=False, mark_evaluated=False) for event in evaluation_events]

    derived_events = []
    opportunities = []
    for evaluation in evaluations:
        derived_events.extend(evaluation.derived_events)
        opportunities.extend(evaluation.opportunities)
    if derived_events:
        store.record(derived_events)
    for event in evaluation_events:
        if event.event_id is not None:
            store.mark_evaluated(event_id=event.event_id)

    plans = [planner.plan(opportunity) for opportunity in opportunities]
    _validate_apply_plan_scope(mode=mode, plans=plans)
    execution_results = [executor.execute(plan=plan, mode=mode) for plan in plans]

    return {
        "adapter": adapter.name,
        "mode": mode,
        "player_guid_filter": player_guid,
        "questgiver_entry": settings.event_default_questgiver_entry,
        "polled_count": len(polled_events),
        "recorded_count": len(record_result.recorded),
        "runtime_state_event_count": len(runtime_sync_result.observed_transitions),
        "runtime_state_recorded_count": len(runtime_record_result.recorded),
        "projected_count": sum(1 for result in projection_results if result.status == "projected"),
        "derived_event_count": len(derived_events),
        "opportunity_count": len(opportunities),
        "plan_count": len(plans),
        "execution_count": len(execution_results),
        "executions": [result.to_dict() for result in execution_results],
    }


def _emit_output(*, payload: dict[str, object], summary: bool, output_json: Path | None) -> None:
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(raw, encoding="utf-8")
    if summary:
        print(
            f"adapter={payload['adapter']} mode={payload['mode']} player_guid={payload['player_guid_filter']} "
            f"questgiver={payload['questgiver_entry']} polled={payload['polled_count']} "
            f"recorded={payload['recorded_count']} runtime_events={payload.get('runtime_state_event_count', 0)} "
            f"runtime_recorded={payload.get('runtime_state_recorded_count', 0)} "
            f"projected={payload['projected_count']} "
            f"derived={payload['derived_event_count']} opportunities={payload['opportunity_count']} "
            f"plans={payload['plan_count']} executions={payload['execution_count']}"
        )
        executions = payload.get("executions")
        if isinstance(executions, list):
            for line in build_execution_summary_lines(executions):
                print(line)
    else:
        print(raw)


def _apply_settings_overrides(*, args: argparse.Namespace, settings: Settings) -> None:
    if args.questgiver_entry is not None:
        settings.event_default_questgiver_entry = int(args.questgiver_entry)


def _validate_run_arguments(*, args: argparse.Namespace, settings: Settings) -> None:
    adapter_name = getattr(args, "adapter", "db")
    if adapter_name in {"combat_log", "addon_log"} and args.player_guid is None:
        label = "Combat log" if adapter_name == "combat_log" else "Addon log"
        raise SystemExit(f"{label} runs require --player-guid to resolve the source player.")
    if args.mode != "apply":
        return
    if not args.confirm_live_apply:
        raise SystemExit("Apply mode requires --confirm-live-apply.")
    if args.player_guid is None:
        raise SystemExit("Apply mode requires --player-guid to scope the run to one player.")


def _validate_apply_plan_scope(*, mode: str, plans: list[object]) -> None:
    if mode != "apply":
        return
    if len(plans) > 1:
        raise SystemExit(
            f"Apply mode produced {len(plans)} plans. Narrow the run with --player-guid / --batch-size or rerun in dry-run mode."
        )


def _resolve_batch_size(*, adapter_name: str, requested_batch_size: int | None, settings: Settings) -> int:
    if requested_batch_size is not None:
        return int(requested_batch_size)
    if adapter_name == "addon_log":
        return int(settings.addon_log_batch_size)
    if adapter_name == "combat_log":
        return int(settings.combat_log_batch_size)
    return 100


if __name__ == "__main__":
    raise SystemExit(main())
