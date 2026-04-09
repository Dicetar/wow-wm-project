from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore
from wm.reactive.store import ReactiveQuestStore
from wm.sources.addon_log.scanner import AddonLogScanner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only peek into the hidden addon-log source.")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    reactive_store = ReactiveQuestStore(client=client, settings=settings)
    cursor = store.get_cursor(adapter_name="addon_log", cursor_key="state")
    scanner = AddonLogScanner(client=client, settings=settings, reactive_store=reactive_store)
    result = scanner.scan(
        player_guid=int(args.player_guid),
        cursor_value=cursor.cursor_value if cursor is not None else None,
        limit=int(args.limit),
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
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else []
        failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
        print(
            f"file_exists={payload.get('file_exists')} path={payload.get('path')} "
            f"offset={cursor.get('offset')} signals={len(signals)} failures={len(failures)}"
        )
        for index, signal in enumerate(signals, start=1):
            if not isinstance(signal, dict):
                continue
            player = signal.get("player_ref") if isinstance(signal.get("player_ref"), dict) else {}
            subject = signal.get("subject_ref") if isinstance(signal.get("subject_ref"), dict) else {}
            print(
                f"signal[{index}] type={signal.get('event_type')} at={signal.get('occurred_at')} "
                f"player={player.get('name') or player.get('guid')} "
                f"subject={subject.get('name') or subject.get('entry') or '-'} "
                f"offset={signal.get('byte_offset')}"
            )
        for index, failure in enumerate(failures, start=1):
            if not isinstance(failure, dict):
                continue
            print(
                f"failure[{index}] reason={failure.get('reason')} offset={failure.get('byte_offset')} "
                f"event={failure.get('event_type')}"
            )
    else:
        print(raw)


if __name__ == "__main__":
    raise SystemExit(main())
