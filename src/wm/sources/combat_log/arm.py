from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore
from wm.sources.combat_log.models import CombatLogCursor
from wm.sources.combat_log.models import fingerprint_for_path


@dataclass(slots=True)
class CombatLogArmResult:
    file_exists: bool
    path: str
    previous_offset: int | None
    armed_offset: int
    fingerprint: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def arm_combat_log_cursor(*, settings: Settings, store: EventStore) -> CombatLogArmResult:
    path = Path(settings.combat_log_path)
    existing = store.get_cursor(adapter_name="combat_log", cursor_key="state")
    previous_offset: int | None = None
    if existing is not None:
        try:
            previous_offset = int(CombatLogCursor.from_cursor_value(existing.cursor_value, default_path=str(path)).offset)
        except ValueError:
            previous_offset = None

    if not path.exists():
        cursor = CombatLogCursor(path=str(path), offset=0, fingerprint=None)
        store.set_cursor(adapter_name="combat_log", cursor_key="state", cursor_value=cursor.to_cursor_value())
        return CombatLogArmResult(
            file_exists=False,
            path=str(path),
            previous_offset=previous_offset,
            armed_offset=0,
            fingerprint=None,
        )

    fingerprint = fingerprint_for_path(path)
    armed_offset = int(path.stat().st_size)
    cursor = CombatLogCursor(path=str(path), offset=armed_offset, fingerprint=fingerprint)
    store.set_cursor(adapter_name="combat_log", cursor_key="state", cursor_value=cursor.to_cursor_value())
    return CombatLogArmResult(
        file_exists=True,
        path=str(path),
        previous_offset=previous_offset,
        armed_offset=armed_offset,
        fingerprint=fingerprint,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast-forward the combat-log cursor to the current end of file.")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    result = arm_combat_log_cursor(settings=settings, store=store)
    payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")
    if args.summary or args.output_json is not None:
        print(
            f"file_exists={result.file_exists} path={result.path} previous_offset={result.previous_offset} "
            f"armed_offset={result.armed_offset}"
        )
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
