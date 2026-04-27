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
        self.assertIn("gConfig.boneboundCreatureEntry = sConfigMgr->GetOption<uint32>(\"WmSpells.BoneboundServant.CreatureEntry\", 920100u);", runtime)
        self.assertIn("MaintainBoneboundAlphaAbilities(owner, alphaPet, *runtimeConfig, 1000u)", runtime)
        self.assertIn("BONEBOUND_BLEED_VISIBLE_AURA_SPELL_ID = 772", runtime)
        self.assertIn("StartBoneboundBleed(owner, alphaPet, victim, *runtimeConfig, 100u)", runtime)
        self.assertIn("ApplyBoneboundBleedVisibleAura(caster, target, durationMs)", runtime)
        self.assertIn("effect->SetAmount(0);", runtime)
        self.assertIn("effect->SetPeriodic(false);", runtime)
        self.assertIn("HasBoneboundBleedVisibleAura(caster, target)", runtime)
        self.assertIn("gBoneboundBleedCooldownByCaster", runtime)
        self.assertIn("UpdateBoneboundBleedCooldowns(diff);", runtime)
        self.assertIn("TryBoneboundCleave(owner, alphaPet, victim, *runtimeConfig, damage, runtimeConfig->alphaCleaveDamagePct);", runtime)
        self.assertIn("TryBoneboundCleave(owner, attacker, victim, *runtimeConfig, scaledRoll, runtimeConfig->echoCleaveDamagePct);", runtime)
        self.assertIn("UpdateBoneboundCleaveCooldowns(diff);", runtime)
        self.assertIn("BONEBOUND_SLASH_SPELL_ID = 945000", runtime)
        self.assertIn("caster->CastCustomSpell(", runtime)
        self.assertIn("SPELLVALUE_BASE_POINT0", runtime)
        self.assertIn("result != SPELL_CAST_OK", runtime)
        self.assertIn("SeedBoneboundOwnerKillCredit(owner, victim, damage);", runtime)
        self.assertIn("SeedBoneboundOwnerKillCredit(owner, victim, scaledRoll);", runtime)
        self.assertIn("SeedBoneboundOwnerKillCredit(owner, target, it->tickDamage);", runtime)
        self.assertIn("creature->SetLootRecipient(owner, true);", runtime)
        self.assertIn("creature->LowerPlayerDamageReq(damageCredit, true);", runtime)
        self.assertIn("TrySpawnBoneboundAlphaEcho(owner, alphaPet, victim, *runtimeConfig)", runtime)
        self.assertIn("roll_chance_f(procChance)", runtime)
        self.assertIn("Unit::DealDamage(caster, target, it->tickDamage, nullptr, DOT, SPELL_SCHOOL_MASK_NORMAL", runtime)
        self.assertIn("ResolveBoneboundCasterAttackPower(caster)", runtime)
        self.assertIn("UNIT_FIELD_ATTACK_POWER", runtime)
        self.assertIn("config.bleedDamagePerAttackPowerPct = *value;", runtime)
        self.assertIn("config.bleedCooldownMs = *value;", runtime)
        self.assertIn('ExtractJsonUInt(configJson, "shadow_dot_cooldown_ms")', runtime)
        self.assertIn('ExtractJsonUInt(configJson, "bleed_damage_per_attack_power_pct")', runtime)
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
        self.assertIn("uint32 bleedDamagePerAttackPowerPct = 20;", self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.h",
        ).read_text(encoding="utf-8"))
        self.assertIn("uint32 bleedCooldownMs = 6000;", self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.h",
        ).read_text(encoding="utf-8"))
        self.assertIn("uint32 cleaveCooldownMs = 3000;", self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.h",
        ).read_text(encoding="utf-8"))
        self.assertIn("float alphaEchoHuntRadius = 35.0f;", self._repo_root().joinpath(
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
        self.assertIn("uint32 echoEntry = priestEcho", runtime)
        self.assertIn(": (config.alphaEchoCreatureEntry != 0 ? config.alphaEchoCreatureEntry : config.creatureEntry);", runtime)
        self.assertIn("ResolveBoneboundEchoFormationSlot(", runtime)
        self.assertIn("CopyAlphaFinalStatsToEcho(alphaPet, echo, refillHealth)", runtime)
        self.assertIn("void MatchBoneboundEchoMovementSpeed(Pet* alphaPet, TempSummon* echo)", runtime)
        self.assertIn("echo->SetWalk(false);", runtime)
        self.assertIn("echo->SetSpeed(MOVE_RUN, alphaPet->GetSpeedRate(MOVE_RUN), true);", runtime)
        self.assertIn("MatchBoneboundEchoMovementSpeed(alphaPet, echo);", runtime)
        self.assertIn("ApplyBoneboundAlphaEchoRuntime(owner, alphaPet, echo->ToTempSummon(), it->second, *runtimeConfig, false)", runtime)
        self.assertIn("echo->SetCreateHealth(desiredMaxHealth);", runtime)
        self.assertIn("echo->SetLevel(alphaPet->GetLevel());", runtime)
        self.assertIn("ApplyOwnerTransferBonuses(echo, owner, config, false)", runtime)
        self.assertIn("ModifyMeleeDamage(Unit* target, Unit* attacker, uint32& damage) override", unit_script)
        self.assertIn("WmSpells::HandleBoneboundMeleeDamage(attacker, target, damage)", unit_script)
        self.assertIn("AddSC_mod_wm_spells_unit_scripts", loader)

    def test_alpha_echo_melee_applies_independent_bleed_state(self) -> None:
        runtime = self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn("auto echoIt = gBoneboundAlphaEchoes.find(static_cast<uint32>(attacker->GetGUID().GetCounter()));", runtime)
        self.assertIn("uint32 echoGuid = static_cast<uint32>(attacker->GetGUID().GetCounter());", runtime)
        self.assertIn("uint32& bleedCooldown = gBoneboundBleedCooldownByCaster[echoGuid];", runtime)
        self.assertIn("StartBoneboundBleed(owner, attacker, victim, *runtimeConfig, echoIt->second.damagePct);", runtime)
        self.assertIn("uint32 ResolveBoneboundBleedTickDamage(Player* owner, Unit* caster, WmSpells::BoneboundBehaviorConfig const& config, uint32 damagePct)", runtime)
        self.assertIn("uint32 tickDamage = ResolveBoneboundBleedTickDamage(owner, caster, config, damagePct);", runtime)
        self.assertIn("if (bleed.casterGuid == caster->GetGUID() && bleed.targetGuid == target->GetGUID())", runtime)
        self.assertIn("bleed.casterGuid = caster->GetGUID();", runtime)
        self.assertIn("bleed.targetGuid = target->GetGUID();", runtime)

    def test_alpha_echoes_reacquire_alpha_victim_when_follow_motion_sticks(self) -> None:
        runtime = self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")

        self.assertIn("void CommandBoneboundAlphaEchoAttack(Creature* echo, Unit* victim)", runtime)
        self.assertIn("echo->AddThreat(victim, 25.0f);", runtime)
        self.assertIn("echo->SetInCombatWith(victim);", runtime)
        self.assertIn("victim->SetInCombatWith(echo);", runtime)
        self.assertIn("echo->AI()->AttackStart(victim);", runtime)
        self.assertIn("echo->Attack(victim, true);", runtime)
        self.assertIn("echo->GetMotionMaster()->MoveChase(victim);", runtime)
        self.assertIn("CommandBoneboundAlphaEchoAttack(echo, victim);", runtime)
        self.assertIn("IsBoneboundEchoHuntMode(it->second.ownerGuid)", runtime)
        self.assertIn("float ResolveBoneboundEchoHuntRadius(uint32 ownerGuid, std::optional<WmSpells::BoneboundBehaviorConfig> const& runtimeConfig)", runtime)
        self.assertIn("Unit* SelectNearestBoneboundSeekTarget(Player* owner, Creature* seeker, float radius)", runtime)
        self.assertIn("Acore::AnyUnfriendlyUnitInObjectRangeCheck check(owner, owner, radius);", runtime)
        self.assertIn("float distance = owner->GetDistance(candidate);", runtime)
        self.assertIn("victim = SelectNearestBoneboundSeekTarget(owner, echo, huntRadius);", runtime)

    def test_priest_echo_variant_is_role_based_and_visible_spell_casting(self) -> None:
        repo_root = self._repo_root()
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
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_26_02_wm_spell_bonebound_priest_echo.sql",
        ).read_text(encoding="utf-8")
        retune_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_26_05_wm_spell_echo_restorer_mind_blast_retune.sql",
        ).read_text(encoding="utf-8")
        positioning_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_26_06_wm_spell_echo_restorer_positioning.sql",
        ).read_text(encoding="utf-8")
        speed_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_26_07_wm_spell_echo_restorer_speed_match.sql",
        ).read_text(encoding="utf-8")
        seek_range_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_26_08_wm_spell_echo_restorer_seek_teleport_range.sql",
        ).read_text(encoding="utf-8")

        self.assertIn("enum class BoneboundEchoRole", runtime)
        self.assertIn("BoneboundEchoRole::Priest", runtime)
        self.assertIn("bool IsBoneboundPriestEcho(BoneboundAlphaEchoState const& state)", runtime)
        self.assertIn("state.role = priestEcho ? BoneboundEchoRole::Priest : BoneboundEchoRole::Warrior;", runtime)
        self.assertIn("float priestProcChance = runtimeConfig->priestEchoEnabled", runtime)
        self.assertIn("std::clamp(runtimeConfig->priestEchoProcChancePct, 0.0f, 100.0f)", runtime)
        self.assertIn("CountActiveBoneboundPriestEchoes(ownerGuid)", runtime)
        self.assertIn("CountActiveBoneboundWarriorEchoes(ownerGuid)", runtime)
        self.assertIn("uint32 priestPityThreshold = std::max<uint32>(1u, runtimeConfig->priestEchoPityAfterWarriorSpawns);", runtime)
        self.assertIn("gBoneboundWarriorEchoesSincePriestByPlayer[ownerGuid] = std::min<uint32>(priestPityThreshold, warriorSpawnsSincePriest + 1);", runtime)
        self.assertIn("TrySpawnBoneboundAlphaEcho(owner, alphaPet, victim, *runtimeConfig, BoneboundEchoRole::Priest);", runtime)
        self.assertIn("UpdateBoneboundPriestEcho(echo, owner, alphaPet, it->second, *runtimeConfig, diff);", runtime)
        self.assertIn("Unit* SelectBoneboundPriestSupportTarget(", runtime)
        self.assertIn("for (GroupReference* ref = group->GetFirstMember(); ref; ref = ref->next())", runtime)
        self.assertIn("TryCastBoneboundPriestEchoSpell(priestEcho, hurtTarget, config.priestEchoHealSpellId, healAmount)", runtime)
        self.assertIn("TryCastBoneboundPriestEchoSpell(priestEcho, hurtTarget, config.priestEchoRenewSpellId, renewAmount)", runtime)
        self.assertIn("TryCastBoneboundPriestEchoSpell(priestEcho, shieldTarget, config.priestEchoShieldSpellId, shieldAmount)", runtime)
        self.assertIn("TryStartBoneboundPriestDpsCast(priestEcho, enemy, owner, config, damage)", runtime)
        self.assertIn("BoneboundPriestDpsCastState", runtime)
        self.assertIn("bool damageIsNativeSpellHit = damageSpellId == config.priestEchoDpsSpellId;", runtime)
        self.assertIn("SpellCastResult result = priestEcho->CastCustomSpell(", runtime)
        self.assertIn("ClampSpellBasePoint(std::max<uint32>(1u, damage))", runtime)
        self.assertIn("target,\n                false);", runtime)
        self.assertIn("float ResolveBoneboundPriestDpsMaxRange(WmSpells::BoneboundBehaviorConfig const& config)", runtime)
        self.assertIn("float ResolveBoneboundPriestVisibleDpsCastRange(Creature* priestEcho, WmSpells::BoneboundBehaviorConfig const& config)", runtime)
        self.assertIn("config.priestEchoDpsMaxRange = *value;", runtime)
        self.assertIn('ExtractJsonFloat(configJson, "priest_echo_dps_max_range")', runtime)
        self.assertIn("float visibleCastRange = ResolveBoneboundPriestVisibleDpsCastRange(priestEcho, config);", runtime)
        self.assertIn("if (!priestEcho->IsWithinDistInMap(target, visibleCastRange))", runtime)
        self.assertIn("if (!priestEcho->IsWithinLOSInMap(target))", runtime)
        self.assertIn("ClampSpellBasePoint(castState.damage)", runtime)
        self.assertIn("SeedBoneboundOwnerKillCredit(owner, target, damage);", runtime)
        self.assertIn("SpellNonMeleeDamage damageInfo(priestEcho, target, spellInfo, SPELL_SCHOOL_MASK_SHADOW);", runtime)
        self.assertIn("priestEcho->CastSpell(target, config.priestEchoDpsSpellId, false)", runtime)
        self.assertIn("gBoneboundPriestDpsCastByCaster", runtime)
        self.assertIn("echo->SetReactState(priestEcho ? REACT_PASSIVE : REACT_DEFENSIVE);", runtime)
        self.assertIn("Unit* SelectBoneboundPriestShieldTarget(", runtime)
        self.assertIn("IsBoneboundPriestTargetUnderThreat(candidate)", runtime)
        self.assertIn("TryBoneboundPriestMassDispel(priestEcho, supportTargets, config, massDispelCooldown);", runtime)
        self.assertIn("TryBoneboundPriestSingleDispel(priestEcho, supportTargets, config, dispelCooldown);", runtime)
        self.assertIn("CollectBoneboundPriestDispelCandidates(supportTargets, true)", runtime)
        self.assertIn("spellInfo->Dispel == DISPEL_DISEASE || spellInfo->Dispel == DISPEL_CURSE", runtime)
        self.assertIn("spellInfo->Dispel == DISPEL_MAGIC || spellInfo->Dispel == DISPEL_POISON", runtime)
        self.assertIn("MoveBoneboundPriestEchoToSafePosition(priestEcho, owner, enemy, state, config);", runtime)
        self.assertIn("enemy && IsBoneboundEchoHuntMode(state.ownerGuid)", runtime)
        self.assertIn("priestEcho->GetMotionMaster()->MoveFollow(enemy, seekDistance, state.followAngle);", runtime)
        self.assertIn("void CommandBoneboundPriestEchoSeek(Creature* priestEcho, Unit* victim)", runtime)
        self.assertIn("CommandBoneboundPriestEchoSeek(priestEcho, enemy);", runtime)
        self.assertIn("CommandBoneboundPriestEchoSeek(echo, enemy);", runtime)
        self.assertIn("BoneboundEchoFormationSlot formationSlot = ResolveBoneboundEchoFormationSlot(", runtime)
        self.assertIn("state.followDistance = formationSlot.followDistance;", runtime)
        self.assertIn("damage = 0;", runtime)
        self.assertIn("AddBoneboundPriestSpellPowerBonus(", runtime)
        self.assertIn("owner->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW)", runtime)
        self.assertIn("config.priestEchoSpellPowerToDamagePct", runtime)
        self.assertIn("uint32 ResolveBoneboundPriestEchoStaffItem(WmSpells::BoneboundBehaviorConfig const& config)", runtime)
        self.assertIn("state.virtualItem1 = priestEcho ? ResolveBoneboundPriestEchoStaffItem(config) : 0;", runtime)
        self.assertIn('ExtractJsonUIntArray(configJson, "priest_echo_staff_item_entries")', runtime)
        self.assertIn('ExtractJsonString(configJson, "alpha_echo_name")', runtime)
        self.assertIn("std::string const& name = priestEcho ? config.priestEchoName : config.alphaEchoName;", runtime)
        self.assertIn("bool nameChanged = creature->GetName() != name;", runtime)
        self.assertIn("creature->UpdateObjectVisibility();", runtime)
        self.assertIn('std::string alphaEchoName = "Echo Destroyer";', header)
        self.assertIn('std::string priestEchoName = "Echo Restorer";', header)
        self.assertIn("priestEchoDpsSpellId = 8092", header)
        self.assertIn("uint32 priestEchoDpsDamageSpellId = 8092;", header)
        self.assertIn("uint32 priestEchoDpsCastTimeMs = 1500;", header)
        self.assertIn("uint32 priestEchoDpsDamagePct = 19;", header)
        self.assertIn("uint32 priestEchoDpsCooldownMs = 2500;", header)
        self.assertIn("float priestEchoDpsMaxRange = 100.0f;", header)
        self.assertIn("uint32 priestEchoCreatureEntry = 920103;", header)
        self.assertIn("uint32 priestEchoDisplayId = 11397;", header)
        self.assertIn("float priestEchoProcChancePct = 5.0f;", header)
        self.assertIn("uint32 priestEchoMaxActive = 10;", header)
        self.assertIn("uint32 priestEchoPityAfterWarriorSpawns = 6;", header)
        self.assertIn("std::vector<uint32> priestEchoStaffItemEntries = {18842, 22800, 19909, 21275, 21452, 22335, 19570, 19566};", header)
        self.assertIn("uint32 priestEchoHealSpellId = 2061;", header)
        self.assertIn("uint32 priestEchoRenewSpellId = 139;", header)
        self.assertIn("uint32 priestEchoShieldSpellId = 17;", header)
        self.assertIn("uint32 priestEchoDiseaseDispelSpellId = 528;", header)
        self.assertIn("uint32 priestEchoCurseDispelSpellId = 475;", header)
        self.assertIn("uint32 priestEchoMassDispelSpellId = 32375;", header)
        self.assertIn("uint32 priestEchoMassDispelCooldownMs = 180000;", header)
        self.assertIn("uint32 priestEchoSpellPowerToDamagePct = 45;", header)
        self.assertIn("float priestEchoSafeFollowDistance = 1.8f;", header)
        self.assertIn("float priestEchoSafeMinEnemyDistance = 6.0f;", header)
        self.assertIn("SET @wm_priest_echo_creature_entry := 920103;", sql)
        self.assertIn("SET @wm_priest_echo_model_source_entry := 15121;", sql)
        self.assertIn("name = 'Echo Restorer'", sql)
        self.assertIn("'$.alpha_echo_name', 'Echo Destroyer'", sql)
        self.assertIn("'$.priest_echo_name', 'Echo Restorer'", sql)
        self.assertIn("'$.priest_echo_display_id', 11397", sql)
        self.assertIn("'$.priest_echo_staff_item_entries', JSON_ARRAY(18842, 22800, 19909, 21275, 21452, 22335, 19570, 19566)", sql)
        self.assertIn("'$.priest_echo_proc_chance_pct', 5.0", sql)
        self.assertIn("'$.priest_echo_max_active', 10", sql)
        self.assertIn("'$.priest_echo_pity_after_warrior_spawns', 6", sql)
        self.assertIn("'$.priest_echo_mass_dispel_cooldown_ms', 180000", sql)
        self.assertIn("'$.priest_echo_mass_dispel_min_affected', 3", sql)
        self.assertIn("'$.priest_echo_safe_follow_distance', 1.8", positioning_sql)
        self.assertIn("'$.priest_echo_safe_min_enemy_distance', 6.0", positioning_sql)
        self.assertIn("'$.priest_echo_dps_spell_id', 8092", retune_sql)
        self.assertIn("'$.priest_echo_dps_damage_spell_id', 8092", retune_sql)
        self.assertIn("'$.priest_echo_dps_cast_time_ms', 1500", retune_sql)
        self.assertIn("'$.priest_echo_dps_damage_pct', 19", retune_sql)
        self.assertIn("'$.priest_echo_dps_cooldown_ms', 2500", retune_sql)
        self.assertIn("'$.priest_echo_spell_power_to_damage_pct', 45", retune_sql)
        self.assertIn("SET @wm_alpha_echo_creature_entry := 920101;", speed_sql)
        self.assertIn("SET @wm_priest_echo_creature_entry := 920103;", speed_sql)
        self.assertIn("restorer.speed_walk = destroyer.speed_walk", speed_sql)
        self.assertIn("restorer.speed_run = destroyer.speed_run", speed_sql)
        self.assertIn("'$.priest_echo_dps_max_range', 100.0", seek_range_sql)

    def test_alpha_echo_mode_command_and_count_aura_are_runtime_owned(self) -> None:
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
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_26_00_wm_spell_bonebound_echo_control_cleave.sql",
        ).read_text(encoding="utf-8")

        self.assertIn('behaviorKind == "bonebound_echo_mode_v1"', runtime)
        self.assertIn("BehaviorExecutionResult ExecuteBoneboundEchoMode(Player* player, std::string const& mode, std::optional<float> huntRadiusOverride)", runtime)
        self.assertIn("BehaviorExecutionResult ExecuteBoneboundEchoSeekRange(Player* player, float huntRadius)", runtime)
        self.assertIn("BehaviorExecutionResult ExecuteBoneboundEchoTeleport(Player* player)", runtime)
        self.assertIn('normalized == "teleport" || normalized == "tp" || normalized == "recall"', runtime)
        self.assertIn("echo->NearTeleportTo(x, y, z, player->GetOrientation());", runtime)
        self.assertIn("gBoneboundPriestDpsCastByCaster.erase(echoGuid);", runtime)
        self.assertIn('"bonebound_echo_teleported:" + std::to_string(teleported)', runtime)
        self.assertIn('normalized == "hunt"', runtime)
        self.assertIn('normalized == "follow"', runtime)
        self.assertIn("gBoneboundEchoHuntRadiusByPlayer[ownerGuid] = clampedRadius;", runtime)
        self.assertIn("ExecuteBoneboundEchoMode(player, mode, huntRadius)", runtime)
        self.assertIn('ExtractJsonFloat(payloadJson, "hunt_radius")', runtime)
        self.assertIn("gBoneboundEchoHuntModeByPlayer[ownerGuid] = huntMode;", runtime)
        self.assertIn("RefreshBoneboundEchoCountAura(owner, *runtimeConfig);", runtime)
        self.assertIn("BONEBOUND_ECHO_COUNT_DEFAULT_AURA_SPELL_ID = 467", runtime)
        self.assertIn("BONEBOUND_ECHO_MIN_FOLLOW_SEPARATION_YARDS = 1.6f", runtime)
        self.assertIn("BoneboundEchoFormationRingCapacity(float followDistance)", runtime)
        self.assertIn("ResolveBoneboundEchoFormationSlot(", runtime)
        self.assertIn("RefreshBoneboundEchoFormationSlots(Player* owner, WmSpells::BoneboundBehaviorConfig const& config)", runtime)
        self.assertIn("followDistance += BONEBOUND_ECHO_MIN_FOLLOW_SEPARATION_YARDS;", runtime)
        self.assertIn("RefreshBoneboundEchoFormationSlots(owner, config);", runtime)
        self.assertIn("aura->SetMaxDuration(-1);", runtime)
        self.assertIn("aura->SetDuration(-1);", runtime)
        self.assertIn("aura->SetStackAmount(static_cast<uint8>(std::min<uint32>(255u, activeCount)));", runtime)
        self.assertIn("StripAuraEffects(aura);", runtime)
        self.assertIn("ExtractJsonString(payloadJson, \"mode\")", runtime)
        self.assertIn('"bonebound_echo_mode_v1"', runtime)
        self.assertIn("bool TryParseEchoModeCommand(std::string const& rawMessage, EchoModeCommand& command)", player_script)
        self.assertIn("std::optional<float> TryParseEchoHuntRadius(std::string const& value)", player_script)
        self.assertIn('"range"', player_script)
        self.assertIn('"radius"', player_script)
        self.assertIn('"teleport"', player_script)
        self.assertIn('"tp"', player_script)
        self.assertIn('"recall"', player_script)
        self.assertIn('"#wm echo "', player_script)
        self.assertIn('"wm echo "', player_script)
        self.assertIn('"echo "', player_script)
        self.assertIn("WmSpells::ExecuteBoneboundEchoSeekRange(player, *command.huntRadius)", player_script)
        self.assertIn("WmSpells::ExecuteBoneboundEchoMode(player, command.mode, command.huntRadius)", player_script)
        self.assertIn("WmSpells::ExecuteBoneboundEchoTeleport(player)", player_script)
        self.assertIn("WM Echoes: teleported to your position.", player_script)
        self.assertIn("WM Echoes: seek range set to", player_script)
        self.assertIn("WM Echoes: seek mode enabled at", player_script)
        self.assertIn("WM Echoes: seek mode enabled.", player_script)
        self.assertIn("WM Echoes: follow mode enabled.", player_script)
        self.assertIn("bool OnPlayerCanUseChat(Player* player, uint32 /*type*/, uint32 /*language*/, std::string& msg) override", player_script)
        self.assertIn("'$.cleave_enabled', true", sql)
        self.assertIn("'$.cleave_cooldown_ms', 3000", sql)
        self.assertIn("'$.cleave_radius', 8.0", sql)
        self.assertIn("'$.alpha_cleave_damage_pct', 45", sql)
        self.assertIn("'$.echo_cleave_damage_pct', 25", sql)
        self.assertIn("'$.alpha_echo_hunt_radius', 35.0", sql)
        counter_sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_26_01_wm_spell_bonebound_echo_counter_aura.sql",
        ).read_text(encoding="utf-8")
        self.assertIn("'$.alpha_echo_count_aura_spell_id', 467", counter_sql)
        self.assertIn("'$.alpha_echo_count_aura_refresh_ms', 0", counter_sql)

    def test_bonebound_echo_stasis_stores_counts_and_restores_fresh_echoes(self) -> None:
        repo_root = self._repo_root()
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
        shell_script = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_shell_scripts.cpp",
        ).read_text(encoding="utf-8")
        shell_bank = repo_root.joinpath("control", "runtime", "spell_shell_bank.json").read_text(encoding="utf-8")
        sql = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_26_09_wm_spell_bonebound_echo_stasis.sql",
        ).read_text(encoding="utf-8")

        self.assertIn("struct BoneboundEchoStasisConfig", header)
        self.assertIn("BehaviorExecutionResult ExecuteBoneboundEchoStasis(Player* player, uint32 shellSpellId);", header)
        self.assertIn('behaviorKind == "bonebound_echo_stasis_v1"', runtime)
        self.assertIn("BuildBoneboundEchoStasisConfig", runtime)
        self.assertIn("CheckShellCast(Player* player, uint32 shellSpellId)", runtime)
        self.assertIn("player->HasItemCount(stasisConfig->soulShardItemId, stasisConfig->soulShardCount, false)", runtime)
        self.assertIn("SPELL_FAILED_REAGENTS", runtime)
        self.assertIn("BoneboundEchoStasisCounts CountActiveBoneboundEchoesByRole(uint32 ownerGuid)", runtime)
        self.assertIn("LoadStoredBoneboundEchoStasis", runtime)
        self.assertIn("StoreBoneboundEchoStasis", runtime)
        self.assertIn("ClearBoneboundEchoStasis", runtime)
        self.assertIn("wm_bonebound_echo_stasis", runtime)
        self.assertIn("BoneboundEchoStasisCounts storedBefore = LoadStoredBoneboundEchoStasis(ownerGuid);", runtime)
        self.assertIn("BoneboundEchoStasisCounts storedAfter = AddBoneboundEchoStasisCounts(storedBefore, activeCounts);", runtime)
        self.assertIn("StoreBoneboundEchoStasis(ownerGuid, storedAfter);", runtime)
        self.assertIn("pool_destroyers=", runtime)
        self.assertIn("pool_restorers=", runtime)
        self.assertIn("RemoveBoneboundAlphaEchoes(player);", runtime)
        self.assertIn("SpawnStoredBoneboundAlphaEcho(player, alphaPet, *runtimeConfig, BoneboundEchoRole::Warrior)", runtime)
        self.assertIn("SpawnStoredBoneboundAlphaEcho(player, alphaPet, *runtimeConfig, BoneboundEchoRole::Priest)", runtime)
        self.assertIn("BoneboundEchoStasisCounts remainingCounts = SubtractBoneboundEchoStasisCounts(storedCounts, restoredCounts);", runtime)
        self.assertIn("StoreBoneboundEchoStasis(ownerGuid, remainingCounts);", runtime)
        self.assertIn("ClearBoneboundEchoStasis(ownerGuid);", runtime)
        self.assertIn("RefreshBoneboundEchoCountAura(player, *runtimeConfig);", runtime)
        self.assertIn("state.remainingMs = ResolveAlphaEchoDurationMs(owner);", runtime)
        self.assertIn("ApplyBoneboundAlphaEchoRuntime(owner, alphaPet, echo, state, config, true);", runtime)
        self.assertIn("return CheckShellCast(player, shellSpellId);", runtime)
        self.assertIn("WmSpells::CheckShellCast(player, GetSpellInfo()->Id)", shell_script)
        self.assertIn("SPELL_EFFECT_APPLY_AURA", shell_script)
        self.assertIn('"shell_key": "bonebound_echo_stasis_v1"', shell_bank)
        self.assertIn('"spell_id": 946600', shell_bank)
        self.assertIn('"cast_time_index": 6', shell_bank)
        self.assertIn('"reagent_1_item_id": 6265', shell_bank)
        self.assertIn("CREATE TABLE IF NOT EXISTS wm_bonebound_echo_stasis", sql)
        self.assertIn("'bonebound_echo_stasis_v1'", sql)
        self.assertIn("(@wm_echo_stasis_shell_spell_id, 'spell_wm_shell_dispatch')", sql)

    def test_bonebound_pet_identity_does_not_fallback_to_stock_voidwalker_entry(self) -> None:
        runtime = self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")
        self.assertIn("Do not fall back to stock entry/display heuristics here.", runtime)
        self.assertNotIn(
            "if (pet->GetEntry() == gConfig.boneboundCreatureEntry && gConfig.boneboundDisplayId != 0 && pet->GetDisplayId() == gConfig.boneboundDisplayId)",
            runtime,
        )

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
        self.assertIn("name = 'Echo Destroyer'", sql)
        self.assertIn('"bleed_cooldown_ms":6000', sql)
        self.assertIn('"bleed_tick_ms":1000', sql)
        self.assertIn('"bleed_damage_per_attack_power_pct":20', sql)
        self.assertIn('"bleed_damage_per_level_pct":0', sql)
        self.assertIn('"bleed_damage_per_intellect_pct":0', sql)
        self.assertIn('"bleed_damage_per_shadow_power_pct":0', sql)
        self.assertIn('"alpha_echo_creature_entry":920101', sql)
        self.assertIn('"alpha_echo_name":"Echo Destroyer"', sql)
        self.assertIn('"alpha_echo_proc_chance_pct":7.5', sql)
        self.assertIn('"alpha_echo_max_active":40', sql)

        attack_power_sql = self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_25_00_wm_spell_bonebound_bleed_attack_power.sql",
        ).read_text(encoding="utf-8")
        self.assertIn("'$.bleed_damage_per_attack_power_pct', 20", attack_power_sql)
        self.assertIn("'$.bleed_damage_per_level_pct', 0", attack_power_sql)

    def test_alpha_sql_separates_bonebound_from_stock_voidwalker_entry(self) -> None:
        sql = self._repo_root().joinpath(
            "native_modules",
            "mod-wm-spells",
            "data",
            "sql",
            "world",
            "updates",
            "2026_04_17_00_wm_spell_bonebound_alpha_creature_truth.sql",
        ).read_text(encoding="utf-8")

        self.assertIn("SET @wm_bonebound_alpha_creature_entry := 920100;", sql)
        self.assertIn("name = 'Bonebound Alpha'", sql)
        self.assertIn('"creature_entry":920100', sql)

        cleanup_sql = self._repo_root().joinpath(
            "sql",
            "dev",
            "clear_jecia_legacy_summon_state_characters.sql",
        ).read_text(encoding="utf-8")
        self.assertIn("UPDATE character_pet", cleanup_sql)
        self.assertIn("CreatedBySpell = 940001", cleanup_sql)
        self.assertIn("entry = 920100", cleanup_sql)

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
        self.assertIn("bool lensMarked = IsNightWatchersLensMarked(victim);", runtime)
        self.assertIn("if (lensMarked)", runtime)
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

    def test_bridge_lab_runtime_config_scopes_wm_spells_to_jecia(self) -> None:
        repo_root = self._repo_root()
        configure_script = repo_root.joinpath(
            "scripts",
            "bridge_lab",
            "Configure-BridgeLabRuntime.ps1",
        ).read_text(encoding="utf-8")
        deploy_script = repo_root.joinpath(
            "scripts",
            "bridge_lab",
            "Deploy-BridgeLabWorldServer.ps1",
        ).read_text(encoding="utf-8")

        for script in (configure_script, deploy_script):
            self.assertIn('[string]$WmSpellsPlayerGuidAllowList = "5406"', script)
            self.assertIn(
                'Set-ConfigValue -Path $spellsConfig -Key "WmSpells.PlayerGuidAllowList" -Value """$WmSpellsPlayerGuidAllowList"""',
                script,
            )
            self.assertIn(
                'Set-ConfigValue -Path $spellsConfig -Key "WmSpells.BoneboundServant.CreatureEntry" -Value "920100"',
                script,
            )
            self.assertNotIn(
                'Set-ConfigValue -Path $spellsConfig -Key "WmSpells.PlayerGuidAllowList" -Value """"""',
                script,
            )

    def test_bridge_lab_runtime_config_sets_solo_5man_tuning(self) -> None:
        configure_script = self._repo_root().joinpath(
            "scripts",
            "bridge_lab",
            "Configure-BridgeLabRuntime.ps1",
        ).read_text(encoding="utf-8")

        expected_config_lines = [
            'Ensure-ConfigFile -Path $autoBalanceConfig -DistPath (Join-Path $buildModuleConfigRoot "AutoBalance.conf.dist")',
            'Ensure-ConfigFile -Path $soloLfgConfig -DistPath (Join-Path $buildModuleConfigRoot "SoloLfg.conf.dist")',
            'Ensure-ConfigFile -Path $dynamicLootRatesConfig -DistPath (Join-Path $buildModuleConfigRoot "mod_dynamic_loot_rates.conf.dist")',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.Enable.Global" -Value "1"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.MinPlayers" -Value "1"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.MinPlayers.Heroic" -Value "1"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.InflectionPoint.CurveFloor" -Value "1.0"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.InflectionPoint.CurveCeiling" -Value "1.0"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.InflectionPointHeroic.CurveFloor" -Value "1.0"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.InflectionPointHeroic.CurveCeiling" -Value "1.0"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifier.Health" -Value "0.75"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifier.Damage" -Value "0.50"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifier.Boss.Health" -Value "0.75"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifier.Boss.Damage" -Value "0.50"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifierHeroic.Health" -Value "0.75"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifierHeroic.Damage" -Value "0.50"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifierHeroic.Boss.Health" -Value "0.75"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifierHeroic.Boss.Damage" -Value "0.50"',
            'Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.RewardScaling.XP" -Value "0"',
            'Set-ConfigValue -Path $soloLfgConfig -Key "SoloLFG.Enable" -Value "1"',
            'Set-ConfigValue -Path $soloLfgConfig -Key "SoloLFG.FixedXP" -Value "1"',
            'Set-ConfigValue -Path $soloLfgConfig -Key "SoloLFG.FixedXPRate" -Value "0.75"',
            'Set-ConfigValue -Path $dynamicLootRatesConfig -Key "DynamicLootRates.Enable" -Value "1"',
            'Set-ConfigValue -Path $dynamicLootRatesConfig -Key "DynamicLootRates.Dungeon.Rate.GroupAmount" -Value "2"',
            'Set-ConfigValue -Path $dynamicLootRatesConfig -Key "DynamicLootRates.Dungeon.Rate.ReferencedAmount" -Value "2"',
        ]

        for expected_line in expected_config_lines:
            self.assertIn(expected_line, configure_script)


if __name__ == "__main__":
    unittest.main()
