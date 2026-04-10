from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.control._cli import default_proposal_output_path
from wm.control._cli import load_registry
from wm.control.builder import build_manual_proposal
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a starter WM ControlProposal JSON file.")
    parser.add_argument("--event-id", type=int, required=True)
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--author-name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    event = store.get_event(event_id=args.event_id)
    if event is None:
        raise SystemExit(f"Event not found: {args.event_id}")
    registry = load_registry(settings)
    proposal = build_manual_proposal(
        event=event,
        registry=registry,
        recipe_id=args.recipe,
        action_kind=args.action,
        author_name=args.author_name,
    )
    output = args.output or default_proposal_output_path(
        settings,
        event_id=args.event_id,
        recipe_id=args.recipe,
        action_kind=args.action,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(proposal.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True)
    output.write_text(raw + "\n", encoding="utf-8")
    print(f"proposal_written={output}")
    print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
