from __future__ import annotations

import argparse
import json
import sys

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.reserved.cli import ReservedCliError, ensure_status, parse_notes_arg, render_slot, render_summary
from wm.reserved.db_allocator import ReservedSlotDbAllocator


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wm.reserved.commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser(
        "summary",
        help="Show reserved slot summary from acore_world.",
    )
    summary_parser.set_defaults(command_handler=_handle_summary)

    allocate_parser = subparsers.add_parser(
        "allocate",
        help="Allocate the next free reserved slot for an entity type.",
    )
    allocate_parser.add_argument("--entity-type", required=True)
    allocate_parser.add_argument("--arc-key")
    allocate_parser.add_argument("--character-guid", type=int)
    allocate_parser.add_argument("--source-quest-id", type=int)
    allocate_parser.add_argument("--note", action="append")
    allocate_parser.set_defaults(command_handler=_handle_allocate)

    transition_parser = subparsers.add_parser(
        "transition",
        help="Transition a reserved slot to a new status.",
    )
    transition_parser.add_argument("--entity-type", required=True)
    transition_parser.add_argument("--reserved-id", type=int, required=True)
    transition_parser.add_argument("--status", required=True)
    transition_parser.set_defaults(command_handler=_handle_transition)

    release_parser = subparsers.add_parser(
        "release",
        help="Release a reserved slot to retired or archived.",
    )
    release_parser.add_argument("--entity-type", required=True)
    release_parser.add_argument("--reserved-id", type=int, required=True)
    release_parser.add_argument("--archive", action="store_true")
    release_parser.set_defaults(command_handler=_handle_release)

    get_parser = subparsers.add_parser(
        "get",
        help="Fetch one reserved slot by entity type and reserved ID.",
    )
    get_parser.add_argument("--entity-type", required=True)
    get_parser.add_argument("--reserved-id", type=int, required=True)
    get_parser.set_defaults(command_handler=_handle_get)

    return parser


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_env()
    parser = _build_parser()
    args = parser.parse_args(argv)

    client = MysqlCliClient()
    allocator = ReservedSlotDbAllocator(client=client, settings=settings)

    try:
        return args.command_handler(args, allocator)
    except ReservedCliError as exc:
        print(json.dumps({"error": str(exc)}, indent=2, ensure_ascii=False))
        return 2


def _handle_summary(args: argparse.Namespace, allocator: ReservedSlotDbAllocator) -> int:
    del args
    print(json.dumps(render_summary(allocator.summarize()), indent=2, ensure_ascii=False))
    return 0


def _handle_allocate(args: argparse.Namespace, allocator: ReservedSlotDbAllocator) -> int:
    slot = allocator.allocate_next_free_slot(
        entity_type=args.entity_type,
        arc_key=args.arc_key,
        character_guid=args.character_guid,
        source_quest_id=args.source_quest_id,
        notes=parse_notes_arg(args.note),
    )
    print(json.dumps(render_slot(slot), indent=2, ensure_ascii=False))
    return 0 if slot is not None else 3


def _handle_transition(args: argparse.Namespace, allocator: ReservedSlotDbAllocator) -> int:
    slot = allocator.transition_slot(
        entity_type=args.entity_type,
        reserved_id=args.reserved_id,
        new_status=ensure_status(args.status),
    )
    print(json.dumps(render_slot(slot), indent=2, ensure_ascii=False))
    return 0 if slot is not None else 3


def _handle_release(args: argparse.Namespace, allocator: ReservedSlotDbAllocator) -> int:
    slot = allocator.release_slot(
        entity_type=args.entity_type,
        reserved_id=args.reserved_id,
        archive=bool(args.archive),
    )
    print(json.dumps(render_slot(slot), indent=2, ensure_ascii=False))
    return 0 if slot is not None else 3


def _handle_get(args: argparse.Namespace, allocator: ReservedSlotDbAllocator) -> int:
    slot = allocator.get_slot(
        entity_type=args.entity_type,
        reserved_id=args.reserved_id,
    )
    print(json.dumps(render_slot(slot), indent=2, ensure_ascii=False))
    return 0 if slot is not None else 3


if __name__ == "__main__":
    sys.exit(main())
