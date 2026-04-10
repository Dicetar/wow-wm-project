from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore
from wm.sources.native_bridge.scanner import NativeBridgeScanner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only peek into the native WM bridge source.")
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    cursor = store.get_cursor(adapter_name="native_bridge", cursor_key="last_seen")
    scanner = NativeBridgeScanner(client=client, settings=settings)
    result = scanner.scan(
        cursor_value=cursor.cursor_value if cursor is not None else None,
        limit=int(args.limit),
        player_guid=args.player_guid,
    )
    payload = result.to_dict()
    _emit_output(payload=payload, summary=args.summary, output_json=args.output_json)
    return 0


def _emit_output(*, payload: dict[str, object], summary: bool, output_json: Path | None) -> None:
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(raw, encoding="utf-8")
    if summary:
        cursor = payload.get("cursor") if isinstance(payload.get("cursor"), dict) else {}
        records = payload.get("records") if isinstance(payload.get("records"), list) else []
        failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
        print(
            f"table_exists={payload.get('table_exists')} last_seen={cursor.get('last_seen_id')} "
            f"records={len(records)} failures={len(failures)}"
        )
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                continue
            print(
                f"record[{index}] id={record.get('bridge_event_id')} family={record.get('event_family')} "
                f"type={record.get('event_type')} player={record.get('player_guid')} "
                f"subject={record.get('subject_type')}:{record.get('subject_entry')}"
            )
        for index, failure in enumerate(failures, start=1):
            if not isinstance(failure, dict):
                continue
            print(
                f"failure[{index}] reason={failure.get('reason')} "
                f"id={failure.get('bridge_event_id')} event={failure.get('event_family')}.{failure.get('event_type')}"
            )
    else:
        print(raw)


if __name__ == "__main__":
    raise SystemExit(main())
