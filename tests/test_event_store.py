import json
import re
import unittest

from wm.config import Settings
from wm.events.models import WMEvent
from wm.events.store import EventStore


class _DummyClient:
    mysql_bin_path = "mysql"


class MemoryEventStore(EventStore):
    def __init__(self) -> None:
        super().__init__(client=_DummyClient(), settings=Settings(world_db_name="acore_world"))
        self._events: dict[tuple[str, str], dict[str, object]] = {}
        self._cursors: dict[tuple[str, str], str] = {}
        self._event_auto_id = 1

    def _query_world(self, sql: str):
        if "SELECT EventID FROM wm_event_log" in sql and "Source =" in sql:
            source = _extract_single_quoted(sql, "Source = ")
            source_event_key = _extract_single_quoted(sql, "SourceEventKey = ")
            row = self._events.get((source, source_event_key))
            if row is None:
                return []
            return [{"EventID": row["EventID"]}]

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


def _extract_single_quoted(sql: str, marker: str) -> str:
    start = sql.index(marker) + len(marker)
    quoted = sql[start:]
    match = re.match(r"'([^']*)'", quoted)
    if match is None:
        raise AssertionError(f"Could not extract quoted marker {marker} from SQL: {sql}")
    return match.group(1)


if __name__ == "__main__":
    unittest.main()
