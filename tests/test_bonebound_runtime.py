import unittest
from pathlib import Path


class BoneboundRuntimeStaticTests(unittest.TestCase):
    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def test_alpha_v3_is_single_alpha_with_native_abilities(self) -> None:
        runtime = self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn('behaviorKind == "summon_bonebound_alpha_v3"', runtime)
        self.assertIn("config.spawnOmega = false;", runtime)
        self.assertIn("MaintainBoneboundAlphaAbilities(owner, alphaPet, *runtimeConfig, 1000u)", runtime)
        self.assertIn("StartBoneboundShadowDot(owner, alphaPet, victim, config)", runtime)
        self.assertIn("TrySpawnBoneboundAlphaEcho(owner, alphaPet, victim, *runtimeConfig)", runtime)
        self.assertIn("roll_chance_f(procChance)", runtime)
        self.assertIn("Unit::DealDamage(caster, target, it->tickDamage, nullptr, DOT, SPELL_SCHOOL_MASK_NORMAL", runtime)
        self.assertIn("config.shadowDotCooldownMs = *value;", runtime)
        self.assertIn("float alphaEchoProcChancePct = 7.5f;", self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.h",
        ).read_text(encoding="utf-8"))
        self.assertIn("uint32 alphaEchoMaxActive = 40;", self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.h",
        ).read_text(encoding="utf-8"))
        self.assertIn("uint32 shadowDotCooldownMs = 6000;", self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.h",
        ).read_text(encoding="utf-8"))

    def test_alpha_echo_damage_is_runtime_hooked_not_visible_field_copy(self) -> None:
        repo_root = self._repo_root()
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
        loader = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "mod_wm_spells_loader.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn("void HandleBoneboundMeleeDamage(Unit* attacker, Unit* victim, uint32& damage)", runtime)
        self.assertIn("damage = std::max<uint32>(damage, scaledRoll)", runtime)
        self.assertIn("uint32 echoEntry = config.alphaEchoCreatureEntry != 0 ? config.alphaEchoCreatureEntry : config.creatureEntry;", runtime)
        self.assertIn("RandomAlphaEchoFollowAngle()", runtime)
        self.assertIn("CopyAlphaFinalStatsToEcho(alphaPet, echo, true)", runtime)
        self.assertIn("ApplyOwnerTransferBonuses(echo, owner, config, false)", runtime)
        self.assertIn("ModifyMeleeDamage(Unit* target, Unit* attacker, uint32& damage) override", unit_script)
        self.assertIn("WmSpells::HandleBoneboundMeleeDamage(attacker, target, damage)", unit_script)
        self.assertIn("AddSC_mod_wm_spells_unit_scripts", loader)

    def test_alpha_echoes_survive_mount_temporary_unsummon(self) -> None:
        runtime = self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn("uint32 creatureEntry = 0;", runtime)
        self.assertIn("TempSummon* SpawnBoneboundAlphaEchoFromState", runtime)
        self.assertIn("owner->IsPetNeedBeTemporaryUnsummoned()", runtime)
        self.assertIn("Keep the Echo state alive until the main Bonebound pet can return.", runtime)
        self.assertIn("RestoreTemporarilyUnsummonedBoneboundPet(owner)", runtime)
        self.assertIn(
            "if (owner->IsPetNeedBeTemporaryUnsummoned())\n"
            "            {\n"
            "                RemoveBoneboundOmega(owner);\n"
            "                return;\n"
            "            }\n\n"
            "            RemoveBoneboundAlphaEchoes(owner);",
            runtime,
        )
        self.assertIn("gBoneboundAlphaEchoes[static_cast<uint32>(restored->GetGUID().GetCounter())] = state;", runtime)

    def test_alpha_echo_sql_uses_wm_template_and_bleed_tuning(self) -> None:
        sql = self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_16_00_wm_spell_bonebound_alpha_abilities.sql",
        ).read_text(encoding="utf-8")

        self.assertIn("SET @wm_alpha_echo_creature_entry := 920101;", sql)
        self.assertIn("name = 'Bonebound Alpha Echo'", sql)
        self.assertIn('"shadow_dot_cooldown_ms":6000', sql)
        self.assertIn('"shadow_dot_tick_ms":1000', sql)
        self.assertIn('"shadow_dot_damage_per_shadow_power_pct":0', sql)
        self.assertIn('"alpha_echo_creature_entry":920101', sql)
        self.assertIn('"alpha_echo_proc_chance_pct":7.5', sql)
        self.assertIn('"alpha_echo_max_active":40', sql)

    def test_night_watchers_lens_tracks_refreshed_visible_target_debuff(self) -> None:
        repo_root = self._repo_root()
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
        unit_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_unit_scripts.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn("constexpr uint32 NIGHT_WATCHERS_LENS_ITEM_ENTRY = 910006;", runtime)
        self.assertIn("constexpr uint32 NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID = 132;", runtime)
        self.assertIn("constexpr uint32 NIGHT_WATCHERS_LENS_MARK_DEBUFF_SPELL_ID = 770;", runtime)
        self.assertIn("constexpr uint32 NIGHT_WATCHERS_LENS_MARK_DURATION_MS = 10000;", runtime)
        self.assertIn("constexpr float NIGHT_WATCHERS_LENS_PROC_CHANCE_PCT = 10.0f;", runtime)
        self.assertIn("std::unordered_map<uint64, NightWatchersLensMarkState> gNightWatchersLensMarksByTarget;", runtime)
        self.assertIn("player->HasAura(NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID)", runtime)
        self.assertIn("bool RefreshNightWatchersLensMark(Player* caster, Unit* target)", runtime)
        self.assertIn("aura->SetMaxDuration(static_cast<int32>(NIGHT_WATCHERS_LENS_MARK_DURATION_MS));", runtime)
        self.assertIn("aura->SetDuration(static_cast<int32>(NIGHT_WATCHERS_LENS_MARK_DURATION_MS));", runtime)
        self.assertIn("gNightWatchersLensMarksByTarget[target->GetGUID().GetRawValue()] =", runtime)
        self.assertIn("bool IsNightWatchersLensWandShot(SpellInfo const* spellInfo)", runtime)
        self.assertIn("spellInfo->EquippedItemClass == ITEM_CLASS_WEAPON", runtime)
        self.assertIn("ITEM_SUBCLASS_WEAPON_WAND", runtime)
        self.assertIn("spellInfo->HasAttribute(SPELL_ATTR2_AUTO_REPEAT)", runtime)
        self.assertIn("bool TryProcNightWatchersLensMark(Unit* attacker, Unit* victim, uint32 damage)", runtime)
        self.assertIn("void HandleNightWatchersLensWeaponDamage(Unit* attacker, Unit* victim, uint32& damage)", runtime)
        self.assertIn("void HandleNightWatchersLensSpellDamage(Unit* attacker, Unit* victim, int32& damage, SpellInfo const* spellInfo)", runtime)
        self.assertIn("if (IsNightWatchersLensMarked(victim))", runtime)
        self.assertIn("procChance = std::clamp(procChance * NIGHT_WATCHERS_LENS_MARK_PROC_MULTIPLIER, 0.0f, 100.0f);", runtime)
        self.assertIn("victimMaxSkillValueForLevel = HalveNightWatchersLensDefenseValue(victimMaxSkillValueForLevel);", runtime)
        self.assertIn("victimDefenseSkill = HalveNightWatchersLensDefenseValue(victimDefenseSkill);", runtime)
        self.assertIn("miss_chance = HalveNightWatchersLensDefenseValue(miss_chance);", runtime)
        self.assertIn("dodge_chance = HalveNightWatchersLensDefenseValue(dodge_chance);", runtime)
        self.assertIn("parry_chance = HalveNightWatchersLensDefenseValue(parry_chance);", runtime)
        self.assertIn("block_chance = HalveNightWatchersLensDefenseValue(block_chance);", runtime)
        self.assertIn("crit_chance = std::clamp<int32>(crit_chance * 2, 0, 10000);", runtime)
        self.assertNotIn("void HandleNightWatchersLensDamage", runtime)
        self.assertIn("WmSpells::MaintainNightWatchersLens(player, BONEBOUND_MAINTENANCE_INTERVAL_MS)", player_script)
        self.assertIn("OnPlayerEquip(Player* player, Item* item", player_script)
        self.assertIn("OnPlayerUnequip(Player* player, Item* item) override", player_script)
        self.assertNotIn("UNITHOOK_ON_DAMAGE", unit_script)
        self.assertIn("UNITHOOK_MODIFY_SPELL_DAMAGE_TAKEN", unit_script)
        self.assertIn("UNITHOOK_ON_BEFORE_ROLL_MELEE_OUTCOME_AGAINST", unit_script)
        self.assertIn("WmSpells::HandleNightWatchersLensWeaponDamage(attacker, target, damage)", unit_script)
        self.assertIn("WmSpells::HandleNightWatchersLensSpellDamage(attacker, target, damage, spellInfo)", unit_script)
        self.assertIn("WmSpells::HandleNightWatchersLensDefenseExposure(", unit_script)


if __name__ == "__main__":
    unittest.main()
