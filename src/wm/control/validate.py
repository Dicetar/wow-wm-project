from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from wm.config import Settings
from wm.control._cli import build_live_coordinator
from wm.control._cli import load_proposal


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a WM ControlProposal JSON file.")
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        proposal = load_proposal(args.proposal)
    except ValidationError as exc:
        print(exc)
        return 1
    coordinator = build_live_coordinator(Settings.from_env())
    result = coordinator.validate(proposal)
    if args.summary:
        print(f"ok={result.ok} issues={len(result.issues)} registry_hash={result.registry_hash}")
        for issue in result.issues:
            print(f"{issue.severity} path={issue.path} message={issue.message}")
    else:
        print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
