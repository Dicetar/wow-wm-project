import unittest
from pathlib import Path

from wm.config import Settings
from wm.events.adapters import build_event_adapter
from wm.sources.native_bridge.action_kinds import native_action_kind_ids
from wm.sources.native_bridge.adapter import NativeBridgeAdapter
from wm.sources.native_bridge.adapter import _build_gossip_session_expired_events
from wm.sources.native_bridge.adapter import _record_to_event
from wm.sources.native_bridge.arm import arm_native_bridge_cursor
from wm.sources.native_bridge.configure import parse_bridge_runtime_config
from wm.sources.native_bridge.configure import parse_allowlist
from wm.sources.native_bridge.configure import set_allowlist
from wm.sources.native_bridge.models import NativeBridgeRecord
from wm.sources.native_bridge.scanner import NativeBridgeScanner


class _FakeClient:
    def __init__(self, rows=None, table_exists=True) -> None:
        self.rows = rows or []
        self.table_exists = table_exists
        self.sql_calls: list[str] = []

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password, database
        self.sql_calls.append(sql)
        if "SHOW TABLES LIKE 'wm_bridge_event'" in sql:
            return [{"Tables_in_acore_world (wm_bridge_event)": "wm_bridge_event"}] if self.table_exists else []
        if "FROM wm_event_log talk" in sql:
            return []
        if "MAX(BridgeEventID)" in sql:
            return list(self.rows)
        if "FROM wm_bridge_event" in sql:
            return list(self.rows)
        raise AssertionError(f"Unexpected SQL: {sql}")


class _CursorStore:
    def __init__(self, value: str | None = None) -> None:
        self.value = value

    def get_cursor(self, *, adapter_name: str, cursor_key: str = "last_seen"):
        del adapter_name, cursor_key
        if self.value is None:
            return None
        return type("Cursor", (), {"cursor_value": self.value})()

    def set_cursor(self, *, adapter_name: str, cursor_key: str = "last_seen", cursor_value: str) -> None:
        del adapter_name, cursor_key
        self.value = cursor_value


class NativeBridgeSourceTests(unittest.TestCase):
    def test_scanner_reports_missing_bridge_table(self) -> None:
        scanner = NativeBridgeScanner(
            client=_FakeClient(table_exists=False),  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world"),
        )

        result = scanner.scan(cursor_value="5", limit=10)

        self.assertFalse(result.table_exists)
        self.assertEqual(result.cursor.last_seen_id, 5)
        self.assertEqual(result.records, [])

    def test_scanner_parses_rows_and_reports_invalid_payload(self) -> None:
        scanner = NativeBridgeScanner(
            client=_FakeClient(
                rows=[
                    {
                        "BridgeEventID": "6",
                        "OccurredAt": "2026-04-09 12:00:00",
                        "EventFamily": "combat",
                        "EventType": "kill",
                        "Source": "native_bridge",
                        "PlayerGUID": "5406",
                        "AccountID": "132",
                        "SubjectType": "creature",
                        "SubjectGUID": "Creature-0-0-0-0-6-0000000001",
                        "SubjectEntry": "6",
                        "ObjectType": None,
                        "ObjectGUID": None,
                        "ObjectEntry": None,
                        "MapID": "0",
                        "ZoneID": "12",
                        "AreaID": "40",
                        "PayloadJSON": '{"player_name":"Jecia","subject_name":"Kobold Vermin"}',
                    },
                    {
                        "BridgeEventID": "7",
                        "OccurredAt": "2026-04-09 12:00:01",
                        "EventFamily": "quest",
                        "EventType": "completed",
                        "Source": "native_bridge",
                        "PlayerGUID": "5406",
                        "AccountID": "132",
                        "SubjectType": None,
                        "SubjectGUID": None,
                        "SubjectEntry": None,
                        "ObjectType": "quest",
                        "ObjectGUID": None,
                        "ObjectEntry": "910000",
                        "MapID": "0",
                        "ZoneID": "12",
                        "AreaID": "40",
                        "PayloadJSON": '{"broken"',
                    },
                ]
            ),  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world"),
        )

        result = scanner.scan(cursor_value="0", limit=10, player_guid=5406)

        self.assertTrue(result.table_exists)
        self.assertEqual(result.cursor.last_seen_id, 7)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].bridge_event_id, 6)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.failures[0].reason, "invalid_payload_json")

    def test_adapter_emits_canonical_slice_a_events(self) -> None:
        adapter = NativeBridgeAdapter(
            client=_FakeClient(
                rows=[
                    {
                        "BridgeEventID": "8",
                        "OccurredAt": "2026-04-09 12:00:00",
                        "EventFamily": "combat",
                        "EventType": "kill",
                        "Source": "native_bridge",
                        "PlayerGUID": "5406",
                        "AccountID": "132",
                        "SubjectType": "creature",
                        "SubjectGUID": "Creature-0-0-0-0-6-0000000001",
                        "SubjectEntry": "6",
                        "ObjectType": None,
                        "ObjectGUID": None,
                        "ObjectEntry": None,
                        "MapID": "0",
                        "ZoneID": "12",
                        "AreaID": "40",
                        "PayloadJSON": '{"player_name":"Jecia","subject_name":"Kobold Vermin"}',
                    },
                    {
                        "BridgeEventID": "9",
                        "OccurredAt": "2026-04-09 12:00:01",
                        "EventFamily": "gossip",
                        "EventType": "selected",
                        "Source": "native_bridge",
                        "PlayerGUID": "5406",
                        "AccountID": "132",
                        "SubjectType": "creature",
                        "SubjectGUID": "Creature-0-0-0-0-197-0000000001",
                        "SubjectEntry": "197",
                        "ObjectType": None,
                        "ObjectGUID": None,
                        "ObjectEntry": None,
                        "MapID": "0",
                        "ZoneID": "12",
                        "AreaID": "40",
                        "PayloadJSON": '{"subject_name":"Marshal McBride","action":1001}',
                    },
                    {
                        "BridgeEventID": "10",
                        "OccurredAt": "2026-04-09 12:00:02",
                        "EventFamily": "area",
                        "EventType": "entered",
                        "Source": "native_bridge",
                        "PlayerGUID": "5406",
                        "AccountID": "132",
                        "SubjectType": "area",
                        "SubjectGUID": None,
                        "SubjectEntry": "40",
                        "ObjectType": None,
                        "ObjectGUID": None,
                        "ObjectEntry": None,
                        "MapID": "0",
                        "ZoneID": "12",
                        "AreaID": "40",
                        "PayloadJSON": '{"area_name":"Northshire Valley"}',
                    },
                ]
            ),  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world", native_bridge_batch_size=20),
            store=_CursorStore("7"),  # type: ignore[arg-type]
            batch_size=20,
        )

        events = adapter.poll()

        self.assertEqual(len(events), 3)
        self.assertEqual([event.event_type for event in events], ["kill", "gossip_select", "enter_area"])
        self.assertTrue(all(event.source == "native_bridge" for event in events))
        self.assertEqual(adapter.last_cursor_value, "10")

    def test_mapping_keeps_future_slice_b_types_ready(self) -> None:
        spell_event = _record_to_event(
            NativeBridgeRecord(
                bridge_event_id=21,
                occurred_at="2026-04-09 12:00:03",
                event_family="spell",
                event_type="cast",
                source="native_bridge",
                player_guid=5406,
                subject_type="spell",
                subject_entry=686,
                payload={"spell_id": 686, "spell_name": "Shadow Bolt"},
            )
        )
        aura_event = _record_to_event(
            NativeBridgeRecord(
                bridge_event_id=22,
                occurred_at="2026-04-09 12:00:04",
                event_family="aura",
                event_type="applied",
                source="native_bridge",
                player_guid=5406,
                subject_type="spell",
                subject_entry=1243,
                payload={"aura_name": "Power Word: Fortitude"},
            )
        )

        self.assertIsNotNone(spell_event)
        self.assertIsNotNone(aura_event)
        assert spell_event is not None
        assert aura_event is not None
        self.assertEqual(spell_event.event_type, "spell_cast")
        self.assertEqual(aura_event.event_type, "aura_applied")

    def test_adapter_derives_gossip_session_expired_after_timeout(self) -> None:
        client = _FakeClient(
            rows=[
                {
                    "EventID": "100",
                    "SourceEventKey": "native_bridge:9",
                    "OccurredAt": "2026-04-09 12:00:00",
                    "ExpiredAt": "2026-04-09 12:00:45",
                    "PlayerGUID": "5406",
                    "SubjectType": "creature",
                    "SubjectEntry": "197",
                    "MapID": "0",
                    "ZoneID": "12",
                    "AreaID": "40",
                    "EventValue": "Marshal McBride",
                    "MetadataJSON": '{"payload":{"subject_name":"Marshal McBride"}}',
                }
            ]
        )

        def query(*, host, port, user, password, database, sql):  # type: ignore[no-untyped-def]
            del host, port, user, password, database
            client.sql_calls.append(sql)
            if "FROM wm_event_log talk" in sql:
                return list(client.rows)
            return []

        client.query = query  # type: ignore[method-assign]

        events = _build_gossip_session_expired_events(
            client=client,  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world", native_bridge_gossip_session_timeout_seconds=45),
            player_guid=5406,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "gossip_session_expired")
        self.assertEqual(events[0].source, "native_bridge_derived")
        self.assertEqual(events[0].source_event_key, "native_bridge:9:gossip_session_expired")
        self.assertTrue(any("gossip_select" in sql for sql in client.sql_calls))

    def test_build_event_adapter_supports_native_bridge(self) -> None:
        adapter = build_event_adapter(
            adapter_name="native_bridge",
            client=_FakeClient(),  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world", native_bridge_batch_size=55),
            store=_CursorStore(),  # type: ignore[arg-type]
        )

        self.assertIsInstance(adapter, NativeBridgeAdapter)
        self.assertEqual(adapter.batch_size, 55)

    def test_arm_native_bridge_cursor_uses_player_high_watermark(self) -> None:
        client = _FakeClient(rows=[{"LastSeenID": "44"}])
        store = _CursorStore("7")

        result = arm_native_bridge_cursor(
            client=client,  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world"),
            store=store,  # type: ignore[arg-type]
            player_guid=5406,
        )

        self.assertTrue(result.table_exists)
        self.assertEqual(result.previous_last_seen, 7)
        self.assertEqual(result.armed_last_seen, 44)
        self.assertEqual(store.value, "44")
        self.assertTrue(any("WHERE PlayerGUID = 5406" in sql for sql in client.sql_calls))

    def test_configure_updates_allowlist_without_touching_other_options(self) -> None:
        original = (
            "[worldserver]\n"
            "WmBridge.Enable = 1\n"
            'WmBridge.PlayerGuidAllowList = "111,222"\n'
            "WmBridge.Emit.Kill = 1\n"
        )

        updated = set_allowlist(original, [5406])

        self.assertEqual(parse_allowlist(original), [111, 222])
        self.assertEqual(parse_allowlist(updated), [5406])
        self.assertIn('WmBridge.PlayerGuidAllowList = "5406"', updated)
        self.assertIn("WmBridge.Emit.Kill = 1", updated)

    def test_configure_can_insert_or_clear_allowlist(self) -> None:
        text = set_allowlist("[worldserver]\n", [222, 111])
        self.assertEqual(parse_allowlist(text), [111, 222])

        cleared = set_allowlist(text, [])

        self.assertIn('WmBridge.PlayerGuidAllowList = ""', cleared)
        self.assertEqual(parse_allowlist(cleared), [])

    def test_bridge_runtime_config_snapshot_parses_flags_and_wildcard_allowlist(self) -> None:
        snapshot = parse_bridge_runtime_config(
            "\n".join(
                [
                    "[worldserver]",
                    "WmBridge.Enable = 1",
                    "WmBridge.ActionQueue.Enable = 1",
                    "WmBridge.DbControl.Enable = 0",
                    'WmBridge.PlayerGuidAllowList = "*"',
                    "",
                ]
            )
        )

        self.assertTrue(snapshot.enabled)
        self.assertTrue(snapshot.action_queue_enabled)
        self.assertFalse(snapshot.db_control_enabled)
        self.assertTrue(snapshot.allow_all_players)
        self.assertEqual(snapshot.player_guid_allowlist, [])
        self.assertTrue(snapshot.allows_player(5406))

    def test_native_module_has_action_queue_scaffold(self) -> None:
        root = Path("native_modules/mod-wm-bridge/src")
        expected_files = {
            "wm_bridge_action_queue.cpp",
            "wm_bridge_player_actions.cpp",
            "wm_bridge_inventory_actions.cpp",
            "wm_bridge_quest_actions.cpp",
            "wm_bridge_creature_actions.cpp",
            "wm_bridge_gossip_actions.cpp",
            "wm_bridge_companion_actions.cpp",
            "wm_bridge_environment_actions.cpp",
            "wm_bridge_debug_actions.cpp",
            "wm_bridge_unit_script.cpp",
        }

        self.assertTrue(expected_files.issubset({path.name for path in root.glob("*.cpp")}))

    def test_native_action_queue_avoids_generic_command_escape_hatches(self) -> None:
        source = Path("native_modules/mod-wm-bridge/src/wm_bridge_action_queue.cpp").read_text(encoding="utf-8")

        self.assertIn("wm_bridge_action_request", source)
        self.assertIn("debug_ping", source)
        self.assertIn("ClaimExpiresAt", source)
        self.assertIn("sequence_prior_failed", source)
        self.assertIn("ORDER BY req.Priority ASC", source)
        self.assertIn("quest_add", source)
        self.assertIn("AddQuestAndCheckCompletion", source)
        self.assertIn('MakePlayerScopedEvent(player, "quest", "granted")', source)
        self.assertIn("grant_source", source)
        self.assertIn("world_announce_to_player", source)
        self.assertNotIn("HandleCommand", source)
        self.assertNotIn("ChatHandler", source)

    def test_native_bridge_tracks_owned_summon_kills_beyond_pet_hooks(self) -> None:
        loader = Path("native_modules/mod-wm-bridge/src/mod_wm_bridge_loader.cpp").read_text(encoding="utf-8")
        source = Path("native_modules/mod-wm-bridge/src/wm_bridge_unit_script.cpp").read_text(encoding="utf-8")

        self.assertIn("AddSC_mod_wm_bridge_unit_script", loader)
        self.assertIn("UNITHOOK_ON_UNIT_DEATH", source)
        self.assertIn("GetCharmerOrOwnerPlayerOrPlayerItself()", source)
        self.assertIn('JsonAppendString(payload, firstField, "kill_source", "owned_unit")', source)
        self.assertIn("killer->ToPlayer()", source)
        self.assertIn("killer->IsPet()", source)
        self.assertIn("killer->IsTotem()", source)
        self.assertIn('MakePlayerScopedEvent(player, "combat", "kill")', source)

    def test_python_native_catalog_has_no_duplicate_ids(self) -> None:
        kinds = native_action_kind_ids()

        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertGreaterEqual(len(kinds), 80)


if __name__ == "__main__":
    unittest.main()
