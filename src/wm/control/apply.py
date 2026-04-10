from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.control._cli import build_live_coordinator
from wm.control._cli import load_proposal


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run or apply a WM ControlProposal.")
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--confirm-live-apply", action="store_true")
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    proposal = load_proposal(args.proposal)
    coordinator = build_live_coordinator(Settings.from_env())
    result = coordinator.execute(
        proposal=proposal,
        mode=args.mode,
        confirm_live_apply=args.confirm_live_apply,
    )
    if args.summary:
        print(
            f"status={result.status} mode={args.mode} action={proposal.action.kind} "
            f"recipe={proposal.selected_recipe} issues={len(result.issues or [])}"
        )
        for issue in result.issues or []:
            print(f"{issue.severity} path={issue.path} message={issue.message}")
    else:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.status in {"dry-run", "applied"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
