from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.candidates.providers_v4 import build_spell_candidates_v4
from wm.candidates.ranking import CandidateContext


class CandidateProviderV4Tests(unittest.TestCase):
    def test_spell_candidates_are_ranked_by_context_and_noise_penalties(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "spell_dbc",
            "row_count": 3,
            "sample_count": 3,
            "order_columns": ["ID"],
            "primary_key": ["ID"],
            "schema": [
                {"Field": "ID", "Type": "int"},
                {"Field": "Name_Lang_enUS", "Type": "varchar"},
                {"Field": "ManaCost", "Type": "int"},
                {"Field": "Effect_1", "Type": "int"},
                {"Field": "DurationIndex", "Type": "int"},
            ],
            "samples": [
                {"position_offset": 0, "row": {"ID": 100, "Name_Lang_enUS": "Arcane Burst", "ManaCost": 50, "Effect_1": 6, "DurationIndex": 0}},
                {"position_offset": 1, "row": {"ID": 101, "Name_Lang_enUS": "Mine Slave - On Gossip", "ManaCost": 0, "Effect_1": 6, "DurationIndex": 0}},
                {"position_offset": 2, "row": {"ID": 102, "Name_Lang_enUS": "Stance Rage Passive", "ManaCost": 0, "Effect_1": 6, "DurationIndex": 0}},
            ],
        }
        context = CandidateContext(target_level_hint=10, positive_terms=["arcane"], negative_terms=[])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "spell_dbc.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = build_spell_candidates_v4(path, context=context, limit=3)
        self.assertEqual(result.options[0].label, "Arcane Burst")
        self.assertIn("score=", result.options[0].summary or "")


if __name__ == "__main__":
    unittest.main()
