from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.autoplay.service import AutoplayRuntimeConfig
from wm.autoplay.service import AutoplayService
from wm.autoplay.service import status_summary
from wm.autoplay.state import AutoplayStateStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.autoplay", description="Run the local WM autoplay service.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run autoplay until stopped.")
    run.add_argument("--player-guid", type=int)
    run.add_argument("--interval-seconds", type=float, default=2.0)
    run.add_argument("--state-root", type=Path, default=None)
    run.add_argument("--project-root", type=Path, default=Path.cwd())
    run.add_argument("--lab-mysql-port", type=int, default=33307)
    run.add_argument("--soap-port", type=int, default=7879)
    run.add_argument("--once", action="store_true")
    run.add_argument("--no-start-watcher", action="store_true")
    run.add_argument("--summary", action="store_true")

    status = subparsers.add_parser("status", help="Print autoplay status.")
    status.add_argument("--state-root", type=Path, default=None)
    status.add_argument("--summary", action="store_true")

    stop = subparsers.add_parser("stop", help="Request autoplay stop.")
    stop.add_argument("--state-root", type=Path, default=None)
    stop.add_argument("--summary", action="store_true")

    pause = subparsers.add_parser("pause", help="Pause autoplay.")
    pause.add_argument("--state-root", type=Path, default=None)
    pause.add_argument("--summary", action="store_true")

    resume = subparsers.add_parser("resume", help="Resume autoplay.")
    resume.add_argument("--state-root", type=Path, default=None)
    resume.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    store = AutoplayStateStore(args.state_root) if args.state_root is not None else AutoplayStateStore()

    if args.command == "status":
        status = store.load_status()
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "stop":
        status = store.request_stop()
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "pause":
        status = store.set_paused(True)
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "resume":
        status = store.set_paused(False)
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "run":
        config = AutoplayRuntimeConfig(
            player_guid=args.player_guid,
            interval_seconds=args.interval_seconds,
            start_watcher=not bool(args.no_start_watcher),
            bridge_lab_mysql_port=args.lab_mysql_port,
            soap_port=args.soap_port,
            project_root=args.project_root.resolve(),
        )
        code = AutoplayService(store=store).run_forever(config=config, once=bool(args.once))
        if args.summary:
            print(status_summary(store.load_status()))
        return code
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
