import unittest
from pathlib import Path

from wm.spells.broug_guard import BROUG_AUTO_RETALIATION_SHELL_ID
from wm.spells.broug_guard import BROUG_DEFLECTED_SHELL_ID
from wm.spells.broug_guard import BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID
from wm.spells.broug_guard import BROUG_DEFLECT_SHELL_ID
from wm.spells.broug_guard import BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID
from wm.spells.broug_guard import BROUG_SKIRMISHER_MARK_SHELL_ID
from wm.spells.broug_guard import BROUG_UNIVERSAL_PARRY_SHELL_ID
from wm.spells.broug_guard import BROUG_VULNERABLE_SHELL_ID
from wm.spells.broug_guard import build_character_grant_sql
from wm.spells.broug_guard import build_world_grant_sql
from wm.spells.broug_guard import grant_broug_guard


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


class BrougGuardTests(unittest.TestCase):
    def test_bridge_lab_runtime_keeps_broug_in_wm_spells_allowlist(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        configure = repo_root.joinpath("scripts", "bridge_lab", "Configure-BridgeLabRuntime.ps1").read_text(
            encoding="utf-8"
        )
        start = repo_root.joinpath("scripts", "bridge_lab", "Start-BridgeLabAll.ps1").read_text(encoding="utf-8")

        self.assertIn('[string]$WmSpellsPlayerGuidAllowList = "5406,5405"', configure)
        self.assertIn('[string]$WmSpellsPlayerGuidAllowList = ""', start)
        self.assertIn("$effectiveWmSpellsAllowList = $WmSpellsPlayerGuidAllowList", start)
        self.assertIn('if ($PlayerGuid -ne 5405)', start)
        self.assertIn('$effectiveWmSpellsAllowList = "$effectiveWmSpellsAllowList,5405"', start)
        self.assertIn('"-WmSpellsPlayerGuidAllowList", $effectiveWmSpellsAllowList', start)

    def test_character_grant_sql_targets_one_guid_and_shells(self) -> None:
        sql = build_character_grant_sql(5405)

        self.assertIn("character_spell", sql)
        self.assertIn(str(BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID), sql)
        self.assertIn("946604", sql)
        self.assertIn(f"(5405, {BROUG_UNIVERSAL_PARRY_SHELL_ID}, 255)", sql)
        self.assertIn(f"(5405, {BROUG_SKIRMISHER_MARK_SHELL_ID}, 255)", sql)
        self.assertNotIn("character_skills", sql)
        self.assertNotIn("playercreateinfo", sql.lower())
        self.assertNotIn("mod_learnspells", sql.lower())

    def test_world_grant_sql_targets_one_guid_and_two_active_grants(self) -> None:
        sql = build_world_grant_sql(5405)

        self.assertIn("wm_spell_grant", sql)
        self.assertIn("PlayerGUID = 5405", sql)
        self.assertIn(str(BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID), sql)
        self.assertIn("946604", sql)
        self.assertIn(f"ShellSpellID = {BROUG_UNIVERSAL_PARRY_SHELL_ID}", sql)
        self.assertIn(f"ShellSpellID = {BROUG_SKIRMISHER_MARK_SHELL_ID}", sql)
        self.assertIn("broug_universal_parry_v1", sql)
        self.assertIn("broug_skirmisher_shot_v1", sql)
        self.assertIn("replaced_by_targeted_skirmisher_shot_v1", sql)
        self.assertIn("RevokedAt IS NULL", sql)
        self.assertNotIn("SELECT guid FROM characters", sql)
        self.assertNotIn("playerbots", sql.lower())

    def test_apply_executes_character_then_world_only(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_guard(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5405,
            mode="apply",
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.applied)
        self.assertEqual(result.player_guid, 5405)
        self.assertEqual(len(client.queries), 2)
        self.assertEqual(client.queries[0]["database"], "acore_characters")
        self.assertEqual(client.queries[1]["database"], "acore_world")
        self.assertIn("character_spell", client.queries[0]["sql"])
        self.assertIn("wm_spell_grant", client.queries[1]["sql"])

    def test_dry_run_does_not_touch_db(self) -> None:
        client = FakeMysqlClient()

        result = grant_broug_guard(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5405,
            mode="dry-run",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.applied)
        self.assertEqual(client.queries, [])

    def test_rejects_non_explicit_guid(self) -> None:
        with self.assertRaises(ValueError):
            build_character_grant_sql(0)

    def test_world_sql_seeds_behavior_and_counter_without_broad_grants(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        passive_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_30_01_wm_spell_broug_guard_passives.sql",
        ).read_text(encoding="utf-8")
        reward_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_30_02_wm_spell_broug_deflect_rewards.sql",
        ).read_text(encoding="utf-8")
        skirmisher_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_30_04_wm_spell_broug_skirmisher_shot.sql",
        ).read_text(encoding="utf-8")
        deflect_rework_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_05_01_00_wm_spell_broug_deflect_rework.sql",
        ).read_text(encoding="utf-8")
        counter_stance_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_05_01_01_wm_spell_broug_deflect_counter_stance.sql",
        ).read_text(encoding="utf-8")
        deflect_retune_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_05_01_02_wm_spell_broug_deflect_window_retune.sql",
        ).read_text(encoding="utf-8")
        counter_stance_aura_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_05_01_03_wm_spell_broug_counterstrike_stance_aura.sql",
        ).read_text(encoding="utf-8")
        sql = passive_sql + "\n" + reward_sql + "\n" + skirmisher_sql + "\n" + deflect_rework_sql + "\n" + counter_stance_sql + "\n" + deflect_retune_sql + "\n" + counter_stance_aura_sql
        lowered = sql.lower()

        self.assertIn("create table if not exists wm_broug_guard_counter", lowered)
        self.assertIn("create table if not exists wm_broug_deflect_counter_stance", lowered)
        self.assertIn("insert into wm_spell_shell", lowered)
        self.assertIn("insert into wm_spell_behavior", lowered)
        self.assertIn(str(BROUG_UNIVERSAL_PARRY_SHELL_ID), sql)
        self.assertIn(str(BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID), sql)
        self.assertIn(str(BROUG_SKIRMISHER_MARK_SHELL_ID), sql)
        self.assertIn(str(BROUG_VULNERABLE_SHELL_ID), sql)
        self.assertIn(str(BROUG_DEFLECTED_SHELL_ID), sql)
        self.assertIn(str(BROUG_DEFLECT_SHELL_ID), sql)
        self.assertIn(str(BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID), sql)
        self.assertIn(str(BROUG_AUTO_RETALIATION_SHELL_ID), sql)
        self.assertIn("broug_universal_parry_v1", sql)
        self.assertIn("broug_skirmisher_shot_v1", sql)
        self.assertIn("broug_vulnerable_v1", sql)
        self.assertIn("broug_deflected_v1", sql)
        self.assertIn("broug_deflect_v1", sql)
        self.assertIn("broug_deflect_counter_stance_v1", sql)
        self.assertIn("broug_auto_retaliation_v1", sql)
        self.assertIn("base_chance_pct", sql)
        self.assertIn("strength_to_chance_pct", sql)
        self.assertIn("expertise_to_chance_pct", sql)
        self.assertIn("weapon_mastery_to_chance_pct", sql)
        self.assertIn("damage_pct", sql)
        self.assertIn("min_attack_interval_ms", sql)
        self.assertIn("skirmisher_shot_hit", sql)
        self.assertIn("parry_pre_ms", sql)
        self.assertIn("parry_animation_ms", sql)
        self.assertIn("parry_post_ms", sql)
        self.assertIn("window_ms", sql)
        self.assertIn("'$.parry_pre_ms', 100", sql)
        self.assertIn("'$.parry_animation_ms', 450", sql)
        self.assertIn("'$.parry_post_ms', 100", sql)
        self.assertIn("'$.window_ms', 650", sql)
        self.assertIn("vulnerable_spell_id", sql)
        self.assertIn("deflected_spell_id", sql)
        self.assertIn("vulnerable_duration_ms", sql)
        self.assertIn("deflected_stun_ms_per_stack", sql)
        self.assertIn("max_vulnerable_stacks", sql)
        self.assertIn("counterattack_requires_aura", sql)
        self.assertIn("stance_aura_spell_id", sql)
        self.assertIn("stance_form_id", sql)
        self.assertIn("stance_bar_order", sql)
        self.assertIn("icon_id', 558", sql)
        self.assertIn("spell_wm_shell_dispatch", sql)
        self.assertIn("spell_cooldown_overrides", sql)
        self.assertIn("910180", sql)
        self.assertIn("910181", sql)
        self.assertIn("920104", sql)
        self.assertIn("920105", sql)
        self.assertIn("KilledMonsterCredit", repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8"))
        self.assertNotIn("insert into playercreateinfo", lowered)
        self.assertNotIn("insert into mod_learnspells", lowered)
        self.assertNotIn("update playercreateinfo", lowered)
        self.assertNotIn("update mod_learnspells", lowered)

    def test_native_runtime_hooks_broug_guard_through_unit_and_player_scripts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        runtime = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")
        unit_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_unit_scripts.cpp",
        ).read_text(encoding="utf-8")
        shell_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_shell_scripts.cpp",
        ).read_text(encoding="utf-8")
        player_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_player_scripts.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn("BROUG_UNIVERSAL_PARRY_SHELL_ID = 946800", runtime)
        self.assertIn("BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID = 946801", runtime)
        self.assertIn("BROUG_RETIRED_SKIRMISHER_TOGGLE_SHELL_ID = 946604", runtime)
        self.assertIn("BROUG_SKIRMISHER_MARK_SHELL_ID = 946098", runtime)
        self.assertIn("BROUG_VULNERABLE_SHELL_ID = 946200", runtime)
        self.assertIn("BROUG_DEFLECTED_SHELL_ID = 946201", runtime)
        self.assertIn("BROUG_DEFLECT_SHELL_ID = 946603", runtime)
        self.assertIn("BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID = 946605", runtime)
        self.assertIn("BROUG_AUTO_RETALIATION_SHELL_ID = 946802", runtime)
        self.assertIn("BROUG_PARRY_QUEST_ID = 910180", runtime)
        self.assertIn("BROUG_DEFLECT_QUEST_ID = 910181", runtime)
        self.assertIn("broug_universal_parry_v1", runtime)
        self.assertIn("broug_skirmisher_shot_v1", runtime)
        self.assertIn("broug_deflect_v1", runtime)
        self.assertIn("broug_deflect_counter_stance_v1", runtime)
        self.assertIn("broug_auto_retaliation_v1", runtime)
        self.assertIn("wm_broug_guard_counter", runtime)
        self.assertIn("ResolveBrougUniversalParryChance", runtime)
        self.assertIn("ResolveBrougUniversalParryExpertisePct", runtime)
        self.assertIn("ResolveBrougUniversalParryWeaponMasteryPct", runtime)
        self.assertIn("STAT_STRENGTH", runtime)
        self.assertIn("GetExpertiseDodgeOrParryReduction", runtime)
        self.assertIn("GetWeaponSkillValue(BASE_ATTACK", runtime)
        self.assertIn("BuildBrougSkirmisherDamageInfo", runtime)
        self.assertIn("CalculateDamage(RANGED_ATTACK", runtime)
        self.assertIn("PROC_FLAG_DONE_RANGED_AUTO_ATTACK", runtime)
        self.assertIn("ResolveBrougRangedEmote", runtime)
        self.assertIn("SHEATH_STATE_RANGED", runtime)
        self.assertIn("PlayBrougSkirmisherFeedback(player, rangedItem", runtime)
        self.assertIn("ExecuteBrougSkirmisherMark", runtime)
        self.assertIn("FireBrougSkirmisherShot", runtime)
        self.assertNotIn("TryBrougSkirmisherAutoAttack", runtime)
        self.assertIn("GetExplTargetUnit()", shell_script)
        self.assertIn("SPELL_EFFECT_SCHOOL_DAMAGE", shell_script)
        self.assertIn("SPELL_EFFECT_WEAPON_DAMAGE", shell_script)
        self.assertIn("SPELL_EFFECT_WEAPON_DAMAGE_NOSCHOOL", shell_script)
        self.assertIn("SPELL_EFFECT_WEAPON_PERCENT_DAMAGE", shell_script)
        self.assertIn("SPELL_EFFECT_NORMALIZED_WEAPON_DMG", shell_script)
        self.assertIn("ExecuteBrougDeflect", runtime)
        self.assertIn("parryPreMs = 100", header := repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.h",
        ).read_text(encoding="utf-8"))
        self.assertIn("parryAnimationMs = 450", header)
        self.assertIn("parryPostMs = 100", header)
        self.assertIn("windowMs = 650", header)
        self.assertIn("vulnerableSpellId = 946200", header)
        self.assertIn("deflectedSpellId = 946201", header)
        self.assertIn("vulnerableDurationMs = 60000", header)
        self.assertIn("maxVulnerableStacks = 255", header)
        self.assertIn("counterattackEnabledDefault = false", header)
        self.assertIn("deflectPendingResolveAtMs", runtime)
        self.assertIn("deflectRootUntilMs", runtime)
        self.assertIn("deflectParryFeedbackAtMs", runtime)
        self.assertIn("deflectCaughtStacksByAttacker", runtime)
        self.assertIn("IsBrougDeflectCounterStanceActive", runtime)
        self.assertIn("player->HasAura(BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID)", runtime)
        self.assertIn("gBrougCounterStanceToggleOffByPlayer", runtime)
        self.assertIn("ShouldAllowShellDefaultEffect", runtime)
        self.assertIn("ShouldAllowShellDefaultEffect(Player const* player", runtime)
        self.assertIn("ShouldAllowShellDefaultEffect", shell_script)
        self.assertIn("Counterstrike Stance inactive", runtime)
        self.assertNotIn("deflectCounterattackEnabled", runtime)
        self.assertNotIn("LoadStoredBrougDeflectCounterattackEnabled", runtime)
        self.assertNotIn("StoreBrougDeflectCounterattackEnabled", runtime)
        self.assertIn("ExecuteBrougDeflectCounterStance", runtime)
        self.assertIn("if (!counterattackEnabled)", runtime)
        self.assertIn("IsBrougDeflectWindowActive", runtime)
        self.assertIn("ApplyBrougVulnerableStack", runtime)
        self.assertIn("ConsumeBrougVulnerableForDamage", runtime)
        self.assertIn("ApplyBrougDeflectedStacks", runtime)
        self.assertIn("ApplyBrougVisibleAura", runtime)
        self.assertIn("Aura::TryCreate", runtime)
        self.assertIn("HasBrougDeflectedAura", runtime)
        self.assertIn("EnsureBrougDeflectedStun", runtime)
        self.assertIn("gBrougDeflectedStunUnits", runtime)
        self.assertIn("ReleaseBrougForcedStun", runtime)
        self.assertIn("RestartBrougStunnedCreature", runtime)
        self.assertIn("CaptureBrougDeflectEvent", runtime)
        self.assertIn("ResolveBrougDeflectCounterTarget", runtime)
        self.assertIn("DealBrougDeflectCounterDamage", runtime)
        self.assertIn("PlayBrougDeflectStrikeFeedback(player, target)", runtime)
        self.assertIn("HandleEmoteCommand(ResolveBrougAttackEmote(player))", runtime)
        self.assertIn("player->SendMeleeAttackStart(target)", runtime)
        self.assertIn("player->SendAttackStateUpdate(&damageInfo)", runtime)
        self.assertIn("player->DealMeleeDamage(&damageInfo, true)", runtime)
        self.assertIn("player->SendMeleeAttackStop(target)", runtime)
        self.assertIn("gBrougPendingForcedParryByVictim.erase(player->GetGUID())", runtime)
        self.assertIn("SetControlled(true, UNIT_STATE_STUNNED", runtime)
        self.assertIn("SetControlled(true, UNIT_STATE_ROOT", runtime)
        self.assertIn("SetControlled(false, UNIT_STATE_ROOT", runtime)
        self.assertIn("target->CastStop()", runtime)
        self.assertIn("target->StopMoving()", runtime)
        self.assertIn("target && target->HasAura(BROUG_DEFLECTED_SHELL_ID)", runtime)
        self.assertIn("if (HasBrougDeflectedAura(unit))", runtime)
        self.assertIn("HandleBrougGuardAuraApply", runtime)
        self.assertIn("HandleBrougGuardAuraRemove", runtime)
        self.assertIn("spellInfo->IsPositive()", runtime)
        self.assertIn("aura->Remove(AURA_REMOVE_BY_DEFAULT)", runtime)
        self.assertIn("ModifySpellDamageTaken covers single-target spells and direct AoE hits", runtime)
        self.assertIn("UNITHOOK_ON_AURA_APPLY", unit_script)
        self.assertIn("UNITHOOK_ON_AURA_REMOVE", unit_script)
        self.assertIn("TryQueueBrougUniversalMeleeParry(attacker, victim, damage, true)", runtime)
        self.assertIn("HandleBrougGuardMeleeOutcome", runtime)
        self.assertIn("gBrougPendingForcedParryByVictim", runtime)
        self.assertIn("parry_chance = std::max<int32>(parry_chance, 30000)", runtime)
        self.assertIn("SPELL_MISS_PARRY", runtime)
        self.assertIn("EMOTE_ONESHOT_PARRY", runtime)
        self.assertIn("EMOTE_ONESHOT_ATTACK_THROWN", runtime)
        self.assertIn("player->KilledMonsterCredit(creditCreatureEntry)", runtime)
        self.assertIn("CreditBrougQuestProgress(player, BROUG_PARRY_CREDIT_CREATURE_ENTRY)", runtime)
        self.assertIn("CreditBrougQuestProgress(player, BROUG_DEFLECT_CREDIT_CREATURE_ENTRY)", runtime)
        self.assertIn("CanCompleteBrougGuardQuest", runtime)
        self.assertIn("HandleBrougGuardQuestComplete", runtime)
        self.assertIn("UNIT_FIELD_RANGED_ATTACK_POWER", runtime)
        self.assertIn("UNITHOOK_MODIFY_PERIODIC_DAMAGE_AURAS_TICK", unit_script)
        self.assertIn("HandleBrougGuardMeleeDamage(attacker, target, damage)", unit_script)
        self.assertIn("HandleBrougGuardSpellDamage(attacker, target, damage, spellInfo)", unit_script)
        self.assertIn("HandleBrougGuardPeriodicDamage(attacker, target, damage, spellInfo)", unit_script)
        self.assertIn("HandleBrougGuardAuraApply(unit, aura)", unit_script)
        self.assertIn("HandleBrougGuardAuraRemove(unit, aurApp, mode)", unit_script)
        self.assertIn("HandleBrougGuardMeleeOutcome", unit_script)
        self.assertIn("TickBrougGuard(player, diff)", player_script)
        self.assertIn("MaintainBrougGuard(player", player_script)
        self.assertIn("ForgetBrougGuard(player)", player_script)
        self.assertIn("OnPlayerBeforeQuestComplete", player_script)
        self.assertIn("OnPlayerCompleteQuest", player_script)


if __name__ == "__main__":
    unittest.main()
