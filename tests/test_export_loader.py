from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.export.loader import load_export
from wm.export.models import ExportBundle, RowListExport


class ExportLoaderTests(unittest.TestCase):
    def test_loads_bundle_export(self) -> None:
        payload = {
            "database": "acore_world",
            "table": "creature_template",
            "row_count": 12345,
            "sample_count": 2,
            "order_columns": ["entry"],
            "primary_key": ["entry"],
            "schema": [{"name": "entry", "type": "int"}],
            "samples": [
                {"entry": 1, "name": "Wolf", "subname": "NULL"},
                {"entry": 2, "name": "Guard", "subname": None},
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bundle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_export(path)

        self.assertIsInstance(loaded, ExportBundle)
        assert isinstance(loaded, ExportBundle)
        self.assertEqual(loaded.table, "creature_template")
        self.assertEqual(loaded.row_count, 12345)
        self.assertEqual(loaded.samples[0]["subname"], None)

    def test_loads_row_list_export(self) -> None:
        payload = [
            {"entry": 1, "name": "Wolf", "subname": "NULL"},
            {"entry": 2, "name": "Guard", "subname": None},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rows.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_export(path)

        self.assertIsInstance(loaded, RowListExport)
        assert isinstance(loaded, RowListExport)
        self.assertEqual(len(loaded.rows), 2)
        self.assertEqual(loaded.rows[0]["subname"], None)


if __name__ == "__main__":
    unittest.main()
