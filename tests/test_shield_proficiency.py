import unittest
from pathlib import Path

from wm.spells.shield_proficiency import PASSIVE_SHELL_ID
from wm.spells.shield_proficiency import DUAL_WIELD_SKILL_ID
from wm.spells.shield_proficiency import DUAL_WIELD_SPELL_ID
from wm.spells.shield_proficiency import LEATHER_SKILL_ID
from wm.spells.shield_proficiency import LEATHER_SPELL_IDS
from wm.spells.shield_proficiency import MAIL_SKILL_ID
from wm.spells.shield_proficiency import MAIL_SPELL_IDS
from wm.spells.shield_proficiency import POLEARMS_SKILL_ID
from wm.spells.shield_proficiency import POLEARMS_SPELL_ID
from wm.spells.shield_proficiency import PLATE_MIN_LEVEL
from wm.spells.shield_proficiency import PLATE_SKILL_ID
from wm.spells.shield_proficiency import PLATE_SPELL_IDS
from wm.spells.shield_proficiency import SHIELD_SKILL_ID
from wm.spells.shield_proficiency import SHIELD_SPELL_IDS
from wm.spells.shield_proficiency import TWO_HANDED_AXES_SKILL_ID
from wm.spells.shield_proficiency import TWO_HANDED_AXES_SPELL_ID
from wm.spells.shield_proficiency import TWO_HANDED_SWORDS_SKILL_ID
from wm.spells.shield_proficiency import TWO_HANDED_SWORDS_SPELL_ID
from wm.spells.shield_proficiency import build_character_grant_sql
from wm.spells.shield_proficiency import build_world_grant_sql
from wm.spells.shield_proficiency import grant_shield_proficiency


class FakeMysqlClient:
    def __init__(self) -> None:
        self.queries: list[dict] = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        if "SELECT level FROM characters" in kwargs.get("sql", ""):
            return [{"level": "2"}]
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
        self.assertIn("`value` = GREATEST(`value`, VALUES(`value`))", sql)
        self.assertIn("`max` = GREATEST(`max`, VALUES(`max`))", sql)
        self.assertIn("(5406, 433, 1, 1)", sql)
        self.assertIn(f"(5406, {LEATHER_SKILL_ID}, 1, 1)", sql)
        self.assertIn(f"(5406, {MAIL_SKILL_ID}, 1, 1)", sql)
        self.assertIn(f"(5406, {DUAL_WIELD_SKILL_ID}, 1, 1)", sql)
        self.assertIn(f"(5406, {TWO_HANDED_SWORDS_SKILL_ID}, 1, 5)", sql)
        self.assertIn(f"(5406, {TWO_HANDED_AXES_SKILL_ID}, 1, 5)", sql)
        self.assertIn(f"(5406, {POLEARMS_SKILL_ID}, 1, 5)", sql)
        for spell_id in (
            SHIELD_SPELL_IDS
            + LEATHER_SPELL_IDS
            + MAIL_SPELL_IDS
            + (
                DUAL_WIELD_SPELL_ID,
                TWO_HANDED_SWORDS_SPELL_ID,
                TWO_HANDED_AXES_SPELL_ID,
                POLEARMS_SPELL_ID,
            )
        ):
            self.assertIn(f"(5406, {spell_id}, 255)", sql)
        self.assertNotIn(f"(5406, {PLATE_SKILL_ID}, 1, 1)", sql)
        self.assertNotIn(f"(5406, {PLATE_SPELL_IDS[0]}, 255)", sql)
        self.assertNotIn("SELECT guid FROM characters", sql)
        self.assertNotIn("playerbots", sql.lower())

    def test_character_grant_sql_scales_weapon_skill_caps_by_level(self) -> None:
        sql = build_character_grant_sql(5406, player_level=4)

        self.assertIn(f"(5406, {TWO_HANDED_SWORDS_SKILL_ID}, 1, 20)", sql)
        self.assertIn(f"(5406, {TWO_HANDED_AXES_SKILL_ID}, 1, 20)", sql)
        self.assertIn(f"(5406, {POLEARMS_SKILL_ID}, 1, 20)", sql)
        self.assertIn(f"(5406, {MAIL_SKILL_ID}, 1, 1)", sql)
        self.assertIn(f"(5406, {DUAL_WIELD_SKILL_ID}, 1, 1)", sql)
        self.assertNotIn(f"(5406, {PLATE_SKILL_ID}, 1, 1)", sql)

    def test_character_grant_sql_can_include_level_gated_plate(self) -> None:
        sql = build_character_grant_sql(5406, include_plate=True)

        self.assertIn(f"(5406, {PLATE_SKILL_ID}, 1, 1)", sql)
        self.assertIn(f"(5406, {PLATE_SPELL_IDS[0]}, 255)", sql)

    def test_world_grant_sql_targets_one_guid_and_passive_marker(self) -> None:
        sql = build_world_grant_sql(5406)

        self.assertIn("wm_spell_grant", sql)
        self.assertIn(f"{PASSIVE_SHELL_ID}", sql)
        self.assertIn("PlayerGUID = 5406", sql)
        self.assertIn("RevokedAt IS NULL", sql)
        self.assertIn("leather_armor", sql)
        self.assertIn("mail_armor", sql)
        self.assertIn("dual_wield", sql)
        self.assertIn("two_handed_swords", sql)
        self.assertIn("two_handed_axes", sql)
        self.assertIn("polearms", sql)
        self.assertIn("plate_armor", sql)
        self.assertIn("locked_capabilities", sql)
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
        self.assertFalse(result.plate_granted)
        self.assertEqual(result.player_level, 2)
        self.assertEqual(len(client.queries), 3)
        self.assertEqual(client.queries[0]["database"], "acore_characters")
        self.assertEqual(client.queries[1]["database"], "acore_characters")
        self.assertEqual(client.queries[2]["database"], "acore_world")
        self.assertIn("SELECT level FROM characters", client.queries[0]["sql"])
        self.assertIn("character_skills", client.queries[1]["sql"])
        self.assertIn(f"(5406, {TWO_HANDED_SWORDS_SKILL_ID}, 1, 10)", client.queries[1]["sql"])
        self.assertIn(f"(5406, {TWO_HANDED_AXES_SKILL_ID}, 1, 10)", client.queries[1]["sql"])
        self.assertIn(f"(5406, {POLEARMS_SKILL_ID}, 1, 10)", client.queries[1]["sql"])
        self.assertNotIn(f"(5406, {PLATE_SKILL_ID}, 1, 1)", client.queries[1]["sql"])
        self.assertIn("wm_spell_grant", client.queries[2]["sql"])

    def test_apply_can_use_live_level_override_for_weapon_caps(self) -> None:
        client = FakeMysqlClient()

        result = grant_shield_proficiency(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            mode="apply",
            player_level_override=4,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.player_level, 4)
        self.assertEqual(len(client.queries), 2)
        self.assertNotIn("SELECT level FROM characters", client.queries[0]["sql"])
        self.assertIn(f"(5406, {TWO_HANDED_SWORDS_SKILL_ID}, 1, 20)", client.queries[0]["sql"])
        self.assertIn(f"(5406, {TWO_HANDED_AXES_SKILL_ID}, 1, 20)", client.queries[0]["sql"])
        self.assertIn(f"(5406, {POLEARMS_SKILL_ID}, 1, 20)", client.queries[0]["sql"])
        self.assertNotIn(f"(5406, {PLATE_SKILL_ID}, 1, 1)", client.queries[0]["sql"])

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

    def test_native_runtime_syncs_combat_proficiencies_from_wm_grant(self) -> None:
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
        self.assertIn("TWO_HANDED_SWORDS_SPELL_ID = 202", runtime)
        self.assertIn("TWO_HANDED_AXES_SPELL_ID = 197", runtime)
        self.assertIn("POLEARMS_SPELL_ID = 200", runtime)
        self.assertIn("COMBAT_PROFICIENCY_RUNTIME_GRANTS", runtime)
        self.assertIn("SKILL_2H_SWORDS", runtime)
        self.assertIn("SKILL_2H_AXES", runtime)
        self.assertIn("SKILL_POLEARMS", runtime)
        self.assertIn("player->learnSpell(grant.spellId, false)", runtime)
        self.assertIn("player->SetSkill(static_cast<uint16>(grant.skillId)", runtime)
        self.assertIn("GrantKind = 'combat_proficiency'", runtime)
        self.assertIn("player->HasSpell(DUAL_WIELD_SPELL_ID)", runtime)
        self.assertIn("player->SetCanDualWield(true)", runtime)
        self.assertIn("MaintainCombatProficiencies(player)", player_script)
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

    def test_two_hand_weapon_and_armor_world_sql_seeds_dbc_overrides_without_broad_grant_tables(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_30_00_wm_spell_two_hand_weapon_proficiency.sql",
        ).read_text(encoding="utf-8")
        lowered = sql.lower()

        self.assertIn("insert into skillraceclassinfo_dbc", lowered)
        self.assertIn("insert into skilllineability_dbc", lowered)
        for skill_id in (
            TWO_HANDED_SWORDS_SKILL_ID,
            TWO_HANDED_AXES_SKILL_ID,
            POLEARMS_SKILL_ID,
            MAIL_SKILL_ID,
            PLATE_SKILL_ID,
        ):
            self.assertIn(str(skill_id), sql)
        for spell_id in (
            TWO_HANDED_SWORDS_SPELL_ID,
            TWO_HANDED_AXES_SPELL_ID,
            POLEARMS_SPELL_ID,
            MAIL_SPELL_IDS[0],
            PLATE_SPELL_IDS[0],
        ):
            self.assertIn(str(spell_id), sql)
        self.assertIn(f"(100293, 293, 2047, 8, 128, {PLATE_MIN_LEVEL}, 0, 0)", sql)
        self.assertIn("(100055, 55, 202, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0)", sql)
        self.assertIn("(100172, 172, 197, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0)", sql)
        self.assertIn("(100229, 229, 200, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0)", sql)
        self.assertIn("(100413, 413, 8737, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0)", sql)
        self.assertIn("acquiremethod", lowered)
        self.assertNotIn("insert into playercreateinfo_skills", lowered)
        self.assertNotIn("insert into playercreateinfo_spell_custom", lowered)
        self.assertNotIn("insert into mod_learnspells", lowered)
        self.assertNotIn("update playercreateinfo_skills", lowered)
        self.assertNotIn("update playercreateinfo_spell_custom", lowered)
        self.assertNotIn("update mod_learnspells", lowered)


if __name__ == "__main__":
    unittest.main()
