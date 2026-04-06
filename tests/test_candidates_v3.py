from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.candidates.providers_v3 import build_item_candidates_v3, build_quest_candidates_v3, build_spell_candidates_v3


class CandidateProviderV3Tests(unittest.TestCase):
    def test_bundle_schema_with_field_key_still_finds_quest_labels(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "quest_template",
            "row_count": 2,
            "sample_count": 2,
            "order_columns": ["ID"],
            "primary_key": ["ID"],
            "schema": [
                {"Field": "ID", "Type": "int"},
                {"Field": "LogTitle", "Type": "varchar"},
                {"Field": "QuestLevel", "Type": "int"},
            ],
            "samples": [
                {"position_offset": 0, "row": {"ID": 45, "LogTitle": "Discover Rolf's Fate", "QuestLevel": 10}},
                {"position_offset": 1, "row": {"ID": 64, "LogTitle": "The Forgotten Heirloom", "QuestLevel": 12}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "quest_template.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_quest_candidates_v3(path, limit=2)
        self.assertEqual(len(result.options), 2)
        self.assertEqual(result.options[0].label, "Discover Rolf's Fate")

    def test_row_keys_fallback_still_finds_item_names_when_schema_is_odd(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "item_template",
            "row_count": 2,
            "sample_count": 2,
            "order_columns": ["entry"],
            "primary_key": ["entry"],
            "schema": [{"unexpected": "shape"}],
            "samples": [
                {"position_offset": 0, "row": {"entry": 1000, "name": "Arcane Blade", "Quality": 3, "ItemLevel": 50}},
                {"position_offset": 1, "row": {"entry": 1001, "name": "Deprecated Test Blade", "Quality": 3, "ItemLevel": 50}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "item_template.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_item_candidates_v3(path, limit=5)
        self.assertEqual(len(result.options), 1)
        self.assertEqual(result.options[0].label, "Arcane Blade")

    def test_spell_candidates_find_name_lang_with_field_schema(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "spell_dbc",
            "row_count": 2,
            "sample_count": 2,
            "order_columns": ["ID"],
            "primary_key": ["ID"],
            "schema": [
                {"Field": "ID", "Type": "int"},
                {"Field": "Name_Lang_enUS", "Type": "varchar"},
                {"Field": "ManaCost", "Type": "int"},
            ],
            "samples": [
                {"position_offset": 0, "row": {"ID": 900001, "Name_Lang_enUS": "Arcane Burst", "ManaCost": 50}},
                {"position_offset": 1, "row": {"ID": 900002, "Name_Lang_enUS": "Frost Spike", "ManaCost": 40}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "spell_dbc.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_spell_candidates_v3(path, limit=2)
        self.assertEqual(len(result.options), 2)
        self.assertEqual(result.options[0].label, "Arcane Burst")
        self.assertEqual(result.options[0].entry_id, 900001)


if __name__ == "__main__":
    unittest.main()
