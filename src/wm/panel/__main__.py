from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.panel.server import serve


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.panel")
    sub = parser.add_subparsers(dest="subcommand")

    serve_p = sub.add_parser("serve", help="Start the web panel server (default)")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8765)
    serve_p.add_argument("--state-root", type=Path)
    serve_p.add_argument("--live-slice", action="store_true",
                         help="Wire the slice approval gate to the live MySQL spine + native bus.")
    serve_p.add_argument("--db-host", default="127.0.0.1")
    serve_p.add_argument("--db-port", type=int, default=33307)
    serve_p.add_argument("--db-user", default="acore")
    serve_p.add_argument("--db-password", default="acore")
    serve_p.add_argument("--world-db", default="acore_world")

    sum_p = sub.add_parser("summary", help="Print a read-only operator dashboard summary")
    sum_p.add_argument("--json", action="store_true", help="Output as JSON")

    # Legacy flat flags for `wm panel` without a subcommand (backwards compat)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--live-slice", action="store_true",
                        help="Wire the slice approval gate to the live MySQL spine + native bus.")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=33307)
    parser.add_argument("--db-user", default="acore")
    parser.add_argument("--db-password", default="acore")
    parser.add_argument("--world-db", default="acore_world")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.subcommand == "summary":
        from wm.panel.summary import build_panel
        report = build_panel()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(f"WM Panel Summary  [{report.generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC]")
            print()
            for check in report.health:
                flag = f"[{check.status:<8}]"
                detail = f"  {check.detail}" if check.detail else ""
                print(f"  {flag} {check.name}{detail}")
            if report.living_readiness:
                print()
                print("  Living World:")
                for key, live in report.living_readiness.items():
                    print(f"    {'LIVE  ' if live else 'GATED '} {key}")
            if report.feature_counts:
                print()
                total = sum(report.feature_counts.values())
                layers = "  ".join(f"{k}:{v}" for k, v in sorted(report.feature_counts.items()))
                print(f"  Features: {total} tracked  ({layers})")
        return 0

    # Default: serve (subcommand == "serve" or None for legacy invocation)
    host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"
    port = getattr(args, "port", 8765) or 8765
    state_root = getattr(args, "state_root", None)
    serve(host=host, port=int(port), state_root=state_root,
          live_slice=bool(getattr(args, "live_slice", False)),
          db_host=getattr(args, "db_host", "127.0.0.1") or "127.0.0.1",
          db_port=int(getattr(args, "db_port", 33307) or 33307),
          db_user=getattr(args, "db_user", "acore") or "acore",
          db_password=getattr(args, "db_password", "acore") or "acore",
          world_db=getattr(args, "world_db", "acore_world") or "acore_world")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
