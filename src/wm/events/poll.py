from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.adapters import ADAPTER_CHOICES
from wm.events.adapters import build_event_adapter
from wm.events.store import EventStore
from wm.reactive.store import ReactiveQuestStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Poll a WM event adapter and record canonical events.")
    parser.add_argument("--adapter", choices=ADAPTER_CHOICES, default="db")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    reactive_store = ReactiveQuestStore(client=client, settings=settings)
    batch_size = _resolve_batch_size(adapter_name=args.adapter, requested_batch_size=args.batch_size, settings=settings)
    adapter = build_event_adapter(
        adapter_name=args.adapter,
        client=client,
        settings=settings,
        store=store,
        reactive_store=reactive_store,
        batch_size=batch_size,
        player_guid_filter=args.player_guid,
    )

    events = adapter.poll()
    record_result = store.record(events)
    if adapter.last_cursor_value is not None:
        store.set_cursor(adapter_name=adapter.name, cursor_key=adapter.cursor_key, cursor_value=adapter.last_cursor_value)

    payload = {
        "adapter": adapter.name,
        "player_guid_filter": args.player_guid,
        "polled_count": len(events),
        "recorded_count": len(record_result.recorded),
        "skipped_count": len(record_result.skipped),
        "record_result": record_result.to_dict(),
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
            f"adapter={payload['adapter']} player_guid={payload['player_guid_filter']} polled={payload['polled_count']} "
            f"recorded={payload['recorded_count']} skipped={payload['skipped_count']}"
        )
    else:
        print(raw)


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
