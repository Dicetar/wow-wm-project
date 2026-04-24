from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore
from wm.sources.native_bridge.models import NativeBridgeCursor
from wm.sources.native_bridge.models import native_bridge_cursor_key


@dataclass(slots=True)
class NativeBridgeArmResult:
    table_exists: bool
    previous_last_seen: int | None
    armed_last_seen: int
    player_guid: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "table_exists": self.table_exists,
            "previous_last_seen": self.previous_last_seen,
            "armed_last_seen": self.armed_last_seen,
            "player_guid": self.player_guid,
        }


def arm_native_bridge_cursor(
    *,
    settings: Settings,
    store: EventStore,
    player_guid: int | None,
    client: MysqlCliClient | None = None,
) -> NativeBridgeArmResult:
    client = client or MysqlCliClient()
    cursor_key = native_bridge_cursor_key(player_guid)
    existing = store.get_cursor(adapter_name="native_bridge", cursor_key=cursor_key)
    previous_last_seen: int | None = None
    if existing is not None:
        previous_last_seen = NativeBridgeCursor.from_cursor_value(existing.cursor_value).last_seen_id

    if not _bridge_table_exists(client=client, settings=settings):
        store.set_cursor(adapter_name="native_bridge", cursor_key=cursor_key, cursor_value="0")
        return NativeBridgeArmResult(
            table_exists=False,
            previous_last_seen=previous_last_seen,
            armed_last_seen=0,
            player_guid=player_guid,
        )

    armed_last_seen = _latest_bridge_event_id(client=client, settings=settings, player_guid=player_guid)
    store.set_cursor(
        adapter_name="native_bridge",
        cursor_key=cursor_key,
        cursor_value=NativeBridgeCursor(last_seen_id=armed_last_seen).to_cursor_value(),
    )
    return NativeBridgeArmResult(
        table_exists=True,
        previous_last_seen=previous_last_seen,
        armed_last_seen=armed_last_seen,
        player_guid=player_guid,
    )


def _bridge_table_exists(*, client: MysqlCliClient, settings: Settings) -> bool:
    rows = client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql="SHOW TABLES LIKE 'wm_bridge_event'",
    )
    return bool(rows)


def _latest_bridge_event_id(*, client: MysqlCliClient, settings: Settings, player_guid: int | None) -> int:
    predicate = ""
    if player_guid is not None:
        predicate = f" WHERE PlayerGUID = {int(player_guid)}"
    rows = client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=f"SELECT COALESCE(MAX(BridgeEventID), 0) AS LastSeenID FROM wm_bridge_event{predicate}",
    )
    if not rows:
        return 0
    return int(rows[0].get("LastSeenID") or 0)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Arm the native WM bridge cursor from the current high-water mark.")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    result = arm_native_bridge_cursor(
        settings=settings,
        store=store,
        player_guid=args.player_guid,
        client=client,
    )
    payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")
    if args.summary:
        print(
            f"table_exists={result.table_exists} player_guid={result.player_guid} "
            f"previous_last_seen={result.previous_last_seen} armed_last_seen={result.armed_last_seen}"
        )
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
