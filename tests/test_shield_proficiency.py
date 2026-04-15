import unittest
from pathlib import Path

from wm.spells.shield_proficiency import PASSIVE_SHELL_ID
from wm.spells.shield_proficiency import DUAL_WIELD_SKILL_ID
from wm.spells.shield_proficiency import DUAL_WIELD_SPELL_ID
from wm.spells.shield_proficiency import LEATHER_SKILL_ID
from wm.spells.shield_proficiency import LEATHER_SPELL_IDS
from wm.spells.shield_proficiency import SHIELD_SKILL_ID
from wm.spells.shield_proficiency import SHIELD_SPELL_IDS
from wm.spells.shield_proficiency import build_character_grant_sql
from wm.spells.shield_proficiency import build_world_grant_sql
from wm.spells.shield_proficiency import grant_shield_proficiency


class FakeMysqlClient:
    def __init__(self) -> None:
        self.queries: list[dict] = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        return []


class SettingsStub:
    world_db_host = "127.0.0.1"
    world_db_port = 33307
    world_db_user = "acore"
    world_db_password = "acore"
    world_db_name = "acore_world"
    char_db_host = "127.0.0.1"
    char_db_port = 33307
    char_db_user = "acore"
    char_db_password = "acore"
    char_db_name = "acore_characters"


class ShieldProficiencySqlTests(unittest.TestCase):
    def test_character_grant_sql_targets_one_guid_and_required_rows(self) -> None:
        sql = build_character_grant_sql(5406)

        self.assertIn("character_skills", sql)
        self.assertIn("character_spell", sql)
        self.assertIn("(5406, 433, 1, 1)", sql)
        self.assertIn(f"(5406, {LEATHER_SKILL_ID}, 1, 1)", sql)
        self.assertIn(f"(5406, {DUAL_WIELD_SKILL_ID}, 1, 1)", sql)
        for spell_id in SHIELD_SPELL_IDS + LEATHER_SPELL_IDS + (DUAL_WIELD_SPELL_ID,):
            self.assertIn(f"(5406, {spell_id}, 255)", sql)
        self.assertNotIn("SELECT guid FROM characters", sql)
        self.assertNotIn("playerbots", sql.lower())

    def test_world_grant_sql_targets_one_guid_and_passive_marker(self) -> None:
        sql = build_world_grant_sql(5406)

        self.assertIn("wm_spell_grant", sql)
        self.assertIn(f"{PASSIVE_SHELL_ID}", sql)
        self.assertIn("PlayerGUID = 5406", sql)
        self.assertIn("RevokedAt IS NULL", sql)
        self.assertIn("leather_armor", sql)
        self.assertIn("dual_wield", sql)
        self.assertNotIn("SELECT guid FROM characters", sql)
        self.assertNotIn("playerbots", sql.lower())

    def test_apply_executes_character_then_world_only(self) -> None:
        client = FakeMysqlClient()

        result = grant_shield_proficiency(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            mode="apply",
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.applied)
        self.assertEqual(len(client.queries), 2)
        self.assertEqual(client.queries[0]["database"], "acore_characters")
        self.assertEqual(client.queries[1]["database"], "acore_world")
        self.assertIn("character_skills", client.queries[0]["sql"])
        self.assertIn("wm_spell_grant", client.queries[1]["sql"])

    def test_dry_run_does_not_touch_db(self) -> None:
        client = FakeMysqlClient()

        result = grant_shield_proficiency(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            mode="dry-run",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.applied)
        self.assertEqual(client.queries, [])

    def test_rejects_non_explicit_guid(self) -> None:
        with self.assertRaises(ValueError):
            build_character_grant_sql(0)

    def test_world_sql_seeds_dbc_overrides_without_broad_grant_tables(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_15_02_wm_spell_shield_proficiency.sql",
        ).read_text(encoding="utf-8")
        lowered = sql.lower()

        self.assertIn("insert into skillraceclassinfo_dbc", lowered)
        self.assertIn("insert into skilllineability_dbc", lowered)
        self.assertIn(f"skillid, racemask, classmask", lowered)
        self.assertIn(str(SHIELD_SKILL_ID), sql)
        self.assertIn("acquiremethod", lowered)
        self.assertNotIn("insert into playercreateinfo_skills", lowered)
        self.assertNotIn("insert into playercreateinfo_spell_custom", lowered)
        self.assertNotIn("insert into mod_learnspells", lowered)
        self.assertNotIn("update playercreateinfo_skills", lowered)
        self.assertNotIn("update playercreateinfo_spell_custom", lowered)
        self.assertNotIn("update mod_learnspells", lowered)

    def test_leather_world_sql_seeds_dbc_overrides_without_broad_grant_tables(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_15_03_wm_spell_leather_dual_wield_proficiency.sql",
        ).read_text(encoding="utf-8")
        lowered = sql.lower()

        self.assertIn("insert into skillraceclassinfo_dbc", lowered)
        self.assertIn("insert into skilllineability_dbc", lowered)
        self.assertIn(str(LEATHER_SKILL_ID), sql)
        self.assertIn(str(LEATHER_SPELL_IDS[0]), sql)
        self.assertNotIn("insert into playercreateinfo_skills", lowered)
        self.assertNotIn("insert into playercreateinfo_spell_custom", lowered)
        self.assertNotIn("insert into mod_learnspells", lowered)
        self.assertNotIn("update playercreateinfo_skills", lowered)
        self.assertNotIn("update playercreateinfo_spell_custom", lowered)
        self.assertNotIn("update mod_learnspells", lowered)

    def test_native_runtime_syncs_dual_wield_without_shield_reapply(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        runtime = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")
        player_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_player_scripts.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn("COMBAT_PROFICIENCY_SHELL_ID = 944000", runtime)
        self.assertIn("DUAL_WIELD_SPELL_ID = 674", runtime)
        self.assertIn("GrantKind = 'combat_proficiency'", runtime)
        self.assertIn("player->HasSpell(DUAL_WIELD_SPELL_ID)", runtime)
        self.assertIn("player->SetCanDualWield(true)", runtime)
        self.assertIn("MaintainCombatProficiencies(player)", player_script)
        self.assertNotIn("SetSkill(SKILL_SHIELD", runtime)
        self.assertNotIn("OnPlayerIsClass", player_script)

    def test_dual_wield_world_sql_seeds_skill_validity_without_broad_grant_tables(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_15_04_wm_spell_dual_wield_skill_validity.sql",
        ).read_text(encoding="utf-8")
        lowered = sql.lower()

        self.assertIn("insert into skillraceclassinfo_dbc", lowered)
        self.assertIn(str(DUAL_WIELD_SKILL_ID), sql)
        self.assertNotIn("insert into playercreateinfo_skills", lowered)
        self.assertNotIn("insert into playercreateinfo_spell_custom", lowered)
        self.assertNotIn("insert into mod_learnspells", lowered)
        self.assertNotIn("update playercreateinfo_skills", lowered)
        self.assertNotIn("update playercreateinfo_spell_custom", lowered)
        self.assertNotIn("update mod_learnspells", lowered)


if __name__ == "__main__":
    unittest.main()
