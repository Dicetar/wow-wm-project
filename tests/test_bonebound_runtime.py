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


if __name__ == "__main__":
    unittest.main()
