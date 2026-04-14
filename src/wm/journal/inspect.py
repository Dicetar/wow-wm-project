from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.journal.reader import SubjectJournalBundle, load_subject_journal_for_creature
from wm.subjects.resolver import build_subject_card_from_profile
from wm.targets.resolver import LookupStore, TargetResolver
from wm.targets.runtime_resolver import RuntimeTargetResolver


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.journal.inspect")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--target-entry", type=int, required=True)
    parser.add_argument(
        "--lookup-json",
        type=Path,
        default=Path("data/lookup/creature_template_full.json"),
        help="Static creature lookup JSON used unless --runtime is set.",
    )
    parser.add_argument("--runtime", action="store_true", help="Resolve target profile from the live world DB.")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    target_profile = _resolve_target_profile(args=args, client=client, settings=settings)
    if target_profile is None:
        print(f"journal_resolved=false target_entry={int(args.target_entry)}")
        return 2

    bundle = load_subject_journal_for_creature(
        client=client,
        settings=settings,
        player_guid=int(args.player_guid),
        creature_entry=int(args.target_entry),
        resolved_subject_card=build_subject_card_from_profile(target_profile),
    )
    payload = _bundle_to_dict(
        bundle=bundle,
        player_guid=int(args.player_guid),
        target_profile=target_profile.to_dict(),
    )
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        print(_render_summary(payload))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    return 0


def _resolve_target_profile(*, args: argparse.Namespace, client: MysqlCliClient, settings: Settings) -> Any | None:
    if args.runtime:
        return RuntimeTargetResolver(client=client, settings=settings).resolve_creature_entry(int(args.target_entry))
    return TargetResolver(store=LookupStore.from_json(args.lookup_json)).resolve_creature_entry(int(args.target_entry))


def _bundle_to_dict(
    *,
    bundle: SubjectJournalBundle,
    player_guid: int,
    target_profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "player_guid": int(player_guid),
        "target_entry": int(target_profile["entry"]),
        "status": bundle.status,
        "source_flags": list(bundle.source_flags),
        "subject_id": bundle.subject_id,
        "target_profile": target_profile,
        "subject_card": asdict(bundle.subject_card) if bundle.subject_card is not None else None,
        "counters": asdict(bundle.counters) if bundle.counters is not None else None,
        "events": [asdict(event) for event in bundle.events],
        "summary": (
            {
                "title": bundle.summary.title,
                "description": bundle.summary.description,
                "history_lines": bundle.summary.history_lines,
                "raw": bundle.summary.raw,
            }
            if bundle.summary is not None
            else None
        ),
        "definition": bundle.definition,
        "enrichment": bundle.enrichment,
    }


def _render_summary(payload: dict[str, Any]) -> str:
    target = payload.get("target_profile") or {}
    counters = payload.get("counters") or {}
    summary = payload.get("summary") or {}
    return "\n".join(
        [
            f"journal: player={payload.get('player_guid')} target={payload.get('target_entry')} | {target.get('name')}",
            f"status: {payload.get('status')}",
            f"source_flags: {', '.join(payload.get('source_flags') or []) or '(none)'}",
            f"subject_id: {payload.get('subject_id')}",
            f"counters: kills={counters.get('kill_count', 0)}, skins={counters.get('skin_count', 0)}, feeds={counters.get('feed_count', 0)}, talks={counters.get('talk_count', 0)}, quests={counters.get('quest_complete_count', 0)}",
            f"events: {len(payload.get('events') or [])}",
            f"summary_title: {summary.get('title')}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
