from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.status.feature_status import (
    load_feature_status,
    summarize_by_axis,
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
        runtime = summarize_by_axis(load_feature_status(), "runtime_status")
        self.assertEqual(sum(runtime.values()), len(load_feature_status().entries))

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
                                "runtime_status": "PARTIAL",
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

    def test_runtime_status_field_is_loaded_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "status.json"
            p.write_text(
                json.dumps(
                    {
                        "schema_version": "x",
                        "entries": [
                            {
                                "feature_key": "a",
                                "layer": "l",
                                "repo_status": "WORKING",
                                "runtime_status": "PARTIAL",
                                "gameplay_status": "UNKNOWN",
                                "requires_live_proof": True,
                                "scope": "s",
                                "last_verified": "2026-01-01",
                                "last_live_proof": "proof-1",
                                "evidence_refs": ["proofs/proof-1.json"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            doc = load_feature_status(p)
            self.assertEqual(doc.entries[0].runtime_status, "PARTIAL")
            self.assertTrue(doc.entries[0].requires_live_proof)
            self.assertEqual(doc.entries[0].last_live_proof, "proof-1")
            self.assertEqual(doc.entries[0].evidence_refs, ["proofs/proof-1.json"])

    def test_live_proof_required_working_gameplay_needs_proof_ref(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "status.json"
            p.write_text(
                json.dumps(
                    {
                        "schema_version": "x",
                        "entries": [
                            {
                                "feature_key": "autoplay.x",
                                "layer": "autoplay",
                                "repo_status": "WORKING",
                                "runtime_status": "WORKING",
                                "gameplay_status": "WORKING",
                                "requires_live_proof": True,
                                "scope": "s",
                                "last_verified": "2026-01-01",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = validate_feature_status(p)
            self.assertFalse(result.ok)
            self.assertTrue(any("last_live_proof" in issue for issue in result.issues))

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
