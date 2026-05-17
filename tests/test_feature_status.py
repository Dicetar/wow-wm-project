from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.status.feature_status import (
    load_feature_status,
    summarize_by_status,
    validate_feature_status,
)

_REPO = Path(__file__).resolve().parents[1]


class FeatureStatusTests(unittest.TestCase):
    def test_repo_file_is_valid(self) -> None:
        result = validate_feature_status()
        self.assertTrue(result.ok, f"feature_status.json invalid: {result.issues}")

    def test_repo_file_loads_and_has_entries(self) -> None:
        doc = load_feature_status()
        self.assertTrue(doc.schema_version)
        self.assertTrue(doc.entries)
        keys = {e.feature_key for e in doc.entries}
        self.assertIn("living.nemesis", keys)
        self.assertIn("perception.bounty_full_loop", keys)

    def test_summary_counts(self) -> None:
        counts = summarize_by_status(load_feature_status())
        self.assertEqual(sum(counts.values()), len(load_feature_status().entries))

    def test_invalid_status_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(
                json.dumps(
                    {
                        "schema_version": "x",
                        "entries": [
                            {
                                "feature_key": "a",
                                "layer": "l",
                                "repo_status": "NOPE",
                                "gameplay_status": "WORKING",
                                "scope": "s",
                                "last_verified": "2026-01-01",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            r = validate_feature_status(p)
            self.assertFalse(r.ok)
            self.assertTrue(any("invalid" in i for i in r.issues))

    def test_duplicate_feature_key_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "dup.json"
            entry = {
                "feature_key": "dup",
                "layer": "l",
                "repo_status": "WORKING",
                "gameplay_status": "WORKING",
                "scope": "s",
                "last_verified": "2026-01-01",
            }
            p.write_text(json.dumps({"schema_version": "x", "entries": [entry, entry]}), encoding="utf-8")
            self.assertFalse(validate_feature_status(p).ok)


if __name__ == "__main__":
    unittest.main()
