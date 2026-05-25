"""Utilities for assembling V2 context pack sections into a pack dict."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from wm.context.versions import CURRENT_PACK_VERSION
from wm.context.zone_mood import stub_zone_mood
from wm.context.legend import LocalLegendSection


def enrich_pack_with_v2_sections(
    pack: dict,
    *,
    player_guid: int,
    zone_id: int | None = None,
    zone_name: str = "",
    db_client: Any = None,
) -> dict:
    """Add version, zone_mood, and local_legends fields to a pack dict in-place."""
    pack["version"] = CURRENT_PACK_VERSION

    zone_mood_data: dict = {"mood_key": "neutral", "intensity": 1}
    if db_client is not None and zone_id is not None:
        try:
            from wm.living.zone_mood import evaluate_zone_mood
            zm = evaluate_zone_mood(player_guid, zone_id, db_client)
            zone_mood_data = {"mood_key": zm.mood_key, "intensity": zm.intensity}
        except Exception:
            pass

    pack["zone_mood"] = zone_mood_data

    legend_data: list = []
    if db_client is not None:
        try:
            rows = db_client.query(
                "SELECT event_type, data_json, at FROM wm_journal_special_event "
                "WHERE player_guid = %s ORDER BY at DESC LIMIT 5",
                (player_guid,),
            )
            legend_data = [
                {"event_type": r["event_type"], "at": str(r.get("at"))}
                for r in rows
            ]
        except Exception:
            pass

    pack["local_legends"] = legend_data
    return pack


def build_session_context_pack(*, player_guid: int) -> dict[str, Any]:
    """Build a player-level context pack for autoplay when no target exists yet.

    Target-specific generation should continue to use `wm.context.builder`.
    Autoplay also needs a safe session snapshot for broad proposal modes such as
    scenes/actions; this function fails soft so the service can show blockers
    instead of crashing when BridgeLab is down.
    """
    notes: list[str] = []
    character_state = None
    recent_events: list[dict[str, Any]] = []
    native_context_snapshot = None
    try:
        from wm.config import Settings
        from wm.context.builder import DbCharacterStateLoader
        from wm.context.builder import LatestNativeContextSnapshotLoader
        from wm.db.mysql_cli import MysqlCliClient
        from wm.events.store import EventStore

        settings = Settings.from_env()
        client = MysqlCliClient()
        try:
            bundle = DbCharacterStateLoader(client=client, settings=settings).load(character_guid=int(player_guid))
            character_state = asdict(bundle)
        except Exception as exc:
            notes.append(f"character_state: {type(exc).__name__}: {exc}")
        try:
            recent_events = [
                event.to_dict()
                for event in EventStore(client=client, settings=settings).list_recent_events(
                    player_guid=int(player_guid),
                    limit=10,
                    newest_first=True,
                )
            ]
        except Exception as exc:
            notes.append(f"recent_events: {type(exc).__name__}: {exc}")
        try:
            native_context_snapshot = LatestNativeContextSnapshotLoader(client=client, settings=settings).load_latest(
                player_guid=int(player_guid)
            )
        except Exception as exc:
            notes.append(f"native_context_snapshot: {type(exc).__name__}: {exc}")
    except Exception as exc:
        notes.append(f"live_context: {type(exc).__name__}: {exc}")

    status = "WORKING" if character_state is not None and not notes else "PARTIAL" if character_state is not None else "UNKNOWN"
    return {
        "schema_version": "wm.context_pack.session.v1",
        "version": CURRENT_PACK_VERSION,
        "pack_id": f"context:{int(player_guid)}:session",
        "status": status,
        "player_guid": int(player_guid),
        "character_state": character_state,
        "recent_events": recent_events,
        "native_context_snapshot": native_context_snapshot,
        "generation_input": {
            "player": {
                "guid": int(player_guid),
                "profile": (character_state or {}).get("profile") if isinstance(character_state, dict) else None,
            },
            "recent_events": recent_events,
            "native_context_snapshot": native_context_snapshot,
        },
        "notes": notes,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.context.pack")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build an autoplay session context pack.")
    build.add_argument("--player-guid", type=int, required=True)
    build.add_argument("--target-entry", type=int)
    build.add_argument("--event-id", type=int)
    build.add_argument("--runtime", action="store_true")
    build.add_argument("--summary", action="store_true")
    build.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "build":
        raise SystemExit(f"Unsupported command: {args.command}")

    if args.target_entry is not None or args.event_id is not None:
        from wm.context.builder import main as builder_main

        delegated = ["--player-guid", str(args.player_guid)]
        if args.target_entry is not None:
            delegated.extend(["--target-entry", str(args.target_entry)])
        if args.event_id is not None:
            delegated.extend(["--event-id", str(args.event_id)])
        if args.runtime:
            delegated.append("--runtime")
        if args.summary:
            delegated.append("--summary")
        if args.output_json is not None:
            delegated.extend(["--output-json", str(args.output_json)])
        return builder_main(delegated)

    payload = build_session_context_pack(player_guid=int(args.player_guid))
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        print(
            " ".join(
                [
                    f"pack={payload.get('pack_id')}",
                    f"status={payload.get('status')}",
                    f"player_guid={payload.get('player_guid')}",
                    f"recent_events={len(payload.get('recent_events') or [])}",
                    f"native_snapshot={str(bool(payload.get('native_context_snapshot'))).lower()}",
                    f"notes={len(payload.get('notes') or [])}",
                ]
            )
        )
        if args.output_json is not None:
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
