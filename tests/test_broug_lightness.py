import json
import unittest
from pathlib import Path

from wm.character.journey import build_journey_operations
from wm.character.journey import validate_journey_plan
from wm.spells.broug_lightness import BROUG_CLOUD_STEP_CREDIT_ENTRY
from wm.spells.broug_lightness import BROUG_CLOUD_STEP_SHELL_ID
from wm.spells.broug_lightness import BROUG_KILLING_INTENT_SHELL_ID
from wm.spells.broug_lightness import BROUG_LIGHTNESS_ARC_KEY
from wm.spells.broug_lightness import BROUG_LIGHTNESS_STAGE_KEY
from wm.spells.broug_lightness import BROUG_MARKED_MERIDIAN_SHELL_ID
from wm.spells.broug_lightness import BROUG_NO_FOOTFALL_QUEST_ID
from wm.spells.broug_lightness import BROUG_PARALLEL_ENERGY_SURGE_ITEM_ID
from wm.spells.broug_lightness import BROUG_PARALLEL_ENERGY_SURGE_SELF_AURA_SHELL_ID
from wm.spells.broug_lightness import BROUG_PLAYER_GUID
from wm.spells.broug_lightness import BROUG_SILENT_MERIDIAN_SHELL_ID
from wm.spells.broug_lightness import BROUG_STEPS_QUEST_ID
from wm.spells.broug_lightness import BROUG_STEPS_TARGET_COUNT
from wm.spells.broug_lightness import BROUG_STEPS_TARGET_ENTRY
from wm.spells.broug_lightness import BROUG_STEPS_TARGET_NAME
from wm.spells.broug_lightness import build_character_grant_sql
from wm.spells.broug_lightness import build_character_journey_sql
from wm.spells.broug_lightness import build_character_verify_sql
from wm.spells.broug_lightness import build_world_grant_sql
from wm.spells.broug_lightness import build_world_verify_sql
from wm.spells.broug_lightness import grant_broug_lightness


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


class BrougLightnessTests(unittest.TestCase):
    def test_constants_use_fresh_lightness_ids_and_avoid_parallel_claims(self) -> None:
        self.assertEqual(BROUG_PLAYER_GUID, 5405)
        self.assertEqual(BROUG_STEPS_QUEST_ID, 910182)
        self.assertEqual(BROUG_NO_FOOTFALL_QUEST_ID, 910183)
        self.assertEqual(BROUG_STEPS_TARGET_ENTRY, 2261)
        self.assertEqual(BROUG_STEPS_TARGET_NAME, "Syndicate Watchman")
        self.assertEqual(BROUG_STEPS_TARGET_COUNT, 8)
        self.assertEqual(BROUG_CLOUD_STEP_SHELL_ID, 946202)
        self.assertEqual(BROUG_MARKED_MERIDIAN_SHELL_ID, 946203)
        self.assertEqual(BROUG_KILLING_INTENT_SHELL_ID, 946620)
        self.assertEqual(BROUG_SILENT_MERIDIAN_SHELL_ID, 946803)
        self.assertEqual(BROUG_CLOUD_STEP_CREDIT_ENTRY, 920106)
        self.assertEqual(BROUG_PARALLEL_ENERGY_SURGE_ITEM_ID, 910014)
        self.assertEqual(BROUG_PARALLEL_ENERGY_SURGE_SELF_AURA_SHELL_ID, 946606)
        self.assertNotEqual(BROUG_KILLING_INTENT_SHELL_ID, BROUG_PARALLEL_ENERGY_SURGE_SELF_AURA_SHELL_ID)

    def test_character_journey_sql_records_arc_without_reward_grants(self) -> None:
        sql = build_character_journey_sql(5405)

        self.assertIn("wm_character_profile", sql)
        self.assertIn("wm_character_arc_state", sql)
        self.assertIn("wm_character_conversation_steering", sql)
        self.assertIn(BROUG_LIGHTNESS_ARC_KEY, sql)
        self.assertIn(BROUG_LIGHTNESS_STAGE_KEY, sql)
        self.assertIn("Broug", sql)
        self.assertIn("more parry expansion", sql)
        self.assertNotIn("character_spell", sql)
        self.assertNotIn("wm_spell_grant", sql)
        self.assertNotIn("playercreateinfo", sql.lower())
        self.assertNotIn("mod_learnspells", sql.lower())

    def test_journey_plan_prompt_kind_fits_character_schema(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        plan = validate_journey_plan(
            json.loads(
                repo_root.joinpath(
                    "control",
                    "examples",
                    "journey",
                    "broug_lightness_assassin_v1.json",
                ).read_text(encoding="utf-8")
            )
        )

        prompt_kinds = [prompt["prompt_kind"] for prompt in plan["prompt_queue"]]

        self.assertIn("broug_silent_proof", prompt_kinds)
        self.assertTrue(all(len(prompt_kind) <= 32 for prompt_kind in prompt_kinds))

    def test_recovery_grant_sql_is_scoped_and_manual_is_opt_in(self) -> None:
        cloud_only_character_sql = build_character_grant_sql(5405)
        cloud_only_world_sql = build_world_grant_sql(5405)
        full_character_sql = build_character_grant_sql(5405, include_manual=True)
        full_world_sql = build_world_grant_sql(5405, include_manual=True)

        self.assertIn(f"(5405, {BROUG_CLOUD_STEP_SHELL_ID}, 255)", cloud_only_character_sql)
        self.assertNotIn(str(BROUG_SILENT_MERIDIAN_SHELL_ID), cloud_only_character_sql)
        self.assertIn(f"PlayerGUID = 5405", cloud_only_world_sql)
        self.assertIn(f"ShellSpellID = {BROUG_CLOUD_STEP_SHELL_ID}", cloud_only_world_sql)
        self.assertNotIn(f"ShellSpellID = {BROUG_SILENT_MERIDIAN_SHELL_ID}", cloud_only_world_sql)
        self.assertIn(f"(5405, {BROUG_SILENT_MERIDIAN_SHELL_ID}, 255)", full_character_sql)
        self.assertIn("broug_silent_meridian_v1", full_world_sql)
        self.assertNotIn("SELECT guid FROM characters", full_world_sql)
        self.assertNotIn("playerbots", full_world_sql.lower())

    def test_apply_records_journey_only_by_default(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_lightness(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5405,
            mode="apply",
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.applied)
        self.assertFalse(result.grant_rewards)
        self.assertEqual(result.shell_spell_ids, ())
        self.assertEqual(len(client.queries), 1)
        self.assertEqual(client.queries[0]["database"], "acore_characters")
        self.assertIn("wm_character_arc_state", client.queries[0]["sql"])
        self.assertNotIn("character_spell", client.queries[0]["sql"])

    def test_verify_mode_executes_read_only_character_and_world_checks(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_lightness(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5405,
            mode="verify",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.applied)
        self.assertEqual(result.mode, "verify")
        self.assertEqual(len(client.queries), 6)
        self.assertEqual(client.queries[0]["database"], "acore_characters")
        self.assertEqual(client.queries[1]["database"], "acore_characters")
        self.assertTrue(all(query["database"] == "acore_world" for query in client.queries[2:]))
        joined_sql = "\n".join(query["sql"] for query in client.queries).lower()
        self.assertIn("wm_character_arc_state", joined_sql)
        self.assertIn("wm_broug_lightness_counter", joined_sql)
        self.assertNotIn("insert ", joined_sql)
        self.assertNotIn("update ", joined_sql)
        self.assertNotIn("delete ", joined_sql)

    def test_apply_reward_recovery_executes_character_then_world_grants(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_lightness(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5405,
            mode="apply",
            grant_rewards=True,
            include_manual=True,
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.applied)
        self.assertEqual(result.shell_spell_ids, (BROUG_CLOUD_STEP_SHELL_ID, BROUG_SILENT_MERIDIAN_SHELL_ID))
        self.assertEqual(len(client.queries), 3)
        self.assertEqual(client.queries[0]["database"], "acore_characters")
        self.assertEqual(client.queries[1]["database"], "acore_characters")
        self.assertEqual(client.queries[2]["database"], "acore_world")
        self.assertIn("wm_character_arc_state", client.queries[0]["sql"])
        self.assertIn("character_spell", client.queries[1]["sql"])
        self.assertIn("wm_spell_grant", client.queries[2]["sql"])

    def test_dry_run_does_not_touch_db(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_lightness(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5405,
            mode="dry-run",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.applied)
        self.assertEqual(result.shell_spell_ids, ())
        self.assertEqual(client.queries, [])

    def test_verify_sql_targets_lightness_tables_and_shells(self) -> None:
        world_sql = build_world_verify_sql(5405)
        character_sql = build_character_verify_sql(5405)

        self.assertIn("wm_spell_shell", world_sql)
        self.assertIn("wm_spell_behavior", world_sql)
        self.assertIn("wm_broug_lightness_counter", world_sql)
        self.assertIn(str(BROUG_CLOUD_STEP_SHELL_ID), world_sql)
        self.assertIn(str(BROUG_MARKED_MERIDIAN_SHELL_ID), world_sql)
        self.assertIn(str(BROUG_KILLING_INTENT_SHELL_ID), world_sql)
        self.assertIn(str(BROUG_SILENT_MERIDIAN_SHELL_ID), world_sql)
        self.assertIn("wm_character_arc_state", character_sql)
        self.assertIn("character_spell", character_sql)
        self.assertIn(BROUG_LIGHTNESS_ARC_KEY, character_sql)

    def test_rejects_non_explicit_guid(self) -> None:
        with self.assertRaises(ValueError):
            build_character_journey_sql(0)

    def test_world_sql_seeds_lightness_arc_without_parallel_id_reuse_or_parry_expansion(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_05_02_00_wm_spell_broug_lightness_assassin.sql",
        ).read_text(encoding="utf-8")
        lowered = sql.lower()

        self.assertIn("create table if not exists wm_broug_lightness_counter", lowered)
        self.assertIn("insert into wm_spell_shell", lowered)
        self.assertIn("insert into wm_spell_behavior", lowered)
        self.assertIn("broug_cloud_step_v1", sql)
        self.assertIn("broug_marked_meridian_v1", sql)
        self.assertIn("broug_killing_intent_v1", sql)
        self.assertIn("broug_silent_meridian_v1", sql)
        self.assertIn(str(BROUG_CLOUD_STEP_SHELL_ID), sql)
        self.assertIn(str(BROUG_MARKED_MERIDIAN_SHELL_ID), sql)
        self.assertIn(str(BROUG_KILLING_INTENT_SHELL_ID), sql)
        self.assertIn(str(BROUG_SILENT_MERIDIAN_SHELL_ID), sql)
        self.assertIn(str(BROUG_STEPS_QUEST_ID), sql)
        self.assertIn(str(BROUG_NO_FOOTFALL_QUEST_ID), sql)
        self.assertIn(str(BROUG_CLOUD_STEP_CREDIT_ENTRY), sql)
        self.assertIn("@wm_broug_syndicate_watchman_entry := 2261", sql)
        self.assertIn("Syndicate Watchmen", sql)
        self.assertIn("FactionGroup 8, EnemyGroup 1", sql)
        self.assertNotIn("@wm_broug_defias_profiteer_entry", sql)
        self.assertNotIn("Defias Profiteer", sql)
        self.assertNotIn("1669", sql)
        self.assertIn("@wm_broug_questgiver_entry := 332", sql)
        self.assertIn("'min_range_yards', 0.0", sql)
        self.assertIn("'max_range_yards', 25.0", sql)
        self.assertIn("'energy_cost', 20", sql)
        self.assertIn("'cooldown_ms', 12000", sql)
        self.assertIn("'killing_intent_duration_ms', 10000", sql)
        self.assertIn("'marked_meridian_duration_ms', 12000", sql)
        self.assertIn("'duration_ms', 12000", sql)
        self.assertIn("'kill_window_ms', 10000", sql)
        self.assertIn("'cooldown_reduction_ms', 6000", sql)
        self.assertIn("'damage_bonus_pct', 35", sql)
        self.assertIn("'departure_visual_spell_id', 24222", sql)
        self.assertIn("'arrival_visual_spell_id', 24222", sql)
        self.assertIn("'counter_key', 'cloud_step_strike'", sql)
        self.assertIn("'vulnerable_stack_interaction', 'none'", sql)
        self.assertIn("spell_wm_shell_dispatch", sql)
        self.assertIn("spell_cooldown_overrides", sql)
        self.assertIn("wm_reserved_slot", sql)
        self.assertNotIn("@wm_broug_killing_intent_shell_spell_id := 946606", sql)
        self.assertNotIn("@wm_broug_item", lowered)
        self.assertNotIn("broug_universal_parry_v1", sql)
        self.assertNotIn("broug_deflect_v1", sql)
        self.assertNotIn("wm_broug_guard_counter", sql)
        self.assertNotIn("insert into playercreateinfo", lowered)
        self.assertNotIn("insert into mod_learnspells", lowered)

    def test_native_runtime_hooks_lightness_without_consuming_vulnerable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        runtime = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")
        header = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.h",
        ).read_text(encoding="utf-8")
        player_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_player_scripts.cpp",
        ).read_text(encoding="utf-8")
        unit_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_unit_scripts.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn("BROUG_CLOUD_STEP_SHELL_ID = 946202", runtime)
        self.assertIn("BROUG_MARKED_MERIDIAN_SHELL_ID = 946203", runtime)
        self.assertIn("BROUG_KILLING_INTENT_SHELL_ID = 946620", runtime)
        self.assertIn("BROUG_SILENT_MERIDIAN_SHELL_ID = 946803", runtime)
        self.assertIn("BrougCloudStepConfig", header)
        self.assertIn("BrougSilentMeridianConfig", header)
        self.assertIn("killingIntentSpellId = 946620", header)
        self.assertIn("departureVisualSpellId = 24222", header)
        self.assertIn("arrivalVisualSpellId = 24222", header)
        self.assertIn("IsBrougLightnessBehaviorKind", runtime)
        self.assertIn("broug_cloud_step_v1", runtime)
        self.assertIn("broug_marked_meridian_v1", runtime)
        self.assertIn("broug_killing_intent_v1", runtime)
        self.assertIn("broug_silent_meridian_v1", runtime)
        self.assertIn("LoadActiveBrougLightnessState", runtime)
        self.assertIn("wm_broug_lightness_counter", runtime)
        self.assertIn("SelectBrougCloudStepTarget", runtime)
        self.assertIn("ResolveBrougCloudStepLanding", runtime)
        self.assertNotIn("!IsPlayerAllowed(player) || !gConfig.boneboundServantEnabled", runtime)
        self.assertIn("IsWithinLOSInMap", runtime)
        self.assertIn("CanReachPositionAndGetValidCoords", runtime)
        self.assertIn("GetPower(POWER_ENERGY)", runtime)
        self.assertIn("ModifyPower(POWER_ENERGY", runtime)
        self.assertIn("UNIT_STATE_ROOT", runtime)
        self.assertIn("UNIT_STATE_STUNNED", runtime)
        self.assertIn("UNIT_STATE_CONTROLLED", runtime)
        self.assertIn("NearTeleportTo", runtime)
        self.assertIn("ApplyBrougTimedVisibleAura", runtime)
        self.assertIn("PlayBrougCloudStepVisual", runtime)
        self.assertIn("markedMeridianTargetGuid", runtime)
        self.assertIn("IsBrougMarkedMeridianStateActive", runtime)
        self.assertIn("RemoveAurasDueToSpell(config.markedMeridianSpellId)", runtime)
        self.assertIn("TryConsumeBrougMarkedMeridian", runtime)
        self.assertIn("RecordBrougLightnessCounter", runtime)
        self.assertIn("CreditBrougQuestProgress(player, config.creditCreatureEntry)", runtime)
        self.assertIn("HandleBrougLightnessMeleeDamage", runtime)
        self.assertIn("HandleBrougLightnessSpellDamage", runtime)
        self.assertIn("HandleBrougLightnessCreatureKill", runtime)
        self.assertIn("GetSpellCooldownDelay(state.cloudStep.shellSpellId)", runtime)
        self.assertIn("ModifySpellCooldown(state.cloudStep.shellSpellId", runtime)
        self.assertIn("HasBrougLightnessMarkReady(attacker, victim)", runtime)
        self.assertIn("gBrougLightnessPreserveVulnerableByVictim", runtime)
        self.assertIn("if (HasBrougLightnessMarkReady(attacker, victim))", runtime)
        self.assertIn("return;", runtime)
        self.assertIn("CanCompleteBrougLightnessQuest", runtime)
        self.assertIn("HandleBrougLightnessQuestComplete", runtime)
        self.assertIn("HandleBrougLightnessMeleeDamage(attacker, target, damage)", unit_script)
        self.assertIn("HandleBrougLightnessSpellDamage(attacker, target, damage, spellInfo)", unit_script)
        self.assertIn("TickBrougLightness(player, diff)", player_script)
        self.assertIn("MaintainBrougLightness(player", player_script)
        self.assertIn("ForgetBrougLightness(player)", player_script)
        self.assertIn("OnPlayerBeforeQuestComplete", player_script)
        self.assertIn("OnPlayerCompleteQuest", player_script)
        self.assertIn("OnPlayerCreatureKill", player_script)

        shell_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_shell_scripts.cpp",
        ).read_text(encoding="utf-8")
        self.assertIn("WM shell {} failed: {}", shell_script)
        self.assertIn("WM Broug: Cloud Step fired.", shell_script)

    def test_custom_id_registry_claims_lightness_ids_and_preserves_parallel_claim(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        registry = json.loads(repo_root.joinpath("data", "specs", "custom_id_registry.json").read_text(encoding="utf-8"))
        claims = {(entry["namespace"], int(entry["id"])): entry for entry in registry["claims"]}

        for key in [
            ("spell", BROUG_CLOUD_STEP_SHELL_ID),
            ("spell", BROUG_MARKED_MERIDIAN_SHELL_ID),
            ("spell", BROUG_KILLING_INTENT_SHELL_ID),
            ("spell", BROUG_SILENT_MERIDIAN_SHELL_ID),
            ("quest", BROUG_STEPS_QUEST_ID),
            ("quest", BROUG_NO_FOOTFALL_QUEST_ID),
            ("creature_template", BROUG_CLOUD_STEP_CREDIT_ENTRY),
        ]:
            self.assertIn(key, claims)
            self.assertEqual(claims[key]["status"], "PARTIAL")
            self.assertEqual(claims[key]["player_guid_scope"], 5405)

        self.assertIn(("item", BROUG_PARALLEL_ENERGY_SURGE_ITEM_ID), claims)
        self.assertIn(("spell", BROUG_PARALLEL_ENERGY_SURGE_SELF_AURA_SHELL_ID), claims)
        self.assertEqual(claims[("spell", BROUG_PARALLEL_ENERGY_SURGE_SELF_AURA_SHELL_ID)]["key"], "energy_surge_potion_v1")
        self.assertEqual(claims[("spell", BROUG_KILLING_INTENT_SHELL_ID)]["key"], "broug_killing_intent_v1")

    def test_journey_example_records_broug_lightness_identity(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        plan_path = repo_root.joinpath("control", "examples", "journey", "broug_lightness_assassin_v1.json")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        normalized = validate_journey_plan(plan)
        operations = build_journey_operations(normalized)

        self.assertEqual(normalized["player_guid"], 5405)
        self.assertEqual(normalized["arc_states"][0]["arc_key"], BROUG_LIGHTNESS_ARC_KEY)
        self.assertEqual(normalized["arc_states"][0]["stage_key"], BROUG_LIGHTNESS_STAGE_KEY)
        self.assertTrue(any(item["unlock_id"] == BROUG_CLOUD_STEP_SHELL_ID for item in normalized["unlocks"]))
        self.assertTrue(any(item["unlock_id"] == BROUG_SILENT_MERIDIAN_SHELL_ID for item in normalized["unlocks"]))
        self.assertTrue(any(item["steering_key"] == "broug_lightness_over_guard" for item in normalized["conversation_steering"]))
        self.assertGreaterEqual(len(operations), 5)


if __name__ == "__main__":
    unittest.main()
