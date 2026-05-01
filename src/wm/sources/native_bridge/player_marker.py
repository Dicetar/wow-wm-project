from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.sources.native_bridge.actions import NativeBridgeActionClient


DEFAULT_MARKER_SPELL_ID = 946602


@dataclass(slots=True)
class PlayerMarkerCandidate:
    bridge_event_id: int
    occurred_at: str
    player_guid: int
    player_name: str | None
    account_id: int | None
    spell_id: int
    spell_name: str | None
    map_id: int | None
    zone_id: int | None
    area_id: int | None
    character_name: str | None = None
    character_level: int | None = None
    character_race: int | None = None
    character_class: int | None = None
    character_online: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def scan_recent_player_markers(
    *,
    client: MysqlCliClient,
    settings: Settings,
    spell_id: int = DEFAULT_MARKER_SPELL_ID,
    since_seconds: int = 300,
    limit: int = 20,
) -> list[PlayerMarkerCandidate]:
    marker_spell_id = max(1, int(spell_id))
    rows = client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=(
            "SELECT BridgeEventID, OccurredAt, PlayerGUID, AccountID, SubjectEntry, "
            "MapID, ZoneID, AreaID, PayloadJSON "
            "FROM wm_bridge_event "
            "WHERE EventFamily = 'aura' "
            "AND EventType = 'applied' "
            f"AND SubjectEntry = {marker_spell_id} "
            f"AND OccurredAt >= DATE_SUB(NOW(), INTERVAL {max(1, int(since_seconds))} SECOND) "
            "ORDER BY BridgeEventID DESC "
            f"LIMIT {max(1, int(limit))}"
        ),
    )

    candidates = [_row_to_candidate(row, marker_spell_id) for row in rows]
    _attach_character_rows(client=client, settings=settings, candidates=candidates)
    return candidates


def scope_latest_player_marker(
    *,
    client: MysqlCliClient,
    settings: Settings,
    spell_id: int = DEFAULT_MARKER_SPELL_ID,
    since_seconds: int = 300,
    profile: str = "default",
    reason: str = "WM player marker aura discovery",
    expires_seconds: int | None = None,
) -> dict[str, Any]:
    candidates = scan_recent_player_markers(
        client=client,
        settings=settings,
        spell_id=spell_id,
        since_seconds=since_seconds,
        limit=10,
    )
    if not candidates:
        return {
            "scoped": False,
            "reason": "no_marker_event",
            "spell_id": int(spell_id),
            "since_seconds": int(since_seconds),
            "candidates": [],
        }

    selected = candidates[0]
    NativeBridgeActionClient(client=client, settings=settings).enable_player_scope(
        player_guid=selected.player_guid,
        profile=profile,
        enabled=True,
        reason=reason,
        expires_seconds=expires_seconds,
    )
    return {
        "scoped": True,
        "player_guid": selected.player_guid,
        "player_name": selected.character_name or selected.player_name,
        "profile": profile,
        "expires_seconds": expires_seconds,
        "candidate": selected.to_dict(),
        "candidate_count": len(candidates),
    }


def _row_to_candidate(row: dict[str, Any], fallback_spell_id: int) -> PlayerMarkerCandidate:
    payload = _parse_payload(row.get("PayloadJSON"))
    spell_id = _int_or_none(row.get("SubjectEntry")) or _int_or_none(payload.get("spell_id")) or fallback_spell_id
    return PlayerMarkerCandidate(
        bridge_event_id=int(row["BridgeEventID"]),
        occurred_at=str(row.get("OccurredAt") or ""),
        player_guid=int(row["PlayerGUID"]),
        player_name=_str_or_none(payload.get("player_name")),
        account_id=_int_or_none(row.get("AccountID")),
        spell_id=int(spell_id),
        spell_name=_str_or_none(payload.get("aura_name")) or _str_or_none(payload.get("spell_name")),
        map_id=_int_or_none(row.get("MapID")),
        zone_id=_int_or_none(row.get("ZoneID")),
        area_id=_int_or_none(row.get("AreaID")),
    )


def _attach_character_rows(
    *,
    client: MysqlCliClient,
    settings: Settings,
    candidates: list[PlayerMarkerCandidate],
) -> None:
    guids = sorted({candidate.player_guid for candidate in candidates})
    if not guids:
        return

    rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=(
            "SELECT guid, name, race, class, level, online "
            "FROM characters "
            f"WHERE guid IN ({','.join(str(guid) for guid in guids)})"
        ),
    )
    by_guid = {int(row["guid"]): row for row in rows}
    for candidate in candidates:
        row = by_guid.get(candidate.player_guid)
        if not row:
            continue
        candidate.character_name = _str_or_none(row.get("name"))
        candidate.character_level = _int_or_none(row.get("level"))
        candidate.character_race = _int_or_none(row.get("race"))
        candidate.character_class = _int_or_none(row.get("class"))
        online = _int_or_none(row.get("online"))
        candidate.character_online = None if online is None else online > 0


def _parse_payload(raw: object) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(str(value))


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find or scope a player from a recent WM marker aura event.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="List recent marker aura applications.")
    scan.add_argument("--spell-id", type=int, default=DEFAULT_MARKER_SPELL_ID)
    scan.add_argument("--since-seconds", type=int, default=300)
    scan.add_argument("--limit", type=int, default=20)
    scan.add_argument("--summary", action="store_true")

    scope = subparsers.add_parser("scope-latest", help="Scope the latest player that applied the marker aura.")
    scope.add_argument("--spell-id", type=int, default=DEFAULT_MARKER_SPELL_ID)
    scope.add_argument("--since-seconds", type=int, default=300)
    scope.add_argument("--profile", default="default")
    scope.add_argument("--reason", default="WM player marker aura discovery")
    scope.add_argument("--expires-seconds", type=int)
    scope.add_argument("--summary", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()

    if args.command == "scan":
        candidates = scan_recent_player_markers(
            client=client,
            settings=settings,
            spell_id=args.spell_id,
            since_seconds=args.since_seconds,
            limit=args.limit,
        )
        payload: dict[str, Any] = {
            "spell_id": args.spell_id,
            "since_seconds": args.since_seconds,
            "count": len(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
    elif args.command == "scope-latest":
        payload = scope_latest_player_marker(
            client=client,
            settings=settings,
            spell_id=args.spell_id,
            since_seconds=args.since_seconds,
            profile=args.profile,
            reason=args.reason,
            expires_seconds=args.expires_seconds,
        )
    else:
        raise SystemExit(f"Unsupported command: {args.command}")

    if args.summary:
        _print_summary(args.command, payload)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _print_summary(command: str, payload: dict[str, Any]) -> None:
    if command == "scan":
        print(
            f"marker_scan spell_id={payload.get('spell_id')} since_seconds={payload.get('since_seconds')} "
            f"count={payload.get('count')}"
        )
        for index, candidate in enumerate(payload.get("candidates") or [], start=1):
            if not isinstance(candidate, dict):
                continue
            print(
                f"candidate[{index}] event={candidate.get('bridge_event_id')} "
                f"player={candidate.get('player_guid')} "
                f"name={candidate.get('character_name') or candidate.get('player_name') or '<unknown>'} "
                f"spell={candidate.get('spell_id')} online={candidate.get('character_online')}"
            )
        return

    print(
        f"marker_scope scoped={payload.get('scoped')} "
        f"player={payload.get('player_guid') or ''} "
        f"name={payload.get('player_name') or ''} "
        f"reason={payload.get('reason') or ''}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
