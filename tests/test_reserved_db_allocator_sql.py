from __future__ import annotations

import unittest

from wm.reserved.db_allocator import _json_or_null, _sql_int_or_null, _sql_string, _sql_string_or_null


class ReservedDbAllocatorSqlTests(unittest.TestCase):
    def test_sql_string_quotes(self) -> None:
        self.assertEqual(_sql_string("wm_arc"), "'wm_arc'")
        self.assertEqual(_sql_string("wm_'arc"), "'wm_''arc'")

    def test_sql_string_or_null(self) -> None:
        self.assertEqual(_sql_string_or_null(None), "NULL")
        self.assertEqual(_sql_string_or_null("abc"), "'abc'")

    def test_sql_int_or_null(self) -> None:
        self.assertEqual(_sql_int_or_null(None), "NULL")
        self.assertEqual(_sql_int_or_null(42), "42")

    def test_json_or_null(self) -> None:
        self.assertEqual(_json_or_null(None), "NULL")
        self.assertTrue(_json_or_null(["a", "b"]).startswith("'[") )


if __name__ == "__main__":
    unittest.main()
