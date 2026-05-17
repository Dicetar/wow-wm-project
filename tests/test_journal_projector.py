from __future__ import annotations

import unittest

from wm.config import Settings
from wm.journal.projector import JournalProjector, build_subject_journal_sql


class _FakeClient:
    def __init__(self, *, events, subject_rows_sequence):
        self._events = events
        self._subject_seq = list(subject_rows_sequence)
        self.executed: list[str] = []

    def query(self, *, host, port, user, password, database, sql):
        self.executed.append(sql)
        if "FROM wm_event_log WHERE ProjectedAt IS NULL" in sql:
            return self._events
        if "FROM wm_subject_definition" in sql:
            return self._subject_seq.pop(0) if self._subject_seq else []
        return []


def _settings() -> Settings:
    return Settings()


def _kill_event(eid: int, entry: int = 46, zone: int = 40) -> dict:
    return {
        "EventID": eid,
        "EventType": "kill",
        "PlayerGUID": 5406,
        "SubjectType": "creature",
        "SubjectEntry": entry,
        "ZoneID": zone,
        "EventValue": None,
    }


class JournalProjectorTests(unittest.TestCase):
    def test_dry_run_emits_sql_without_writes(self) -> None:
        client = _FakeClient(events=[_kill_event(1)], subject_rows_sequence=[[{"SubjectID": "7"}]])
        r = JournalProjector(client=client, settings=_settings()).project_unprojected(mode="dry-run")
        self.assertEqual(r.considered, 1)
        self.assertEqual(r.projected, 1)
        joined = "\n".join(r.statements)
        self.assertIn("wm_player_subject_journal", joined)
        self.assertIn("wm_player_subject_event", joined)
        self.assertIn("wm_player_zone_stats", joined)
        self.assertIn("UPDATE wm_event_log SET ProjectedAt", joined)
        # dry-run: only SELECTs were actually executed, no INSERT/UPDATE.
        self.assertFalse(any(s.startswith(("INSERT", "UPDATE")) for s in client.executed))

    def test_apply_executes_writes(self) -> None:
        client = _FakeClient(
            events=[_kill_event(1)],
            subject_rows_sequence=[[{"SubjectID": "7"}]],
        )
        r = JournalProjector(client=client, settings=_settings()).project_unprojected(mode="apply")
        self.assertEqual(r.projected, 1)
        self.assertTrue(any(s.startswith("INSERT INTO wm_player_subject_journal") for s in client.executed))
        self.assertTrue(any(s.startswith("UPDATE wm_event_log SET ProjectedAt") for s in client.executed))

    def test_unmapped_event_type_is_skipped_but_marked(self) -> None:
        ev = _kill_event(2)
        ev["EventType"] = "loot_item"
        client = _FakeClient(events=[ev], subject_rows_sequence=[])
        r = JournalProjector(client=client, settings=_settings()).project_unprojected(mode="apply")
        self.assertEqual(r.skipped, 1)
        self.assertEqual(r.projected, 0)
        self.assertTrue(any("SET ProjectedAt" in s for s in client.executed))
        self.assertFalse(any("wm_player_subject_journal" in s for s in client.executed))

    def test_missing_subject_is_materialized(self) -> None:
        client = _FakeClient(
            events=[_kill_event(3)],
            subject_rows_sequence=[[], [{"SubjectID": "12"}]],  # not found, then found after materialize
        )
        r = JournalProjector(client=client, settings=_settings()).project_unprojected(mode="apply")
        self.assertEqual(r.materialized_subjects, 1)
        self.assertTrue(any("INSERT INTO wm_subject_definition" in s for s in client.executed))

    def test_idempotency_query_filters_projected(self) -> None:
        client = _FakeClient(events=[], subject_rows_sequence=[])
        JournalProjector(client=client, settings=_settings()).project_unprojected(mode="dry-run")
        self.assertTrue(any("ProjectedAt IS NULL" in s for s in client.executed))

    def test_counter_sql_is_additive_upsert(self) -> None:
        sql = build_subject_journal_sql(player_guid=5406, subject_id=7, counter_col="KillCount")
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        self.assertIn("KillCount = KillCount + 1", sql)

    def test_bad_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            JournalProjector(client=_FakeClient(events=[], subject_rows_sequence=[]), settings=_settings()).project_unprojected(mode="x")


if __name__ == "__main__":
    unittest.main()
