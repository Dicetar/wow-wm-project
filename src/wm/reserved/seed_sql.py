from __future__ import annotations

import argparse
import json
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wm.reserved.seed_sql")
    parser.add_argument(
        "--ranges",
        type=Path,
        default=Path(r"D:\WOW\wm-project\data\specs\reserved_id_ranges.json"),
        help="Path to reserved ID range JSON spec.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(r"D:\WOW\wm-project\sql\dev\generated_seed_reserved_slots.sql"),
        help="Output SQL path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    payload = json.loads(args.ranges.read_text(encoding="utf-8"))
    ranges = payload.get("ranges", {})

    statements: list[str] = [
        "-- Generated reserved slot seed SQL",
        "-- This file is safe to re-run because it uses INSERT IGNORE.",
        "",
    ]

    for entity_type, spec in ranges.items():
        start = spec.get("start")
        end = spec.get("end")
        if start is None or end is None:
            continue
        statements.append(f"-- {entity_type}: {start}..{end}")
        for reserved_id in range(int(start), int(end) + 1):
            statements.append(
                "INSERT IGNORE INTO wm_reserved_slot "
                "(EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON) "
                f"VALUES ('{entity_type}', {reserved_id}, 'free', NULL, NULL, NULL, NULL);"
            )
        statements.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(statements), encoding="utf-8")
    print(f"Wrote seed SQL to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
