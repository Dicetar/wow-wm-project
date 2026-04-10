from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.control._cli import default_proposal_output_path
from wm.control._cli import load_registry
from wm.control.builder import build_manual_proposal


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a manual announcement ControlProposal.")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--manual-reason", required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    proposal = build_manual_proposal(
        event=None,
        registry=load_registry(settings),
        recipe_id="manual_admin_action",
        action_kind="announcement",
        author_kind="manual_admin",
        manual_reason=args.manual_reason,
        payload_overrides={"player_guid": args.player_guid, "text": args.text},
    )
    output = args.output or default_proposal_output_path(
        settings,
        event_id=None,
        recipe_id=proposal.selected_recipe,
        action_kind="announcement",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(proposal.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True)
    output.write_text(raw + "\n", encoding="utf-8")
    print(f"proposal_written={output}")
    print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
