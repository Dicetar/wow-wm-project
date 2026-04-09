from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.content import DeterministicContentFactory
from wm.events.executor import ReactionExecutor
from wm.events.planner import DeterministicReactionPlanner
from wm.events.reporting import build_execution_summary_lines
from wm.events.reporting import build_suppressed_opportunity_lines
from wm.events.rules import DeterministicRuleEngine
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview WM reaction plans without mutating WM state.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--questgiver-entry", type=int)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    _apply_settings_overrides(args=args, settings=settings)
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    engine = DeterministicRuleEngine(client=client, settings=settings, store=store)
    planner = DeterministicReactionPlanner(
        content_factory=DeterministicContentFactory(client=client, settings=settings),
    )
    executor = ReactionExecutor(client=client, settings=settings, store=store)
    payload = build_plan_payload(
        store=store,
        engine=engine,
        planner=planner,
        executor=executor,
        player_guid=args.player_guid,
        limit=args.limit,
        questgiver_entry=settings.event_default_questgiver_entry,
    )
    _emit_output(payload=payload, summary=args.summary, output_json=args.output_json)
    return 0


def build_plan_payload(
    *,
    store: EventStore,
    engine: DeterministicRuleEngine,
    planner: DeterministicReactionPlanner,
    executor: ReactionExecutor,
    player_guid: int | None,
    limit: int,
    questgiver_entry: int | None,
) -> dict[str, object]:
    events = store.list_recent_events(
        event_class="observed",
        player_guid=player_guid,
        limit=limit,
        newest_first=False,
    )
    evaluations = [engine.evaluate(event, preview=True) for event in events]

    derived_events = []
    opportunities = []
    suppressed_opportunities = []
    for evaluation in evaluations:
        derived_events.extend(evaluation.derived_events)
        opportunities.extend(evaluation.opportunities)
        suppressed_opportunities.extend(evaluation.suppressed_opportunities)

    plans = [planner.plan(opportunity) for opportunity in opportunities]
    previews = [executor.preview(plan=plan) for plan in plans]
    return {
        "mode": "preview",
        "player_guid_filter": player_guid,
        "questgiver_entry": questgiver_entry,
        "event_count": len(events),
        "derived_event_count": len(derived_events),
        "opportunity_count": len(opportunities),
        "suppressed_opportunity_count": len(suppressed_opportunities),
        "plan_count": len(plans),
        "preview_count": len(previews),
        "events": [event.to_dict() for event in events],
        "evaluations": [evaluation.to_dict() for evaluation in evaluations],
        "previews": [result.to_dict() for result in previews],
    }


def _emit_output(*, payload: dict[str, object], summary: bool, output_json: Path | None) -> None:
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(raw, encoding="utf-8")
    if summary:
        print(
            f"mode={payload['mode']} player_guid={payload['player_guid_filter']} "
            f"questgiver={payload['questgiver_entry']} events={payload['event_count']} "
            f"derived={payload['derived_event_count']} opportunities={payload['opportunity_count']} "
            f"suppressed={payload['suppressed_opportunity_count']} plans={payload['plan_count']} "
            f"previews={payload['preview_count']}"
        )
        evaluations = payload.get("evaluations")
        if isinstance(evaluations, list):
            suppressed = []
            for evaluation in evaluations:
                if not isinstance(evaluation, dict):
                    continue
                suppressed_rows = evaluation.get("suppressed_opportunities")
                if isinstance(suppressed_rows, list):
                    suppressed.extend(suppressed_rows)
            for line in build_suppressed_opportunity_lines(suppressed):
                print(line)
        previews = payload.get("previews")
        if isinstance(previews, list):
            for line in build_execution_summary_lines(previews):
                print(line)
    else:
        print(raw)


def _apply_settings_overrides(*, args: argparse.Namespace, settings: Settings) -> None:
    if args.questgiver_entry is not None:
        settings.event_default_questgiver_entry = int(args.questgiver_entry)


if __name__ == "__main__":
    raise SystemExit(main())
