from __future__ import annotations

import argparse
import json

from wm.config import Settings
from wm.control._cli import load_registry
from wm.control.perception import build_perception_pack
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect WM control options for one event.")
    parser.add_argument("--event-id", type=int, required=True)
    parser.add_argument("--summary", action="store_true")
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
    pack = build_perception_pack(event=event, registry=registry, store=store)
    if args.summary:
        print(
            f"event_id={event.event_id} event_type={event.event_type} player_guid={event.player_guid} "
            f"eligible_recipes={len(pack['eligible_recipes'])}"
        )
        for recipe in pack["eligible_recipes"]:
            print(
                f"recipe={recipe['id']} live_enabled={recipe.get('live_enabled', False)} "
                f"allowed_actions={','.join(recipe.get('allowed_actions', []))}"
            )
        return 0
    print(json.dumps(pack, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
