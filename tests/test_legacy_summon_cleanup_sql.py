import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHARACTER_CLEANUP_SQL = REPO_ROOT / "sql" / "dev" / "clear_jecia_legacy_summon_state_characters.sql"
WORLD_CLEANUP_SQL = REPO_ROOT / "sql" / "dev" / "clear_jecia_legacy_summon_state_world.sql"


class LegacySummonCleanupSqlTests(unittest.TestCase):
    def test_character_cleanup_preserves_stock_summon_voidwalker(self) -> None:
        sql = CHARACTER_CLEANUP_SQL.read_text(encoding="utf-8")

        self.assertNotRegex(sql, re.compile(r"CreatedBySpell\s+IN\s*\(\s*697\b", re.IGNORECASE))
        self.assertNotRegex(sql, re.compile(r"spell\s+IN\s*\(\s*697\b", re.IGNORECASE))
        self.assertIn("INSERT IGNORE INTO character_spell (guid, spell, specMask)", sql)
        self.assertRegex(sql, re.compile(r"VALUES\s*\(\s*@wm_player_guid\s*,\s*697\s*,\s*255\s*\)", re.IGNORECASE))

    def test_character_cleanup_removes_retired_dev_carriers_only(self) -> None:
        sql = CHARACTER_CLEANUP_SQL.read_text(encoding="utf-8")

        self.assertIn("49126", sql)
        self.assertIn("8853", sql)
        self.assertIn("57913", sql)
        self.assertIn("bonebound_alpha_shell_spell_present", sql)

    def test_world_cleanup_removes_stock_script_bindings_not_character_spells(self) -> None:
        sql = WORLD_CLEANUP_SQL.read_text(encoding="utf-8")

        self.assertIn("DELETE FROM spell_script_names", sql)
        self.assertIn("697", sql)
        self.assertNotIn("character_spell", sql)
        self.assertNotIn("character_pet", sql)


if __name__ == "__main__":
    unittest.main()
