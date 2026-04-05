from __future__ import annotations

import unittest

from wm.db.mysql_cli import MysqlCliClient


class MysqlCliParserTests(unittest.TestCase):
    def test_parse_tsv_output(self) -> None:
        stdout = "CharacterGUID\tCharacterName\tWMPersona\n42\tAldren\tdefault\n"
        rows = MysqlCliClient._parse_tsv_output(stdout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["CharacterGUID"], "42")
        self.assertEqual(rows[0]["CharacterName"], "Aldren")

    def test_parse_tsv_output_normalizes_null(self) -> None:
        stdout = "entry\tsubname\n1498\tNULL\n"
        rows = MysqlCliClient._parse_tsv_output(stdout)
        self.assertEqual(rows[0]["subname"], None)

    def test_parse_tsv_output_empty(self) -> None:
        rows = MysqlCliClient._parse_tsv_output("")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
