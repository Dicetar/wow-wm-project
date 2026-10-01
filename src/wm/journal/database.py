
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
import time
import sqlite3
from pathlib import Path

@dataclass
class JournalEntry:
    timestamp: int
    player_guid: int
    event_kind: str  # 'kill', 'loot', 'quest_complete', etc.
    subject_guid: Optional[str] = None
    subject_entry: Optional[int] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "player_guid": self.player_guid,
            "event_kind": self.event_kind,
            "subject_guid": self.subject_guid,
            "subject_entry": self.subject_entry,
            "payload": self.payload
        }

class PlayerJournal:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    player_guid INTEGER NOT NULL,
                    event_kind TEXT NOT NULL,
                    subject_guid TEXT,
                    subject_entry INTEGER,
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_player_event ON journal_entries (player_guid, event_kind)")

    def log_event(self, entry: JournalEntry) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO journal_entries (timestamp, player_guid, event_kind, subject_guid, subject_entry, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                (entry.timestamp, entry.player_guid, entry.event_kind, entry.subject_guid, entry.subject_entry, json.dumps(entry.payload))
            )

    def get_history(self, player_guid: int, limit: int = 20) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM journal_entries WHERE player_guid = ? ORDER BY timestamp DESC LIMIT ?",
                (player_guid, limit)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stat(self, player_guid: int, event_kind: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM journal_entries WHERE player_guid = ? AND event_kind = ?",
                (player_guid, event_kind)
            )
            return cursor.fetchone()[0]

# Testing the new component
if __name__ == "__main__":
    test_db = 'test_journal.db'
    journal = PlayerJournal(test_db)

    print("Logging test event...")
    test_entry = JournalEntry(
        timestamp=int(time.time()),
        player_guid=12345,
        event_kind='kill',
        subject_guid='GUID_WOLF',
        subject_entry=99,
        payload={'name': 'Grey Wolf', 'region': 'Westfall'}
    )
    journal.log_event(test_entry)

    print(f"Count for player 12345 (kill): {journal.get_stat(12345, 'kill')}")
    print("Raw history:")
    for e in journal.get_history(12345):
        print(e)

    os.remove(test_db)
