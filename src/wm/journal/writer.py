from __future__ import annotations

import json
from typing import Any


class JournalWriter:
    def __init__(self, db_client: Any):
        self._db = db_client

    def increment_counter(self, player_guid: int, subject_entry: int,
                          counter_key: str, delta: int = 1) -> None:
        self._db.execute(
            """
            INSERT INTO wm_journal_counter
                (player_guid, subject_entry, counter_key, count, last_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                count = count + VALUES(count),
                last_at = NOW()
            """,
            (player_guid, subject_entry, counter_key, delta),
        )

    def get_counter(self, player_guid: int, subject_entry: int,
                    counter_key: str) -> int:
        rows = self._db.query(
            "SELECT count FROM wm_journal_counter "
            "WHERE player_guid = %s AND subject_entry = %s AND counter_key = %s",
            (player_guid, subject_entry, counter_key),
        )
        if rows:
            return int(rows[0].get("count", 0))
        return 0

    def record_special_event(self, player_guid: int, event_type: str,
                             subject_entry: int | None = None,
                             narrative_key: str | None = None,
                             data: dict | None = None) -> int:
        data_json = json.dumps(data) if data else None
        result = self._db.execute(
            """
            INSERT INTO wm_journal_special_event
                (player_guid, subject_entry, event_type, narrative_key, data_json)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (player_guid, subject_entry, event_type, narrative_key, data_json),
        )
        return result or 0
