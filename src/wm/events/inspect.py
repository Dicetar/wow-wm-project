from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect recent WM event, reaction, and cooldown state without mutating it.")
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    payload = build_inspect_payload(store=store, player_guid=args.player_guid, limit=args.limit)
    _emit_output(payload=payload, summary=args.summary, output_json=args.output_json)
    return 0


def build_inspect_payload(*, store: EventStore, player_guid: int | None, limit: int) -> dict[str, object]:
    observed_events = store.list_recent_events(
        event_class="observed",
        player_guid=player_guid,
        limit=limit,
        newest_first=True,
    )
    derived_events = store.list_recent_events(
        event_class="derived",
        player_guid=player_guid,
        limit=limit,
        newest_first=True,
    )
    action_events = store.list_recent_events(
        event_class="action",
        player_guid=player_guid,
        limit=limit,
        newest_first=True,
    )
    reaction_logs = store.list_recent_reaction_logs(player_guid=player_guid, limit=limit)
    active_cooldowns = store.list_active_cooldowns(player_guid=player_guid, limit=limit)
    return {
        "player_guid_filter": player_guid,
        "limit": limit,
        "events": {
            "observed": [event.to_dict() for event in observed_events],
            "derived": [event.to_dict() for event in derived_events],
            "action": [event.to_dict() for event in action_events],
        },
        "reaction_logs": [record.to_dict() for record in reaction_logs],
        "active_cooldowns": [record.to_dict() for record in active_cooldowns],
        "counts": {
            "observed": len(observed_events),
            "derived": len(derived_events),
            "action": len(action_events),
            "reaction_logs": len(reaction_logs),
            "active_cooldowns": len(active_cooldowns),
        },
    }


def _emit_output(*, payload: dict[str, object], summary: bool, output_json: Path | None) -> None:
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(raw, encoding="utf-8")
    if summary:
        counts = payload.get("counts", {})
        if not isinstance(counts, dict):
            counts = {}
        print(
            f"player_guid={payload.get('player_guid_filter')} observed={counts.get('observed', 0)} "
            f"derived={counts.get('derived', 0)} action={counts.get('action', 0)} "
            f"reactions={counts.get('reaction_logs', 0)} cooldowns={counts.get('active_cooldowns', 0)}"
        )
        for line in _build_summary_lines(payload):
            print(line)
    else:
        print(raw)


def _build_summary_lines(payload: dict[str, object]) -> list[str]:
    lines: list[str] = []
    events = payload.get("events")
    if isinstance(events, dict):
        for event_class in ("observed", "derived", "action"):
            rows = events.get(event_class)
            if not isinstance(rows, list):
                continue
            for index, event in enumerate(rows, start=1):
                if not isinstance(event, dict):
                    continue
                lines.append(
                    f"{event_class}[{index}] type={event.get('event_type')} "
                    f"subject={event.get('subject_type')}:{event.get('subject_entry')} "
                    f"occurred_at={event.get('occurred_at')}"
                )
    reaction_logs = payload.get("reaction_logs")
    if isinstance(reaction_logs, list):
        for index, record in enumerate(reaction_logs, start=1):
            if not isinstance(record, dict):
                continue
            subject = record.get("subject") if isinstance(record.get("subject"), dict) else {}
            lines.append(
                f"reaction[{index}] status={record.get('status')} rule={record.get('rule_type')} "
                f"subject={subject.get('subject_type')}:{subject.get('subject_entry')} "
                f"created_at={record.get('created_at')}"
            )
    cooldowns = payload.get("active_cooldowns")
    if isinstance(cooldowns, list):
        for index, record in enumerate(cooldowns, start=1):
            if not isinstance(record, dict):
                continue
            subject = record.get("subject") if isinstance(record.get("subject"), dict) else {}
            lines.append(
                f"cooldown[{index}] rule={record.get('rule_type')} "
                f"subject={subject.get('subject_type')}:{subject.get('subject_entry')} "
                f"until={record.get('cooldown_until')}"
            )
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
