import os
from pathlib import Path
import unittest

from wm.config import Settings
from wm.reactive.models import ReactiveQuestRule
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.sources.addon_log import AddonLogParser
from wm.sources.addon_log import AddonLogResolver
from wm.sources.addon_log import AddonLogTailAdapter
from wm.sources.addon_log import AddonLogTailer


_HELLO_LINE = (
    '2026-04-08T20:01:01Z [Addon] incoming payload WMB1|type=HELLO|player=Jecia|'
    'player_guid=5406|channel=WMBridgePrivate|ts=1712600000123'
)
_KILL_LINE = (
    '2026-04-08T20:01:02Z [Addon] incoming payload WMB1|type=KILL|player=Jecia|'
    'player_guid=5406|target=Kobold Vermin|target_guid=Creature-0-0-0-0-6-0000000001|'
    'subevent=PARTY_KILL|ts=1712600001123'
)
_OTHER_LINE = "2026-04-08T20:01:03Z [Server] normal line without addon bridge payload"


class _ResolverClient:
    def __init__(self, rows=None) -> None:
        self.rows = rows or {}

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password, database
        for marker, value in self.rows.items():
            if marker in sql:
                return value
        return []


class _ReactiveStore:
    def __init__(self) -> None:
        self.rules = [
            ReactiveQuestRule(
                rule_key="reactive_bounty:kobold_vermin",
                is_active=True,
                player_guid_scope=5406,
                subject_type="creature",
                subject_entry=6,
                trigger_event_type="kill",
                kill_threshold=4,
                window_seconds=120,
                quest_id=910000,
                turn_in_npc_entry=197,
                grant_mode="direct_quest_add",
                post_reward_cooldown_seconds=60,
                metadata={},
                notes=[],
                player_scope=PlayerRef(guid=5406, name="Jecia"),
                subject=CreatureRef(entry=6, name="Kobold Vermin"),
                quest=QuestRef(id=910000, title="Bounty: Kobold Vermin"),
                turn_in_npc=NpcRef(entry=197, name="Marshal McBride"),
            )
        ]

    def fetch_character_name(self, *, player_guid: int) -> str | None:
        return "Jecia" if player_guid == 5406 else None

    def list_active_rules(self, *, subject_type=None, subject_entry=None, trigger_event_type=None, player_guid=None):
        del subject_type, subject_entry, trigger_event_type, player_guid
        return list(self.rules)


class _AdapterStore:
    def __init__(self, cursor_value: str | None = None) -> None:
        self.cursor_value = cursor_value

    def get_cursor(self, *, adapter_name: str, cursor_key: str = "state"):
        del adapter_name, cursor_key
        if self.cursor_value is None:
            return None
        return type("Cursor", (), {"cursor_value": self.cursor_value})()


class AddonLogSourceTests(unittest.TestCase):
    def _workspace_path(self, name: str) -> Path:
        artifacts_dir = Path(os.getcwd()) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / name
        if path.exists():
            path.unlink()
        return path

    def test_parser_extracts_marker_inside_noisy_log_line(self) -> None:
        record = AddonLogParser().parse_line(raw_line=_KILL_LINE, byte_offset=64)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.event_type, "KILL")
        self.assertEqual(record.payload_fields["player"], "Jecia")
        self.assertEqual(record.payload_fields["target"], "Kobold Vermin")
        self.assertEqual(record.byte_offset, 64)

    def test_parser_ignores_non_bridge_lines(self) -> None:
        self.assertIsNone(AddonLogParser().parse_line(raw_line=_OTHER_LINE, byte_offset=0))
        self.assertIsNone(
            AddonLogParser().parse_line(raw_line="WMB1|player=Jecia|player_guid=5406", byte_offset=0)
        )

    def test_tailer_reads_incrementally_and_resets_after_truncate(self) -> None:
        path = self._workspace_path("addon_log_source_tailer.txt")
        try:
            path.write_text(_HELLO_LINE + "\n" + _KILL_LINE + "\n", encoding="utf-8")

            tailer = AddonLogTailer(path=path)
            first = tailer.read(cursor=None, max_lines=20)
            self.assertEqual(len(first.lines), 2)

            path.write_text(_HELLO_LINE + "\n" + _KILL_LINE + "\n" + _KILL_LINE + "\n", encoding="utf-8")
            second = tailer.read(cursor=first.cursor, max_lines=20)
            self.assertEqual(len(second.lines), 1)

            path.write_text(_HELLO_LINE + "\n", encoding="utf-8")
            third = tailer.read(cursor=second.cursor, max_lines=20)
            self.assertEqual(len(third.lines), 1)
            self.assertEqual(third.lines[0].byte_offset, 0)
        finally:
            if path.exists():
                path.unlink()

    def test_resolver_prefers_rule_hint_and_supports_hello(self) -> None:
        resolver = AddonLogResolver(
            client=_ResolverClient(),
            settings=Settings(),
            reactive_store=_ReactiveStore(),  # type: ignore[arg-type]
        )
        hello_record = AddonLogParser().parse_line(raw_line=_HELLO_LINE, byte_offset=10)
        kill_record = AddonLogParser().parse_line(raw_line=_KILL_LINE, byte_offset=20)
        assert hello_record is not None
        assert kill_record is not None

        hello_signal, hello_failure = resolver.resolve(
            record=hello_record,
            player_guid=5406,
            log_path="D:/fake/WMOps.log",
            fingerprint="fpr",
        )
        self.assertIsNone(hello_failure)
        self.assertIsNotNone(hello_signal)
        assert hello_signal is not None
        self.assertEqual(hello_signal.event_type, "hello")
        self.assertEqual(hello_signal.player_ref.guid, 5406)

        kill_signal, kill_failure = resolver.resolve(
            record=kill_record,
            player_guid=5406,
            log_path="D:/fake/WMOps.log",
            fingerprint="fpr",
        )
        self.assertIsNone(kill_failure)
        self.assertIsNotNone(kill_signal)
        assert kill_signal is not None
        self.assertEqual(kill_signal.subject_ref.entry, 6)
        self.assertEqual(kill_signal.resolution_source, "payload_guid+rule_hint")

    def test_resolver_falls_back_to_exact_creature_name(self) -> None:
        resolver = AddonLogResolver(
            client=_ResolverClient(
                rows={
                    "FROM `creature_template` WHERE `name` = 'Kobold Vermin'": [
                        {"entry": "6", "name": "Kobold Vermin"}
                    ]
                }
            ),
            settings=Settings(),
            reactive_store=type(
                "EmptyReactiveStore",
                (),
                {
                    "fetch_character_name": staticmethod(lambda player_guid: "Jecia"),
                    "list_active_rules": staticmethod(lambda **kwargs: []),
                },
            )(),  # type: ignore[arg-type]
        )
        kill_signal, kill_failure = resolver.resolve(
            record=AddonLogParser().parse_line(raw_line=_KILL_LINE, byte_offset=30),
            player_guid=5406,
            log_path="D:/fake/WMOps.log",
            fingerprint="fpr",
        )

        self.assertIsNone(kill_failure)
        self.assertIsNotNone(kill_signal)
        assert kill_signal is not None
        self.assertEqual(kill_signal.subject_ref.entry, 6)
        self.assertEqual(kill_signal.resolution_source, "payload_guid+creature_exact_name")

    def test_adapter_emits_canonical_kill_events_only(self) -> None:
        path = self._workspace_path("addon_log_source_adapter.txt")
        try:
            path.write_text(_HELLO_LINE + "\n" + _KILL_LINE + "\n" + _OTHER_LINE + "\n" + _KILL_LINE + "\n", encoding="utf-8")
            adapter = AddonLogTailAdapter(
                client=_ResolverClient(),
                settings=Settings(addon_log_path=str(path), addon_log_batch_size=20),
                store=_AdapterStore(),  # type: ignore[arg-type]
                reactive_store=_ReactiveStore(),  # type: ignore[arg-type]
                batch_size=20,
                player_guid_filter=5406,
            )

            events = adapter.poll()

            self.assertEqual(len(events), 2)
            self.assertEqual({event.source for event in events}, {"addon_log"})
            self.assertEqual({event.event_type for event in events}, {"kill"})
            self.assertEqual({event.player_guid for event in events}, {5406})
            self.assertEqual({event.subject_entry for event in events}, {6})
            self.assertEqual(len(adapter.last_scan_result.signals), 3)
            self.assertTrue(all(event.source_event_key.startswith(adapter.last_scan_result.cursor.fingerprint) for event in events))
        finally:
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    unittest.main()
