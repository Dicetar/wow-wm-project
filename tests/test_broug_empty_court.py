import json
import unittest
from pathlib import Path

from wm.character.journey import build_journey_operations
from wm.character.journey import validate_journey_plan
from wm.spells.broug_empty_court import BROUG_ASH_WORN_TRACK_GO
from wm.spells.broug_empty_court import BROUG_BOLTED_CELLAR_HATCH_GO
from wm.spells.broug_empty_court import BROUG_BOUNTY_CREDIT_ENTRY
from wm.spells.broug_empty_court import BROUG_COURT_REMNANT_ENTRY
from wm.spells.broug_empty_court import BROUG_DOMAIN_UNSEALED_QUEST_ID
from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_ARC_KEY
from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_REWARD_SHELL_IDS
from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_STAGE_KEY
from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_VISIBLE_SHELL_IDS
from wm.spells.broug_empty_court import BROUG_HAL_MORROW_ENTRY
from wm.spells.broug_empty_court import BROUG_KILLING_INTENT_DOMAIN_SHELL_ID
from wm.spells.broug_empty_court import BROUG_NINETY_EIGHT_QUEST_ID
from wm.spells.broug_empty_court import BROUG_OATH_CREDIT_ENTRY
from wm.spells.broug_empty_court import BROUG_PLAYER_GUID
from wm.spells.broug_empty_court import BROUG_PREDATORS_STRIKE_SHELL_ID
from wm.spells.broug_empty_court import BROUG_PURGED_STATE_SHELL_ID
from wm.spells.broug_empty_court import BROUG_QI_REVERSAL_SHELL_ID
from wm.spells.broug_empty_court import BROUG_ROOM_CREDIT_ENTRY
from wm.spells.broug_empty_court import BROUG_ROOM_QUEST_ID
from wm.spells.broug_empty_court import BROUG_STILLING_QUEST_ID
from wm.spells.broug_empty_court import BROUG_STILLNESS_CREDIT_ENTRY
from wm.spells.broug_empty_court import BROUG_SUPPRESSED_SHELL_ID
from wm.spells.broug_empty_court import BROUG_VITALITY_DRAIN_SHELL_ID
from wm.spells.broug_empty_court import BROUG_WEIGHT_QUEST_ID
from wm.spells.broug_empty_court import BROUG_WEI_JIN_ENTRY
from wm.spells.broug_empty_court import build_character_grant_sql
from wm.spells.broug_empty_court import build_character_journey_sql
from wm.spells.broug_empty_court import build_character_verify_sql
from wm.spells.broug_empty_court import build_sql_summary
from wm.spells.broug_empty_court import build_world_grant_sql
from wm.spells.broug_empty_court import build_world_verify_sql
from wm.spells.broug_empty_court import grant_broug_empty_court


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


class BrougEmptyCourtTests(unittest.TestCase):
    def test_constants_claim_v2_ids_and_avoid_v1_credit_reuse(self) -> None:
        self.assertEqual(BROUG_PLAYER_GUID, 5405)
        self.assertEqual(BROUG_WEIGHT_QUEST_ID, 910184)
        self.assertEqual(BROUG_STILLING_QUEST_ID, 910185)
        self.assertEqual(BROUG_NINETY_EIGHT_QUEST_ID, 910186)
        self.assertEqual(BROUG_ROOM_QUEST_ID, 910187)
        self.assertEqual(BROUG_DOMAIN_UNSEALED_QUEST_ID, 910188)
        self.assertEqual(BROUG_WEI_JIN_ENTRY, 915500)
        self.assertEqual(BROUG_HAL_MORROW_ENTRY, 915520)
        self.assertEqual(BROUG_COURT_REMNANT_ENTRY, 915540)
        self.assertEqual(BROUG_ASH_WORN_TRACK_GO, 195500)
        self.assertEqual(BROUG_BOLTED_CELLAR_HATCH_GO, 195501)
        self.assertEqual((BROUG_STILLNESS_CREDIT_ENTRY, BROUG_BOUNTY_CREDIT_ENTRY, BROUG_ROOM_CREDIT_ENTRY, BROUG_OATH_CREDIT_ENTRY), (920107, 920108, 920109, 920110))
        self.assertEqual(BROUG_SUPPRESSED_SHELL_ID, 946204)
        self.assertEqual(BROUG_QI_REVERSAL_SHELL_ID, 946621)
        self.assertEqual(BROUG_PURGED_STATE_SHELL_ID, 946622)
        self.assertEqual(BROUG_KILLING_INTENT_DOMAIN_SHELL_ID, 946804)
        self.assertEqual(BROUG_PREDATORS_STRIKE_SHELL_ID, 946805)
        self.assertEqual(BROUG_VITALITY_DRAIN_SHELL_ID, 946806)
        self.assertNotIn(920106, (BROUG_STILLNESS_CREDIT_ENTRY, BROUG_BOUNTY_CREDIT_ENTRY, BROUG_ROOM_CREDIT_ENTRY, BROUG_OATH_CREDIT_ENTRY))
        self.assertNotIn(946606, BROUG_EMPTY_COURT_VISIBLE_SHELL_IDS)

    def test_character_journey_sql_records_v2_without_reward_grants(self) -> None:
        sql = build_character_journey_sql(5405)

        self.assertIn("wm_character_profile", sql)
        self.assertIn("wm_character_arc_state", sql)
        self.assertIn(BROUG_EMPTY_COURT_ARC_KEY, sql)
        self.assertIn(BROUG_EMPTY_COURT_STAGE_KEY, sql)
        self.assertIn("room pressure", sql)
        self.assertIn("Vulnerable stacks", sql)
        self.assertNotIn("character_spell", sql)
        self.assertNotIn("wm_spell_grant", sql)
        self.assertNotIn("playercreateinfo", sql.lower())
        self.assertNotIn("mod_learnspells", sql.lower())

    def test_recovery_grant_sql_is_reward_only_and_scoped(self) -> None:
        character_sql = build_character_grant_sql(5405)
        world_sql = build_world_grant_sql(5405)

        for shell_id in BROUG_EMPTY_COURT_REWARD_SHELL_IDS:
            self.assertIn(f"(5405, {shell_id}, 255)", character_sql)
            self.assertIn(f"ShellSpellID = {shell_id}", world_sql)
        self.assertNotIn(str(BROUG_SUPPRESSED_SHELL_ID), character_sql)
        self.assertNotIn(str(BROUG_PURGED_STATE_SHELL_ID), character_sql)
        self.assertNotIn(str(BROUG_SUPPRESSED_SHELL_ID), world_sql)
        self.assertNotIn(str(BROUG_PURGED_STATE_SHELL_ID), world_sql)
        self.assertIn("PlayerGUID = 5405", world_sql)
        self.assertNotIn("SELECT guid FROM characters", world_sql)
        self.assertNotIn("playerbots", world_sql.lower())

    def test_apply_records_journey_only_by_default(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_empty_court(
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

    def test_apply_reward_recovery_executes_character_then_world_grants(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_empty_court(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5405,
            mode="apply",
            grant_rewards=True,
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.applied)
        self.assertEqual(result.shell_spell_ids, BROUG_EMPTY_COURT_REWARD_SHELL_IDS)
        self.assertEqual(len(client.queries), 3)
        self.assertEqual(client.queries[0]["database"], "acore_characters")
        self.assertEqual(client.queries[1]["database"], "acore_characters")
        self.assertEqual(client.queries[2]["database"], "acore_world")
        self.assertIn("character_spell", client.queries[1]["sql"])
        self.assertIn("wm_spell_grant", client.queries[2]["sql"])

    def test_verify_mode_executes_read_only_character_and_world_checks(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_empty_court(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5405,
            mode="verify",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.applied)
        self.assertEqual(len(client.queries), 7)
        joined_sql = "\n".join(query["sql"] for query in client.queries).lower()
        self.assertIn("wm_character_arc_state", joined_sql)
        self.assertIn("wm_broug_empty_court_counter", joined_sql)
        self.assertNotIn("insert ", joined_sql)
        self.assertNotIn("update ", joined_sql)
        self.assertNotIn("delete ", joined_sql)

    def test_verify_and_summary_sql_target_v2_tables_and_shells(self) -> None:
        world_sql = build_world_verify_sql(5405)
        character_sql = build_character_verify_sql(5405)
        summary = build_sql_summary(5405, grant_rewards=True)

        self.assertIn("wm_spell_shell", world_sql)
        self.assertIn("wm_spell_behavior", world_sql)
        self.assertIn("wm_broug_empty_court_counter", world_sql)
        self.assertIn("quest_template", world_sql)
        for shell_id in BROUG_EMPTY_COURT_VISIBLE_SHELL_IDS:
            self.assertIn(str(shell_id), world_sql)
        self.assertIn(BROUG_EMPTY_COURT_ARC_KEY, character_sql)
        self.assertIn("character_grant_sql", summary)
        self.assertIn("world_grant_sql", summary)

    def test_world_sql_seeds_v2_without_forbidden_id_reuse_or_parry_expansion(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_05_02_01_wm_spell_broug_empty_court_v2.sql",
        ).read_text(encoding="utf-8")
        lowered = sql.lower()

        self.assertIn("create table if not exists wm_broug_empty_court_counter", lowered)
        self.assertIn("broug_killing_intent_domain_v1", sql)
        self.assertIn("broug_suppressed_v1", sql)
        self.assertIn("broug_qi_reversal_v1", sql)
        self.assertIn("broug_purged_state_v1", sql)
        self.assertIn("broug_predators_strike_v1", sql)
        self.assertIn("broug_vitality_drain_v1", sql)
        for token in ["910184", "910185", "910186", "910187", "910188", "915500", "915520", "915540", "195500", "195501", "920107", "920108", "920109", "920110"]:
            self.assertIn(token, sql)
        for shell_id in BROUG_EMPTY_COURT_VISIBLE_SHELL_IDS:
            self.assertIn(str(shell_id), sql)
        self.assertIn("spell_wm_shell_dispatch", sql)
        self.assertIn("spell_cooldown_overrides", sql)
        self.assertIn("'duration_ms', 12000", sql)
        self.assertIn("'purged_duration_ms', 30000", sql)
        self.assertIn("'duration_ms', 30000", sql)
        self.assertIn("'base_killing_intent_duration_ms', 15000", sql)
        self.assertIn("'suppressed_duration_ms', 12000", sql)
        self.assertIn("'death_extension_ms', 5000", sql)
        self.assertIn("creature_template_model", sql)
        self.assertIn("1736", sql)
        self.assertIn("11415", sql)
        self.assertIn("3035", sql)
        self.assertIn("1006", sql)
        self.assertIn("2344", sql)
        self.assertIn("wm_reserved_slot", sql)
        self.assertNotIn("920106", sql)
        self.assertNotIn("910014", sql)
        self.assertNotIn("946606", sql)
        self.assertNotIn("946604", sql)
        self.assertNotIn("946801", sql)
        self.assertNotIn("broug_universal_parry_v1", sql)
        self.assertNotIn("broug_deflect_v1", sql)
        self.assertNotIn("insert into playercreateinfo", lowered)
        self.assertNotIn("insert into mod_learnspells", lowered)

    def test_native_runtime_hooks_empty_court_v2(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        runtime = repo_root.joinpath("native_modules", "mod-wm-spells", "src", "wm_spell_runtime.cpp").read_text(encoding="utf-8")
        header = repo_root.joinpath("native_modules", "mod-wm-spells", "src", "wm_spell_runtime.h").read_text(encoding="utf-8")
        player_script = repo_root.joinpath("native_modules", "mod-wm-spells", "src", "wm_spell_player_scripts.cpp").read_text(encoding="utf-8")
        unit_script = repo_root.joinpath("native_modules", "mod-wm-spells", "src", "wm_spell_unit_scripts.cpp").read_text(encoding="utf-8")

        self.assertIn("BrougKillingIntentDomainConfig", header)
        self.assertIn("BrougQiReversalConfig", header)
        self.assertIn("baseKillingIntentDurationMs = 15000", header)
        self.assertIn("suppressedDurationMs = 12000", header)
        self.assertIn("deathExtensionMs = 5000", header)
        self.assertIn("purgedDurationMs = 30000", header)
        self.assertIn("BrougPredatorsStrikeConfig", header)
        self.assertIn("BrougVitalityDrainConfig", header)
        self.assertIn("BROUG_SUPPRESSED_SHELL_ID = 946204", runtime)
        self.assertIn("BROUG_QI_REVERSAL_SHELL_ID = 946621", runtime)
        self.assertIn("BROUG_PURGED_STATE_SHELL_ID = 946622", runtime)
        self.assertIn("BROUG_KILLING_INTENT_DOMAIN_SHELL_ID = 946804", runtime)
        self.assertIn("BROUG_PREDATORS_STRIKE_SHELL_ID = 946805", runtime)
        self.assertIn("BROUG_VITALITY_DRAIN_SHELL_ID = 946806", runtime)
        self.assertIn("IsBrougEmptyCourtBehaviorKind", runtime)
        self.assertIn("wm_broug_empty_court_counter", runtime)
        self.assertIn("ExecuteBrougQiReversal", runtime)
        self.assertIn("ApplyBrougDomainPulse", runtime)
        self.assertIn("HandleBrougEmptyCourtMeleeDamage", runtime)
        self.assertIn("HandleBrougEmptyCourtSpellDamage", runtime)
        self.assertIn("HandleBrougEmptyCourtCreatureKill", runtime)
        self.assertIn("HandleBrougEmptyCourtAuraApply", runtime)
        self.assertIn("HandleBrougEmptyCourtQuestComplete", runtime)
        self.assertIn("ResolveBrougKillingIntentDurationMs", runtime)
        self.assertIn("ApplyBrougPredatorHeal(player, playerGuid, damage)", runtime)
        self.assertIn("IsBrougSilentMeridianKillWindowActive", runtime)
        self.assertIn("HandleBrougEmptyCourtCreatureKill(killer, killed)", player_script)
        self.assertLess(player_script.index("HandleBrougEmptyCourtCreatureKill(killer, killed)"), player_script.index("HandleBrougLightnessCreatureKill(killer, killed)"))
        self.assertIn("TickBrougEmptyCourt(player, diff)", player_script)
        self.assertIn("MaintainBrougEmptyCourt(player", player_script)
        self.assertIn("ForgetBrougEmptyCourt(player)", player_script)
        self.assertIn("HandleBrougEmptyCourtMeleeDamage(attacker, target, damage)", unit_script)
        self.assertIn("HandleBrougEmptyCourtSpellDamage(attacker, target, damage, spellInfo)", unit_script)
        self.assertIn("HandleBrougEmptyCourtAuraApply(unit, aura)", unit_script)

    def test_custom_id_registry_claims_empty_court_ids(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        registry = json.loads(repo_root.joinpath("data", "specs", "custom_id_registry.json").read_text(encoding="utf-8"))
        claims = {(entry["namespace"], int(entry["id"])): entry for entry in registry["claims"]}

        for namespace, id_ in [
            ("spell", BROUG_SUPPRESSED_SHELL_ID),
            ("spell", BROUG_QI_REVERSAL_SHELL_ID),
            ("spell", BROUG_PURGED_STATE_SHELL_ID),
            ("spell", BROUG_KILLING_INTENT_DOMAIN_SHELL_ID),
            ("spell", BROUG_PREDATORS_STRIKE_SHELL_ID),
            ("spell", BROUG_VITALITY_DRAIN_SHELL_ID),
            ("quest", BROUG_WEIGHT_QUEST_ID),
            ("quest", BROUG_STILLING_QUEST_ID),
            ("quest", BROUG_NINETY_EIGHT_QUEST_ID),
            ("quest", BROUG_ROOM_QUEST_ID),
            ("quest", BROUG_DOMAIN_UNSEALED_QUEST_ID),
            ("creature_template", BROUG_WEI_JIN_ENTRY),
            ("creature_template", BROUG_HAL_MORROW_ENTRY),
            ("creature_template", BROUG_COURT_REMNANT_ENTRY),
            ("creature_template", BROUG_STILLNESS_CREDIT_ENTRY),
            ("creature_template", BROUG_BOUNTY_CREDIT_ENTRY),
            ("creature_template", BROUG_ROOM_CREDIT_ENTRY),
            ("creature_template", BROUG_OATH_CREDIT_ENTRY),
            ("gameobject_template", BROUG_ASH_WORN_TRACK_GO),
            ("gameobject_template", BROUG_BOLTED_CELLAR_HATCH_GO),
        ]:
            self.assertIn((namespace, id_), claims)
            self.assertEqual(claims[(namespace, id_)]["status"], "PARTIAL")
            self.assertEqual(claims[(namespace, id_)]["player_guid_scope"], 5405)

        for entry_id in range(915530, 915540):
            self.assertIn(("creature_template", entry_id), claims)

    def test_journey_example_records_empty_court_identity(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        plan_path = repo_root.joinpath("control", "examples", "journey", "broug_empty_court_v2.json")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        normalized = validate_journey_plan(plan)
        operations = build_journey_operations(normalized)

        self.assertEqual(normalized["player_guid"], 5405)
        self.assertEqual(normalized["arc_states"][0]["arc_key"], BROUG_EMPTY_COURT_ARC_KEY)
        self.assertEqual(normalized["arc_states"][0]["stage_key"], BROUG_EMPTY_COURT_STAGE_KEY)
        for shell_id in BROUG_EMPTY_COURT_REWARD_SHELL_IDS:
            self.assertTrue(any(item["unlock_id"] == shell_id for item in normalized["unlocks"]))
        self.assertTrue(any(item["steering_key"] == "broug_empty_court_v2_scope" for item in normalized["conversation_steering"]))
        self.assertGreaterEqual(len(operations), 5)

    def test_rejects_non_explicit_guid(self) -> None:
        with self.assertRaises(ValueError):
            build_character_journey_sql(0)


if __name__ == "__main__":
    unittest.main()
