from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.subjects.resolver import SubjectResolver
from wm.targets.resolver import LookupStore, TargetResolver
from wm.targets.runtime_resolver import RuntimeTargetResolver


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve a raw WM target into a subject card.")
    parser.add_argument("--entry", type=int, required=True, help="Creature template entry to resolve.")
    parser.add_argument(
        "--lookup-json",
        type=Path,
        default=Path("data/lookup/creature_template_full.json"),
        help="Static creature lookup JSON used unless --runtime is set.",
    )
    parser.add_argument("--runtime", action="store_true", help="Resolve from the live world DB.")
    parser.add_argument("--summary", action="store_true", help="Print a compact subject summary.")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    resolver = _build_resolver(args)
    card = resolver.resolve_creature_entry(args.entry)
    if card is None:
        print(f"subject_resolved=false entry={args.entry}")
        return 2

    payload = card.to_dict()
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        print(_render_summary(payload))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    return 0


def _build_resolver(args: argparse.Namespace) -> SubjectResolver:
    if args.runtime:
        settings = Settings.from_env()
        return SubjectResolver(RuntimeTargetResolver(client=MysqlCliClient(), settings=settings))
    store = LookupStore.from_json(args.lookup_json)
    return SubjectResolver(TargetResolver(store=store))


def _render_summary(payload: dict[str, object]) -> str:
    return "\n".join(
        [
            f"subject: {payload.get('canonical_id')} | {payload.get('display_name')}",
            f"kind: {payload.get('kind')}",
            f"archetype: {payload.get('archetype')}",
            f"faction: {payload.get('faction_label')}",
            f"roles: {', '.join(payload.get('role_tags') or [])}",
            f"groups: {', '.join(payload.get('group_keys') or [])}",
            f"areas: {', '.join(payload.get('area_tags') or [])}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
