import os
from pathlib import Path
import unittest

from wm.config import Settings
from wm.reactive.models import ReactiveQuestRule
from wm.refs import CreatureRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.refs import NpcRef
from wm.sources.combat_log import CombatLogCursor
from wm.sources.combat_log import CombatLogParser
from wm.sources.combat_log import CombatLogResolver
from wm.sources.combat_log import CombatLogTailAdapter
from wm.sources.combat_log import CombatLogTailer


_PARTY_KILL_LINE = (
    '4/8 16:20:01.123  PARTY_KILL,0x000000000000152E,"Jecia",0x511,'
    '0xF1300000060000AB,"Kobold Vermin",0xa48'
)
_OTHER_LINE = (
    '4/8 16:20:02.000  SWING_DAMAGE,0x000000000000152E,"Jecia",0x511,'
    '0xF1300000060000AB,"Kobold Vermin",0xa48,12,-1,1,0,0,0,nil,nil,nil'
)


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


class CombatLogSourceTests(unittest.TestCase):
    def _workspace_path(self, name: str) -> Path:
        artifacts_dir = Path(os.getcwd()) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / name
        if path.exists():
            path.unlink()
        return path

    def test_parser_extracts_party_kill_record(self) -> None:
        record = CombatLogParser().parse_line(raw_line=_PARTY_KILL_LINE, byte_offset=128)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.event_name, "PARTY_KILL")
        self.assertEqual(record.source_actor.name, "Jecia")
        self.assertEqual(record.dest_actor.name, "Kobold Vermin")
        self.assertEqual(record.byte_offset, 128)

    def test_parser_ignores_unparseable_lines(self) -> None:
        self.assertIsNone(CombatLogParser().parse_line(raw_line="not a combat log line", byte_offset=0))

    def test_tailer_reads_incrementally_and_resets_after_truncate(self) -> None:
        path = self._workspace_path("combat_log_source_tailer.txt")
        try:
            path.write_text(_PARTY_KILL_LINE + "\n" + _OTHER_LINE + "\n", encoding="utf-8")

            tailer = CombatLogTailer(path=path)
            first = tailer.read(cursor=None, max_lines=20)
            self.assertEqual(len(first.lines), 2)

            path.write_text(
                _PARTY_KILL_LINE + "\n" + _OTHER_LINE + "\n" + _PARTY_KILL_LINE + "\n",
                encoding="utf-8",
            )
            second = tailer.read(cursor=first.cursor, max_lines=20)
            self.assertEqual(len(second.lines), 1)

            path.write_text(_PARTY_KILL_LINE + "\n", encoding="utf-8")
            third = tailer.read(cursor=second.cursor, max_lines=20)
            self.assertEqual(len(third.lines), 1)
            self.assertEqual(third.lines[0].byte_offset, 0)
        finally:
            if path.exists():
                path.unlink()

    def test_resolver_prefers_rule_hint_and_falls_back_to_exact_name(self) -> None:
        settings = Settings()
        reactive_store = _ReactiveStore()
        rule_hint_resolver = CombatLogResolver(
            client=_ResolverClient(),
            settings=settings,
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )
        record = CombatLogParser().parse_line(raw_line=_PARTY_KILL_LINE, byte_offset=10)
        assert record is not None

        signal, failure = rule_hint_resolver.resolve_kill(
            record=record,
            player_guid=5406,
            log_path="D:/fake/WoWCombatLog.txt",
            fingerprint="fpr",
        )

        self.assertIsNone(failure)
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.player_ref.guid, 5406)
        self.assertEqual(signal.subject_ref.entry, 6)
        self.assertEqual(signal.resolution_source, "rule_hint")

        fallback_resolver = CombatLogResolver(
            client=_ResolverClient(
                rows={
                    "FROM `creature_template` WHERE `name` = 'Kobold Vermin'": [
                        {"entry": "6", "name": "Kobold Vermin"}
                    ]
                }
            ),
            settings=settings,
            reactive_store=type(
                "EmptyReactiveStore",
                (),
                {
                    "fetch_character_name": staticmethod(lambda player_guid: "Jecia"),
                    "list_active_rules": staticmethod(lambda **kwargs: []),
                },
            )(),  # type: ignore[arg-type]
        )
        signal, failure = fallback_resolver.resolve_kill(
            record=record,
            player_guid=5406,
            log_path="D:/fake/WoWCombatLog.txt",
            fingerprint="fpr",
        )
        self.assertIsNone(failure)
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.resolution_source, "creature_exact_name")

    def test_adapter_emits_canonical_kill_events(self) -> None:
        path = self._workspace_path("combat_log_source_adapter.txt")
        try:
            path.write_text(_PARTY_KILL_LINE + "\n" + _OTHER_LINE + "\n" + _PARTY_KILL_LINE + "\n", encoding="utf-8")
            adapter = CombatLogTailAdapter(
                client=_ResolverClient(),
                settings=Settings(combat_log_path=str(path), combat_log_batch_size=20),
                store=_AdapterStore(),  # type: ignore[arg-type]
                reactive_store=_ReactiveStore(),  # type: ignore[arg-type]
                batch_size=20,
                player_guid_filter=5406,
            )

            events = adapter.poll()

            self.assertEqual(len(events), 2)
            self.assertEqual({event.source for event in events}, {"combat_log"})
            self.assertEqual({event.event_type for event in events}, {"kill"})
            self.assertEqual({event.player_guid for event in events}, {5406})
            self.assertEqual({event.subject_entry for event in events}, {6})
            self.assertTrue(all(event.source_event_key.startswith(adapter.last_scan_result.cursor.fingerprint) for event in events))
        finally:
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    unittest.main()
