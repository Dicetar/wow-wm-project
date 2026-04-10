from __future__ import annotations

import argparse
import json

from wm.config import Settings
from wm.control._cli import load_registry
from wm.control.perception import build_perception_pack
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a WM perception pack for a future LLM proposal call.")
    parser.add_argument("--event-id", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    event = store.get_event(event_id=args.event_id)
    if event is None:
        raise SystemExit(f"Event not found: {args.event_id}")
    pack = build_perception_pack(event=event, registry=load_registry(settings), store=store)
    print(json.dumps(pack, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
