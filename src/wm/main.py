from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from wm.config import Settings
from wm.targets.resolver import LookupStore, TargetResolver


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wow-wm-project")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser(
        "resolve-target",
        help="Resolve a creature entry into a normalized target profile.",
    )
    resolve_parser.add_argument("--entry", type=int, required=True)
    resolve_parser.add_argument(
        "--lookup",
        type=Path,
        required=True,
        help="Path to creature_template_full-style JSON export.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    Settings.from_env()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "resolve-target":
        store = LookupStore.from_json(args.lookup)
        resolver = TargetResolver(store=store)
        profile = resolver.resolve_creature_entry(args.entry)
        if profile is None:
            print(json.dumps({"error": f"entry {args.entry} not found"}, indent=2))
            return 1
        print(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
