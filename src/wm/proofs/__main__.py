from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wm.proofs.runner import list_proof_packets
from wm.proofs.runner import run_proof_packet


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.proofs", description="Run or list WM proof packets.")
    sub = parser.add_subparsers(dest="command", required=True)
    list_cmd = sub.add_parser("list", help="List known proof packets.")
    list_cmd.add_argument("--json", action="store_true")
    run = sub.add_parser("run", help="Run a proof packet in dry-run/record mode.")
    run.add_argument("proof_kind", choices=[packet["proof_kind"] for packet in list_proof_packets()])
    run.add_argument("--project-root", type=Path, default=Path.cwd())
    run.add_argument("--player-guid", type=int)
    run.add_argument("--mode", choices=["dry-run", "record"], default="dry-run")
    run.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "list":
        packets = list_proof_packets()
        if args.json:
            print(json.dumps({"proof_packets": packets}, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            for packet in packets:
                print(f"{packet['proof_kind']}: {packet['title']}")
        return 0
    if args.command == "run":
        record = run_proof_packet(
            proof_kind=args.proof_kind,
            project_root=args.project_root,
            player_guid=args.player_guid,
            mode=args.mode,
        )
        if args.json:
            print(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            _print_record(record)
        return 0 if record.get("status") in {"passed", "manual_required", "planned"} else 1
    return 2


def _print_record(record: dict[str, Any]) -> None:
    print(
        f"proof_id={record.get('proof_id')} kind={record.get('proof_kind')} "
        f"status={record.get('status')} mode={record.get('mode')}"
    )
    for check in record.get("checks") or []:
        print(f"  {check.get('status')} {check.get('name')}: {check.get('detail')}")
    for blocker in record.get("blockers") or []:
        print(f"  blocker: {blocker}")


if __name__ == "__main__":
    raise SystemExit(main())
