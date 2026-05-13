from __future__ import annotations

import argparse
from pathlib import Path

from wm.panel.server import serve


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.panel")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--state-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    serve(host=args.host, port=args.port, state_root=args.state_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
