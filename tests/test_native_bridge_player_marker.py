import unittest

from wm.config import Settings
from wm.sources.native_bridge.player_marker import scan_recent_player_markers
from wm.sources.native_bridge.player_marker import scope_latest_player_marker


class _FakeClient:
    def __init__(self) -> None:
        self.sql_calls: list[str] = []
        self.scope_sql: list[str] = []

    def query(self, *, host, port, user, password, database, sql):  # type: ignore[no-untyped-def]
        del host, port, user, password
        self.sql_calls.append(sql)
        if "FROM wm_bridge_event" in sql:
            return [
                {
                    "BridgeEventID": "41",
                    "OccurredAt": "2026-04-30 12:00:00",
                    "PlayerGUID": "9001",
                    "AccountID": "77",
                    "SubjectEntry": "946602",
                    "MapID": "0",
                    "ZoneID": "12",
                    "AreaID": "40",
                    "PayloadJSON": '{"player_name":"Beaconchar","spell_id":946602,"aura_name":"WM Watcher Beacon"}',
                }
            ]
        if "FROM characters" in sql:
            if database != "acore_characters":
                raise AssertionError(f"Expected character DB, got {database}")
            return [{"guid": "9001", "name": "Beaconchar", "race": "1", "class": "5", "level": "12", "online": "1"}]
        if "INSERT INTO wm_bridge_player_scope" in sql:
            self.scope_sql.append(sql)
            return []
        raise AssertionError(f"Unexpected SQL: {sql}")


class NativeBridgePlayerMarkerTests(unittest.TestCase):
    def test_scan_recent_player_markers_uses_aura_spell_subject_and_attaches_character(self) -> None:
        client = _FakeClient()

        candidates = scan_recent_player_markers(
            client=client,  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world", char_db_name="acore_characters"),
            since_seconds=120,
            limit=5,
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.player_guid, 9001)
        self.assertEqual(candidate.character_name, "Beaconchar")
        self.assertEqual(candidate.spell_name, "WM Watcher Beacon")
        self.assertTrue(candidate.character_online)
        self.assertTrue(any("EventFamily = 'aura'" in sql for sql in client.sql_calls))
        self.assertTrue(any("SubjectEntry = 946602" in sql for sql in client.sql_calls))

    def test_scope_latest_player_marker_scopes_latest_candidate(self) -> None:
        client = _FakeClient()

        result = scope_latest_player_marker(
            client=client,  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world", char_db_name="acore_characters"),
            since_seconds=120,
            reason="test marker",
            expires_seconds=600,
        )

        self.assertTrue(result["scoped"])
        self.assertEqual(result["player_guid"], 9001)
        self.assertTrue(client.scope_sql)
        self.assertIn("PlayerGUID, Profile, Enabled, Reason, ExpiresAt", client.scope_sql[0])
        self.assertIn("9001", client.scope_sql[0])


if __name__ == "__main__":
    unittest.main()
