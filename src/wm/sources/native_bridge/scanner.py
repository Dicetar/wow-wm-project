from __future__ import annotations

import json

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.sources.native_bridge.models import NativeBridgeCursor
from wm.sources.native_bridge.models import NativeBridgeFailure
from wm.sources.native_bridge.models import NativeBridgeRecord
from wm.sources.native_bridge.models import NativeBridgeScanResult


class NativeBridgeScanner:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def scan(
        self,
        *,
        cursor_value: str | None = None,
        limit: int = 100,
        player_guid: int | None = None,
    ) -> NativeBridgeScanResult:
        cursor = NativeBridgeCursor.from_cursor_value(cursor_value)
        if not self._bridge_table_exists():
            return NativeBridgeScanResult(table_exists=False, cursor=cursor)

        predicates = [f"BridgeEventID > {int(cursor.last_seen_id)}"]
        if player_guid is not None:
            predicates.append(f"PlayerGUID = {int(player_guid)}")
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT BridgeEventID, OccurredAt, EventFamily, EventType, Source, PlayerGUID, AccountID, "
                "SubjectType, SubjectGUID, SubjectEntry, ObjectType, ObjectGUID, ObjectEntry, "
                "MapID, ZoneID, AreaID, PayloadJSON "
                "FROM wm_bridge_event "
                f"WHERE {' AND '.join(predicates)} "
                "ORDER BY BridgeEventID "
                f"LIMIT {int(limit)}"
            ),
        )

        records: list[NativeBridgeRecord] = []
        failures: list[NativeBridgeFailure] = []
        last_seen_id = int(cursor.last_seen_id)
        for row in rows:
            bridge_event_id = int(row["BridgeEventID"])
            last_seen_id = max(last_seen_id, bridge_event_id)
            payload = _parse_payload(row.get("PayloadJSON"))
            if payload is None:
                failures.append(
                    NativeBridgeFailure(
                        reason="invalid_payload_json",
                        bridge_event_id=bridge_event_id,
                        event_family=_str_or_none(row.get("EventFamily")),
                        event_type=_str_or_none(row.get("EventType")),
                        details={"raw_payload": row.get("PayloadJSON")},
                    )
                )
                continue
            records.append(
                NativeBridgeRecord(
                    bridge_event_id=bridge_event_id,
                    occurred_at=str(row.get("OccurredAt") or ""),
                    event_family=str(row.get("EventFamily") or ""),
                    event_type=str(row.get("EventType") or ""),
                    source=str(row.get("Source") or "native_bridge"),
                    player_guid=_int_or_none(row.get("PlayerGUID")),
                    account_id=_int_or_none(row.get("AccountID")),
                    subject_type=_str_or_none(row.get("SubjectType")),
                    subject_guid=_str_or_none(row.get("SubjectGUID")),
                    subject_entry=_int_or_none(row.get("SubjectEntry")),
                    object_type=_str_or_none(row.get("ObjectType")),
                    object_guid=_str_or_none(row.get("ObjectGUID")),
                    object_entry=_int_or_none(row.get("ObjectEntry")),
                    map_id=_int_or_none(row.get("MapID")),
                    zone_id=_int_or_none(row.get("ZoneID")),
                    area_id=_int_or_none(row.get("AreaID")),
                    payload=payload,
                )
            )

        return NativeBridgeScanResult(
            table_exists=True,
            cursor=NativeBridgeCursor(last_seen_id=last_seen_id),
            records=records,
            failures=failures,
        )

    def _bridge_table_exists(self) -> bool:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql="SHOW TABLES LIKE 'wm_bridge_event'",
        )
        return bool(rows)


def _parse_payload(raw_payload: object) -> dict[str, object] | None:
    if raw_payload in (None, ""):
        return {}
    try:
        parsed = json.loads(str(raw_payload))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(str(value))


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
