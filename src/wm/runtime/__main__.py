from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from wm.runtime.status import collect_runtime_status


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.runtime", description="Inspect the local WM runtime stack.")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="Print shared runtime status.")
    status.add_argument("--project-root", type=Path, default=Path.cwd())
    status.add_argument("--db-port", type=int, default=int(os.getenv("WM_WORLD_DB_PORT", "33307") or 33307))
    status.add_argument("--soap-port", type=int, default=int(os.getenv("WM_SOAP_PORT", "7879") or 7879))
    status.add_argument("--panel-host", default=os.getenv("WM_PANEL_HOST", "127.0.0.1"))
    status.add_argument("--panel-port", type=int, default=int(os.getenv("WM_PANEL_PORT", "8765") or 8765))
    status.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "status":
        payload = collect_runtime_status(
            project_root=args.project_root,
            db_port=args.db_port,
            soap_port=args.soap_port,
            panel_host=args.panel_host,
            panel_port=args.panel_port,
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            _print_status(payload)
        return 0 if payload.get("ok") else 1
    return 2


def _print_status(payload: dict[str, Any]) -> None:
    print(f"runtime ok={str(bool(payload.get('ok'))).lower()} generated_at={payload.get('generated_at')}")
    for key, svc in payload.get("services", {}).items():
        print(
            f"{key:10} state={svc.get('state')} health={svc.get('health')} "
            f"count={svc.get('logical_count')} stale={str(bool(svc.get('stale'))).lower()}"
        )
    incidents = payload.get("incidents") or []
    for item in incidents[:8]:
        print(f"incident {item.get('kind')}: {item.get('message')}")


if __name__ == "__main__":
    raise SystemExit(main())
