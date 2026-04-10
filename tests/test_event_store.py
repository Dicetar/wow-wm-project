import json
import re
import unittest

from wm.config import Settings
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.events.store import _sql_datetime_or_expression


class _DummyClient:
    mysql_bin_path = "mysql"


class MemoryEventStore(EventStore):
    def __init__(self) -> None:
        super().__init__(client=_DummyClient(), settings=Settings(world_db_name="acore_world"))
        self._events: dict[tuple[str, str], dict[str, object]] = {}
        self._cursors: dict[tuple[str, str], str] = {}
        self._reaction_logs: list[dict[str, object]] = []
        self._cooldowns: list[dict[str, object]] = []
        self._event_auto_id = 1

    def _query_world(self, sql: str):
        if "SELECT EventID FROM wm_event_log" in sql and "Source =" in sql:
            source = _extract_single_quoted(sql, "Source = ")
            source_event_key = _extract_single_quoted(sql, "SourceEventKey = ")
            row = self._events.get((source, source_event_key))
            if row is None:
                return []
            return [{"EventID": row["EventID"]}]

        if "FROM wm_event_log" in sql and "WHERE EventID =" in sql:
            event_id = int(_extract_int(sql, "WHERE EventID = "))
            rows = [row for row in self._events.values() if row["EventID"] == event_id]
            return rows[:1]

        if "FROM wm_event_log" in sql and "Source =" in sql and "SourceEventKey =" in sql and "LIMIT 1" in sql:
            source = _extract_single_quoted(sql, "Source = ")
            source_event_key = _extract_single_quoted(sql, "SourceEventKey = ")
            row = self._events.get((source, source_event_key))
            return [row] if row is not None else []

        if "FROM wm_event_cursor" in sql:
            adapter_name = _extract_single_quoted(sql, "AdapterName = ")
            cursor_key = _extract_single_quoted(sql, "CursorKey = ")
            cursor_value = self._cursors.get((adapter_name, cursor_key))
            if cursor_value is None:
                return []
            return [
                {
                    "AdapterName": adapter_name,
                    "CursorKey": cursor_key,
                    "CursorValue": cursor_value,
                }
            ]

        if "FROM wm_event_log" in sql and "ORDER BY EventID" in sql:
            rows = list(self._events.values())
            if "EventClass = " in sql:
                event_class = _extract_single_quoted(sql, "EventClass = ")
                rows = [row for row in rows if row["EventClass"] == event_class]
            if "PlayerGUID = " in sql:
                player_guid = int(_extract_int(sql, "PlayerGUID = "))
                rows = [row for row in rows if row["PlayerGUID"] == player_guid]
            if "SubjectType = " in sql:
                subject_type = _extract_single_quoted(sql, "SubjectType = ")
                rows = [row for row in rows if row["SubjectType"] == subject_type]
            if "SubjectEntry = " in sql:
                subject_entry = int(_extract_int(sql, "SubjectEntry = "))
                rows = [row for row in rows if row["SubjectEntry"] == subject_entry]
            if "EventType = " in sql:
                event_type = _extract_single_quoted(sql, "EventType = ")
                rows = [row for row in rows if row["EventType"] == event_type]
            reverse = "ORDER BY EventID DESC" in sql
            rows.sort(key=lambda row: int(row["EventID"]), reverse=reverse)
            return rows

        if "FROM wm_reaction_log" in sql:
            rows = list(self._reaction_logs)
            if "PlayerGUID = " in sql:
                player_guid = int(_extract_int(sql, "PlayerGUID = "))
                rows = [row for row in rows if row["PlayerGUID"] == player_guid]
            if "Status = " in sql:
                status = _extract_single_quoted(sql, "Status = ")
                rows = [row for row in rows if row["Status"] == status]
            rows.sort(key=lambda row: int(row["ReactionID"]), reverse=True)
            return rows

        if "FROM wm_reaction_cooldown" in sql:
            rows = list(self._cooldowns)
            if "PlayerGUID = " in sql:
                player_guid = int(_extract_int(sql, "PlayerGUID = "))
                rows = [row for row in rows if row["PlayerGUID"] == player_guid]
            return rows

        raise AssertionError(f"Unexpected SQL: {sql}")

    def _execute_world(self, sql: str) -> None:
        if sql.startswith("INSERT INTO wm_event_log"):
            values = re.search(
                r"VALUES \('([^']*)', '([^']*)', '([^']*)', '([^']*)', '([^']*)', (\d+|NULL), ('[^']*'|NULL), (\d+|NULL), (\d+|NULL), (\d+|NULL), (\d+|NULL), ('[^']*'|NULL), '(.+)'\)$",
                sql,
            )
            if values is None:
                raise AssertionError(f"Could not parse wm_event_log insert: {sql}")
            source = values.group(3)
            source_event_key = values.group(4)
            self._events[(source, source_event_key)] = {
                "EventID": self._event_auto_id,
                "EventClass": values.group(1),
                "EventType": values.group(2),
                "Source": source,
                "SourceEventKey": source_event_key,
                "OccurredAt": values.group(5),
                "PlayerGUID": int(values.group(6)) if values.group(6) != "NULL" else None,
                "SubjectType": values.group(7).strip("'") if values.group(7) != "NULL" else None,
                "SubjectEntry": int(values.group(8)) if values.group(8) != "NULL" else None,
                "MapID": int(values.group(9)) if values.group(9) != "NULL" else None,
                "ZoneID": int(values.group(10)) if values.group(10) != "NULL" else None,
                "AreaID": int(values.group(11)) if values.group(11) != "NULL" else None,
                "EventValue": values.group(12).strip("'") if values.group(12) != "NULL" else None,
                "MetadataJSON": json.dumps({"parsed": True}),
            }
            self._event_auto_id += 1
            return

        if sql.startswith("INSERT INTO wm_event_cursor"):
            values = re.search(r"VALUES \('([^']*)', '([^']*)', '([^']*)'\)", sql)
            if values is None:
                raise AssertionError(f"Could not parse wm_event_cursor insert: {sql}")
            self._cursors[(values.group(1), values.group(2))] = values.group(3)
            return

        raise AssertionError(f"Unexpected execute SQL: {sql}")


class EventStoreTests(unittest.TestCase):
    def test_sql_datetime_expression_normalizes_iso_strings(self) -> None:
        self.assertEqual(_sql_datetime_or_expression("2026-04-08T14:03:40Z"), "'2026-04-08 14:03:40'")
        self.assertEqual(_sql_datetime_or_expression("2026-04-08T14:03:40.123Z"), "'2026-04-08 14:03:40'")

    def test_record_dedupes_duplicate_source_event(self) -> None:
        store = MemoryEventStore()
        event = WMEvent(
            event_class="observed",
            event_type="kill",
            source="db_poll",
            source_event_key="1001",
            occurred_at="2026-04-08 12:00:00",
            player_guid=1,
            subject_type="creature",
            subject_entry=46,
        )

        first = store.record([event])
        second = store.record([event])

        self.assertEqual(len(first.recorded), 1)
        self.assertEqual(len(second.skipped), 1)
        self.assertIsNotNone(event.event_id)

    def test_cursor_round_trip(self) -> None:
        store = MemoryEventStore()
        store.set_cursor(adapter_name="db_poll", cursor_value="15")
        cursor = store.get_cursor(adapter_name="db_poll")

        self.assertIsNotNone(cursor)
        self.assertEqual(cursor.cursor_value, "15")

    def test_get_event_by_id_and_source_key(self) -> None:
        store = MemoryEventStore()
        event = WMEvent(
            event_class="observed",
            event_type="kill",
            source="native_bridge",
            source_event_key="native_bridge:44",
            occurred_at="2026-04-08 12:00:00",
            player_guid=5406,
            subject_type="creature",
            subject_entry=6,
        )
        store.record([event])

        by_id = store.get_event(event_id=event.event_id or 0)
        by_key = store.get_event_by_source_key(source="native_bridge", source_event_key="native_bridge:44")

        self.assertIsNotNone(by_id)
        self.assertIsNotNone(by_key)
        self.assertEqual(by_id.event_type, "kill")
        self.assertEqual(by_key.player_guid, 5406)

    def test_list_recent_events_filters_by_class_and_player(self) -> None:
        store = MemoryEventStore()
        store.record(
            [
                WMEvent(
                    event_class="observed",
                    event_type="kill",
                    source="db_poll",
                    source_event_key="1001",
                    occurred_at="2026-04-08 12:00:00",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=6,
                ),
                WMEvent(
                    event_class="derived",
                    event_type="repeat_hunt_detected",
                    source="wm.rules",
                    source_event_key="derived-1",
                    occurred_at="2026-04-08 12:01:00",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=6,
                ),
            ]
        )

        rows = store.list_recent_events(event_class="observed", player_guid=5406, limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event_type, "kill")

    def test_list_recent_reaction_logs_parses_rows(self) -> None:
        store = MemoryEventStore()
        store._reaction_logs.append(
            {
                "ReactionID": 5,
                "ReactionKey": "repeat_hunt_followup:5406:creature:6",
                "RuleType": "repeat_hunt_followup",
                "Status": "dry-run",
                "PlayerGUID": 5406,
                "SubjectType": "creature",
                "SubjectEntry": 6,
                "PlannedActionsJSON": json.dumps({"plan_key": "repeat_hunt_followup:5406:creature:6"}),
                "ResultJSON": json.dumps({"status": "dry-run"}),
                "CreatedAt": "2026-04-08 10:00:00",
            }
        )

        rows = store.list_recent_reaction_logs(player_guid=5406, limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "dry-run")
        self.assertEqual(rows[0].subject.subject_entry, 6)

    def test_list_active_cooldowns_parses_rows(self) -> None:
        store = MemoryEventStore()
        store._cooldowns.append(
            {
                "ReactionKey": "repeat_hunt_followup:5406:creature:6",
                "RuleType": "repeat_hunt_followup",
                "PlayerGUID": 5406,
                "SubjectType": "creature",
                "SubjectEntry": 6,
                "CooldownUntil": "2026-04-08 11:00:00",
                "LastTriggeredAt": "2026-04-08 10:00:00",
                "MetadataJSON": json.dumps({"plan_key": "repeat_hunt_followup:5406:creature:6"}),
            }
        )

        rows = store.list_active_cooldowns(player_guid=5406, limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].rule_type, "repeat_hunt_followup")
        self.assertEqual(rows[0].metadata["plan_key"], "repeat_hunt_followup:5406:creature:6")

    def test_list_subject_events_filters_by_subject_and_type(self) -> None:
        store = MemoryEventStore()
        store.record(
            [
                WMEvent(
                    event_class="observed",
                    event_type="kill",
                    source="db_poll",
                    source_event_key="kill-1",
                    occurred_at="2026-04-08 12:00:00",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=6,
                ),
                WMEvent(
                    event_class="observed",
                    event_type="talk",
                    source="db_poll",
                    source_event_key="talk-1",
                    occurred_at="2026-04-08 12:00:05",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=197,
                ),
            ]
        )

        rows = store.list_subject_events(
            player_guid=5406,
            subject_type="creature",
            subject_entry=6,
            event_type="kill",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source_event_key, "kill-1")

    def test_non_creature_subject_lookup_short_circuits(self) -> None:
        store = MemoryEventStore()

        self.assertIsNone(store.resolve_subject_id(subject_type="area", subject_entry=40))


def _extract_single_quoted(sql: str, marker: str) -> str:
    start = sql.index(marker) + len(marker)
    quoted = sql[start:]
    match = re.match(r"'([^']*)'", quoted)
    if match is None:
        raise AssertionError(f"Could not extract quoted marker {marker} from SQL: {sql}")
    return match.group(1)


def _extract_int(sql: str, marker: str) -> str:
    start = sql.index(marker) + len(marker)
    digits = sql[start:]
    match = re.match(r"(\d+)", digits)
    if match is None:
        raise AssertionError(f"Could not extract integer marker {marker} from SQL: {sql}")
    return match.group(1)


if __name__ == "__main__":
    unittest.main()
