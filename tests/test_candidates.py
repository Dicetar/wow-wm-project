from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.candidates.providers import build_item_candidates, build_quest_candidates, build_spell_candidates


class CandidateProviderTests(unittest.TestCase):
    def test_build_quest_candidates_from_sample_bundle(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "quest_template",
            "row_count": 10,
            "sample_count": 2,
            "order_columns": ["ID"],
            "primary_key": ["ID"],
            "schema": [{"name": "ID", "type": "int"}],
            "samples": [
                {"position_offset": 0, "row": {"ID": 1, "LogTitle": "A Trial", "QuestLevel": 10, "MinLevel": 8}},
                {"position_offset": 1, "row": {"ID": 2, "LogTitle": "Another Trial", "QuestLevel": 12, "MinLevel": 10}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "quest_template.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_quest_candidates(path, limit=2)
        self.assertEqual(len(result.options), 2)
        self.assertEqual(result.options[0].label, "A Trial")
        self.assertEqual(result.options[0].entry_id, 1)

    def test_build_item_candidates_from_row_list(self) -> None:
        payload = [
            {"entry": 100, "name": "Arcane Blade", "Quality": 4, "ItemLevel": 60},
            {"entry": 101, "name": "Storm Tome", "Quality": 3, "ItemLevel": 45},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "item_template.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_item_candidates(path, limit=2)
        self.assertEqual(len(result.options), 2)
        self.assertEqual(result.options[0].label, "Arcane Blade")
        self.assertEqual(result.options[0].entry_id, 100)

    def test_build_spell_candidates_normalizes_null_wrapper(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "spell_dbc",
            "row_count": 5,
            "sample_count": 1,
            "order_columns": ["ID"],
            "primary_key": ["ID"],
            "schema": [{"name": "ID", "type": "int"}],
            "samples": [
                {"position_offset": 0, "row": {"ID": 900001, "SpellName1": "Arcane Burst", "Category": "NULL"}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "spell_dbc.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_spell_candidates(path, limit=1)
        self.assertEqual(len(result.options), 1)
        self.assertEqual(result.options[0].label, "Arcane Burst")
        self.assertNotIn("NULL", result.options[0].summary or "")


if __name__ == "__main__":
    unittest.main()
