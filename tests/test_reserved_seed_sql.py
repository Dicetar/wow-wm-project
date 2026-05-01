from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wm.reserved import seed_sql


class ReservedSeedSqlTests(unittest.TestCase):
    def test_entity_type_override_keeps_cache_escape_item_rows_in_item_namespace(self) -> None:
        payload = {
            "ranges": {
                "item_cache_escape": {
                    "entity_type": "item",
                    "start": 919000,
                    "end": 919005,
                    "purpose": "test",
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            ranges_path = Path(tmp).joinpath("ranges.json")
            output_path = Path(tmp).joinpath("seed.sql")
            ranges_path.write_text(json.dumps(payload), encoding="utf-8")

            result = seed_sql.main(["--ranges", str(ranges_path), "--output", str(output_path)])

            self.assertEqual(result, 0)
            output = output_path.read_text(encoding="utf-8")
            self.assertIn("-- item_cache_escape (item): 919000..919005", output)
            self.assertIn("VALUES ('item', 919000, 'free'", output)
            self.assertIn("VALUES ('item', 919001, 'free'", output)
            self.assertIn("VALUES ('item', 919002, 'free'", output)
            self.assertIn("VALUES ('item', 919003, 'free'", output)
            self.assertIn("VALUES ('item', 919004, 'free'", output)
            self.assertIn("VALUES ('item', 919005, 'free'", output)
            self.assertNotIn("VALUES ('item_cache_escape'", output)


if __name__ == "__main__":
    unittest.main()
