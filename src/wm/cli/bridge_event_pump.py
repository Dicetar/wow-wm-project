"""Bridge event pump — polls wm_bridge_event and dispatches to the slice runtime.

Architecture: the native bridge writes observed/derived events into the
wm_bridge_event table. This pump polls that table for the active
character, normalizes rows into runtime events, and fans them to
runtime.feed_use_item / feed_quest_completed / feed_kill. Other event
types are skipped quietly (catch-and-park principle).

The pump is decoupled from the live DB via a `fetch` callable injected
at construction. Production uses `make_mysql_fetch(...)`; tests inject
a list-returning lambda.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from typing import Any, Callable, Protocol


@dataclass(slots=True)
class BridgeEventRow:
    bridge_event_id: int
    event_family: str             # "observed" | "derived" | "action"
    event_type: str               # e.g. "kill", "item_use", "quest_completed"
    player_guid: int | None
    zone_id: int | None
    occurred_at_ts: int           # Unix-ish seconds or polling counter; opaque
    payload: dict[str, Any]
    object_entry: int | None = None
    subject_entry: int | None = None


class _RuntimeProtocol(Protocol):
    runner: Any  # has .module.character_guid
    def feed_use_item(self, *, item_entry: int) -> None: ...
    def feed_quest_completed(self, *, beat_ref: str, character_level: int = 1) -> None: ...
    def feed_kill(self, *, creature_family: str, zone: str, ts: int) -> None: ...


FetchFn = Callable[[int], list[BridgeEventRow]]


class BridgeEventPump:
    """Polls wm_bridge_event for the active character, dispatches to runtime."""

    def __init__(self, *, runtime: _RuntimeProtocol, fetch: FetchFn,
                 last_seen_event_id: int = 0) -> None:
        self.runtime = runtime
        self._fetch = fetch
        self.last_seen_event_id = last_seen_event_id

    def poll_once(self) -> int:
        rows = self._fetch(self.last_seen_event_id)
        for row in rows:
            self._dispatch(row)
            if row.bridge_event_id > self.last_seen_event_id:
                self.last_seen_event_id = row.bridge_event_id
        return len(rows)

    # --- internals -----------------------------------------------------

    def _dispatch(self, row: BridgeEventRow) -> None:
        active = self.runtime.runner.module.character_guid
        if row.player_guid is not None and row.player_guid != active:
            return  # scope: active_character only

        et = row.event_type
        try:
            if et == "item_use":
                item_entry = int(row.payload.get("item_entry", row.object_entry or 0))
                if item_entry:
                    self.runtime.feed_use_item(item_entry=item_entry)
            elif et == "quest_completed":
                beat_ref = str(row.payload.get("beat_ref", ""))
                level = int(row.payload.get("character_level", 1))
                if beat_ref:
                    self.runtime.feed_quest_completed(beat_ref=beat_ref, character_level=level)
            elif et == "kill":
                family = str(row.payload.get("creature_family", row.object_entry or ""))
                zone = str(row.zone_id) if row.zone_id is not None else str(row.payload.get("zone", ""))
                if family and zone:
                    self.runtime.feed_kill(creature_family=family, zone=zone,
                                           ts=int(row.occurred_at_ts))
            # other event types (talk/aura/weather/etc.) are out of slice scope
        except Exception:
            # catch-and-park principle: a malformed row must not crash the loop
            pass


def _row_from_csv(rec: dict[str, str]) -> BridgeEventRow:
    """Convert a mysql_cli CSV row into a BridgeEventRow."""
    def _int(v: str | None) -> int | None:
        if v is None or v == "" or v == "NULL": return None
        try: return int(v)
        except ValueError: return None
    payload_raw = rec.get("PayloadJSON") or ""
    try:
        payload = json.loads(payload_raw) if payload_raw and payload_raw != "NULL" else {}
    except json.JSONDecodeError:
        payload = {}
    return BridgeEventRow(
        bridge_event_id=int(rec["BridgeEventID"]),
        event_family=str(rec.get("EventFamily", "observed")),
        event_type=str(rec.get("EventType", "")),
        player_guid=_int(rec.get("PlayerGUID")),
        zone_id=_int(rec.get("ZoneID")),
        occurred_at_ts=int(rec.get("BridgeEventID", 0)),
        payload=payload,
        object_entry=_int(rec.get("ObjectEntry")),
        subject_entry=_int(rec.get("SubjectEntry")),
    )


def make_mysql_fetch(*, client, host: str, port: int, user: str, password: str,
                     database: str, character_guid: int) -> FetchFn:
    """Production fetch: queries wm_bridge_event via wm.db.mysql_cli."""
    def fetch(after_id: int) -> list[BridgeEventRow]:
        sql = (
            "SELECT BridgeEventID,EventFamily,EventType,PlayerGUID,ZoneID,"
            "PayloadJSON,ObjectEntry,SubjectEntry FROM wm_bridge_event "
            f"WHERE BridgeEventID > {int(after_id)} "
            f"AND PlayerGUID = {int(character_guid)} "
            "AND EventFamily = 'observed' "
            "ORDER BY BridgeEventID ASC LIMIT 100"
        )
        rows = client.query(host=host, port=port, user=user, password=password,
                            database=database, sql=sql)
        return [_row_from_csv(r) for r in rows]
    return fetch
