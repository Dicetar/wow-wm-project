import unittest

from wm.config import Settings
from wm.events.adapters import DBPollingAdapter


class FakeStore:
    def get_cursor(self, *, adapter_name: str, cursor_key: str = "last_seen"):
        del adapter_name, cursor_key
        return None


class FakeClient:
    def __init__(self) -> None:
        self.sql_calls: list[str] = []

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password, database
        self.sql_calls.append(sql)
        return [
            {
                "EventID": "10",
                "PlayerGUID": "5406",
                "SubjectID": "2",
                "EventType": "kill",
                "EventValue": "1",
                "CreatedAt": "2026-04-08 12:00:00",
                "SubjectType": "creature",
                "CreatureEntry": "46",
                "JournalName": "Murloc Forager",
                "HomeArea": "Elwynn coastline",
            }
        ]


class DBPollingAdapterTests(unittest.TestCase):
    def test_poll_includes_optional_player_guid_filter(self) -> None:
        client = FakeClient()
        adapter = DBPollingAdapter(
            client=client,  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world"),
            store=FakeStore(),  # type: ignore[arg-type]
            player_guid_filter=5406,
        )

        events = adapter.poll()

        self.assertEqual(len(events), 1)
        self.assertIn("AND e.PlayerGUID = 5406", client.sql_calls[0])
        self.assertEqual(events[0].player_guid, 5406)


if __name__ == "__main__":
    unittest.main()
