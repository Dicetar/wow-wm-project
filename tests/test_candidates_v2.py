from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.candidates.providers_v2 import build_item_candidates_v2, build_quest_candidates_v2, build_spell_candidates_v2


class CandidateProviderV2Tests(unittest.TestCase):
    def test_spell_candidates_use_dynamic_name_lang_field(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "spell_dbc",
            "row_count": 2,
            "sample_count": 2,
            "order_columns": ["ID"],
            "primary_key": ["ID"],
            "schema": [
                {"name": "ID", "type": "int"},
                {"name": "Name_Lang_enUS", "type": "varchar"},
                {"name": "ManaCost", "type": "int"},
            ],
            "samples": [
                {"position_offset": 0, "row": {"ID": 1, "Name_Lang_enUS": "Arcane Burst", "ManaCost": 50}},
                {"position_offset": 1, "row": {"ID": 2, "Name_Lang_enUS": "Frost Spike", "ManaCost": 40}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "spell_dbc.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_spell_candidates_v2(path, limit=2)
        self.assertEqual(len(result.options), 2)
        self.assertEqual(result.options[0].label, "Arcane Burst")
        self.assertEqual(result.options[0].entry_id, 1)
        self.assertIn("ManaCost=50", result.options[0].summary or "")

    def test_item_candidates_filter_deprecated_labels(self) -> None:
        payload = [
            {"entry": 157, "name": "Deprecated Tauren Recruit's Shirt", "Quality": 1, "ItemLevel": 1},
            {"entry": 1000, "name": "Arcane Blade", "Quality": 3, "ItemLevel": 50},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "item_template.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_item_candidates_v2(path, limit=5)
        self.assertEqual(len(result.options), 1)
        self.assertEqual(result.options[0].label, "Arcane Blade")

    def test_quest_candidates_keep_normal_labels(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "quest_template",
            "row_count": 2,
            "sample_count": 2,
            "order_columns": ["ID"],
            "primary_key": ["ID"],
            "schema": [
                {"name": "ID", "type": "int"},
                {"name": "LogTitle", "type": "varchar"},
                {"name": "QuestLevel", "type": "int"},
            ],
            "samples": [
                {"position_offset": 0, "row": {"ID": 9001, "LogTitle": "A Cautious Truce", "QuestLevel": 10}},
                {"position_offset": 1, "row": {"ID": 9002, "LogTitle": "[UNUSED] Dummy Quest", "QuestLevel": 10}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "quest_template.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_quest_candidates_v2(path, limit=5)
        self.assertEqual(len(result.options), 1)
        self.assertEqual(result.options[0].label, "A Cautious Truce")


if __name__ == "__main__":
    unittest.main()
