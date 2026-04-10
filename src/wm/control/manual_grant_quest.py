from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.control._cli import default_proposal_output_path
from wm.control._cli import load_registry
from wm.control.builder import build_manual_proposal
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a manual quest_grant ControlProposal.")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--quest-id", type=int, required=True)
    parser.add_argument("--event-id", type=int)
    parser.add_argument("--turn-in-npc-entry", type=int)
    parser.add_argument("--rule-key")
    parser.add_argument("--manual-reason")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    registry = load_registry(settings)
    event = None
    if args.event_id is not None:
        event = EventStore(client=MysqlCliClient(), settings=settings).get_event(event_id=args.event_id)
        if event is None:
            raise SystemExit(f"Event not found: {args.event_id}")
    author_kind = "manual" if event is not None else "manual_admin"
    if author_kind == "manual_admin" and not args.manual_reason:
        raise SystemExit("--manual-reason is required when creating an admin proposal without --event-id.")
    payload = {"player_guid": args.player_guid, "quest_id": args.quest_id}
    if args.turn_in_npc_entry is not None:
        payload["turn_in_npc_entry"] = args.turn_in_npc_entry
    if args.rule_key:
        payload["rule_key"] = args.rule_key
    proposal = build_manual_proposal(
        event=event,
        registry=registry,
        recipe_id="kill_burst_bounty" if event is not None else "manual_admin_action",
        action_kind="quest_grant",
        author_kind=author_kind,
        manual_reason=args.manual_reason,
        payload_overrides=payload,
    )
    output = args.output or default_proposal_output_path(
        settings,
        event_id=args.event_id,
        recipe_id=proposal.selected_recipe,
        action_kind="quest_grant",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(proposal.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True)
    output.write_text(raw + "\n", encoding="utf-8")
    print(f"proposal_written={output}")
    print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
