from __future__ import annotations

import unittest
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliError
from wm.journal.reader import SubjectJournalReader, load_subject_journal_for_creature
from wm.subjects.models import SubjectCard as ResolvedSubjectCard


class JournalReaderTests(unittest.TestCase):
    def test_missing_wm_tables_can_still_return_resolver_card(self) -> None:
        client = _FakeMysqlClient(existing_tables=set())
        resolved = _resolved_murloc_card()

        bundle = load_subject_journal_for_creature(
            client=client,  # type: ignore[arg-type]
            settings=Settings(),
            player_guid=42,
            creature_entry=46,
            resolved_subject_card=resolved,
        )

        self.assertEqual(bundle.status, "PARTIAL")
        self.assertIsNone(bundle.subject_id)
        self.assertIsNotNone(bundle.subject_card)
        assert bundle.subject_card is not None
        self.assertEqual(bundle.subject_card.subject_name, "Murloc Forager")
        self.assertIn("subject_resolver", bundle.source_flags)
        self.assertIsNotNone(bundle.counters)
        assert bundle.counters is not None
        self.assertEqual(bundle.counters.kill_count, 0)
        self.assertEqual(bundle.summary.title, "Murloc Forager" if bundle.summary else None)
        self.assertFalse(any("FROM wm_player_subject_journal" in query["sql"] for query in client.queries))

    def test_loads_definition_enrichment_counters_and_events(self) -> None:
        client = _FakeMysqlClient(
            existing_tables={
                "wm_subject_definition",
                "wm_subject_enrichment",
                "wm_player_subject_journal",
                "wm_player_subject_event",
            },
            rows={
                "definition": [
                    {
                        "SubjectID": "77",
                        "SubjectType": "creature",
                        "CreatureEntry": "46",
                        "JournalName": "Murloc Forager",
                        "Archetype": "shoreline pest",
                        "Species": "",
                        "Occupation": "",
                        "HomeArea": "",
                        "ShortDescription": "",
                        "TagsJSON": '["defined"]',
                    }
                ],
                "enrichment": [
                    {
                        "SubjectType": "creature",
                        "EntryID": "46",
                        "Species": "murloc",
                        "Profession": "forager",
                        "RoleLabel": "shore raider",
                        "HomeArea": "Elwynn coast",
                        "ShortDescription": "Shoreline scavenger with a territorial streak.",
                        "TagsJSON": '["enriched", "murloc"]',
                    }
                ],
                "journal": [
                    {
                        "PlayerGUID": "42",
                        "SubjectID": "77",
                        "KillCount": "7",
                        "SkinCount": "0",
                        "FeedCount": "1",
                        "TalkCount": "0",
                        "QuestCompleteCount": "1",
                        "LastQuestTitle": "A Curious Offering",
                    }
                ],
                "events": [
                    {"EventType": "note", "EventValue": "The murloc hesitated."},
                    {"EventType": "feed_trigger_quest", "EventValue": "A Curious Offering"},
                ],
            },
        )

        bundle = SubjectJournalReader(client=client, settings=Settings()).load_for_creature(
            player_guid=42,
            creature_entry=46,
            resolved_subject_card=_resolved_murloc_card(),
        )

        self.assertEqual(bundle.status, "WORKING")
        self.assertEqual(bundle.subject_id, 77)
        self.assertIsNotNone(bundle.subject_card)
        assert bundle.subject_card is not None
        self.assertEqual(bundle.subject_card.short_description, "Shoreline scavenger with a territorial streak.")
        self.assertEqual(bundle.subject_card.species, "murloc")
        self.assertEqual(bundle.subject_card.occupation, "forager")
        self.assertEqual(bundle.subject_card.home_area, "Elwynn coast")
        self.assertIn("defined", bundle.subject_card.tags)
        self.assertIn("enriched", bundle.subject_card.tags)
        self.assertIn("subject_resolver", bundle.source_flags)
        self.assertIn("player_subject_journal", bundle.source_flags)
        self.assertIn("player_subject_event", bundle.source_flags)
        self.assertIsNotNone(bundle.counters)
        assert bundle.counters is not None
        self.assertEqual(bundle.counters.kill_count, 7)
        self.assertEqual(len(bundle.events), 2)
        self.assertIsNotNone(bundle.summary)
        assert bundle.summary is not None
        self.assertIn('Player completed quest: "A Curious Offering"', bundle.summary.history_lines)
        self.assertIn("The murloc hesitated.", bundle.summary.history_lines)

    def test_missing_definition_without_resolver_remains_unknown(self) -> None:
        client = _FakeMysqlClient(existing_tables={"wm_subject_definition", "wm_subject_enrichment"})

        bundle = SubjectJournalReader(client=client, settings=Settings()).load_for_creature(
            player_guid=42,
            creature_entry=999999,
        )

        self.assertEqual(bundle.status, "UNKNOWN")
        self.assertIsNone(bundle.subject_card)
        self.assertIsNone(bundle.summary)

    def test_world_db_unavailable_degrades_to_resolver_fallback(self) -> None:
        client = _FakeMysqlClient(existing_tables=set(), fail_information_schema=True)

        bundle = SubjectJournalReader(client=client, settings=Settings()).load_for_creature(
            player_guid=42,
            creature_entry=46,
            resolved_subject_card=_resolved_murloc_card(),
        )

        self.assertEqual(bundle.status, "PARTIAL")
        self.assertIsNotNone(bundle.subject_card)
        self.assertEqual(bundle.source_flags, ["subject_resolver"])


def _resolved_murloc_card() -> ResolvedSubjectCard:
    return ResolvedSubjectCard(
        canonical_id="creature:46",
        kind="creature",
        display_name="Murloc Forager",
        entry=46,
        archetype="Murloc",
        creature_type="HUMANOID",
        role_tags=["wild_encounter"],
        group_keys=["creature:46", "name:murloc_forager"],
        area_tags=["elwynn"],
    )


class _FakeMysqlClient:
    def __init__(
        self,
        *,
        existing_tables: set[str],
        rows: dict[str, list[dict[str, Any]]] | None = None,
        fail_information_schema: bool = False,
    ) -> None:
        self.existing_tables = existing_tables
        self.rows = rows or {}
        self.fail_information_schema = fail_information_schema
        self.queries: list[dict[str, str]] = []

    def query(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        sql: str,
    ) -> list[dict[str, Any]]:
        del host, port, user, password
        self.queries.append({"database": database, "sql": sql})
        if database == "information_schema":
            if self.fail_information_schema:
                raise MysqlCliError("world db unavailable")
            table_name = _extract_table_name(sql)
            return [{"TABLE_NAME": table_name}] if table_name in self.existing_tables else []
        if "FROM wm_subject_definition" in sql:
            return list(self.rows.get("definition", []))
        if "FROM wm_subject_enrichment" in sql:
            return list(self.rows.get("enrichment", []))
        if "FROM wm_player_subject_journal" in sql:
            return list(self.rows.get("journal", []))
        if "FROM wm_player_subject_event" in sql:
            return list(self.rows.get("events", []))
        return []


def _extract_table_name(sql: str) -> str:
    marker = "AND TABLE_NAME = '"
    start = sql.index(marker) + len(marker)
    end = sql.index("'", start)
    return sql[start:end]


if __name__ == "__main__":
    unittest.main()
