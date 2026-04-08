from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.rules import DeterministicRuleEngine
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate deterministic WM rules against canonical observed events.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    engine = DeterministicRuleEngine(client=client, settings=settings, store=store)

    events = store.list_unevaluated_observed_events(limit=args.limit)
    evaluations = [engine.evaluate(event) for event in events]

    derived_events = []
    opportunities = []
    for evaluation in evaluations:
        derived_events.extend(evaluation.derived_events)
        opportunities.extend(evaluation.opportunities)
    if derived_events:
        store.record(derived_events)

    payload = {
        "event_count": len(events),
        "derived_event_count": len(derived_events),
        "opportunity_count": len(opportunities),
        "evaluations": [evaluation.to_dict() for evaluation in evaluations],
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
            f"events={payload['event_count']} derived={payload['derived_event_count']} "
            f"opportunities={payload['opportunity_count']}"
        )
    else:
        print(raw)


if __name__ == "__main__":
    raise SystemExit(main())
