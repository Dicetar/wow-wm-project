#pragma once

#include "Common.h"
#include "ObjectGuid.h"
#include "Pet.h"
#include "Player.h"
#include "Unit.h"

#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

class SpellInfo;

namespace WmSpells
{
    struct RuntimeConfig
    {
        bool enabled = true;
        bool labOnlyDebugInvokeEnable = false;
        uint32 debugPollIntervalMs = 1000;
        std::unordered_set<uint32> playerGuidAllowList;
        bool intellectBlockPassiveEnabled = true;
        bool boneboundServantEnabled = true;
        std::unordered_set<uint32> boneboundShellSpellIds;
        bool boneboundRequireCorpse = true;
        uint32 boneboundCreatureEntry = 920100;
        std::string boneboundName = "Bonebound Servant";
        uint32 boneboundDisplayId = 734;
        uint32 boneboundVirtualItem1 = 1897;
        uint32 boneboundVirtualItem2 = 0;
        uint32 boneboundVirtualItem3 = 0;
        uint32 boneboundAttackTimeMs = 2000;
        float boneboundScaleBase = 1.0f;
        float boneboundScalePerLevel = 0.005f;
        float boneboundScalePerIntellect = 0.001f;
        float boneboundScalePerShadowPower = 0.0007f;
        uint32 boneboundBaseHealth = 140;
        uint32 boneboundHealthPerLevel = 24;
        uint32 boneboundHealthPerIntellect = 5;
        uint32 boneboundHealthPerShadowPower = 2;
        uint32 boneboundBaseMinDamage = 7;
        uint32 boneboundBaseMaxDamage = 11;
        uint32 boneboundDamagePerLevelPct = 125;
        uint32 boneboundDamagePerIntellectPct = 8;
        uint32 boneboundDamagePerShadowPowerPct = 16;
    };

    struct BehaviorExecutionResult
    {
        bool ok = false;
        std::string message;
    };

    struct BoneboundBehaviorConfig
    {
        uint32 shellSpellId = 0;
        bool persistPet = true;
        bool requireCorpse = true;
        bool spawnOmega = false;
        bool preserveBaseStats = false;
        uint32 creatureEntry = 920100;
        std::string name = "Bonebound Servant";
        uint32 displayId = 734;
        uint32 virtualItem1 = 1897;
        uint32 virtualItem2 = 0;
        uint32 virtualItem3 = 0;
        uint32 attackTimeMs = 2000;
        float scaleBase = 1.0f;
        float scalePerLevel = 0.005f;
        float scalePerIntellect = 0.001f;
        float scalePerShadowPower = 0.0007f;
        uint32 baseHealth = 140;
        uint32 healthPerLevel = 24;
        uint32 healthPerIntellect = 5;
        uint32 healthPerShadowPower = 2;
        uint32 baseMinDamage = 7;
        uint32 baseMaxDamage = 11;
        uint32 damagePerLevelPct = 125;
        uint32 damagePerIntellectPct = 8;
        uint32 damagePerShadowPowerPct = 16;
        bool ownerIntellectToAllStats = true;
        bool ownerShadowPowerToAttackPower = true;
        float ownerIntellectToAllStatsScale = 1.0f;
        float ownerShadowPowerToAttackPowerScale = 1.0f;
        uint32 omegaCreatureEntry = 920100;
        std::string omegaName = "Bonebound Raider";
        uint32 omegaDisplayId = 734;
        uint32 omegaVirtualItem1 = 1897;
        uint32 omegaVirtualItem2 = 0;
        uint32 omegaVirtualItem3 = 0;
        float omegaScaleMultiplier = 1.0f;
        uint32 omegaHealthPct = 85;
        uint32 omegaDamagePct = 75;
        float omegaFollowDistance = 2.2f;
        float omegaFollowAngle = PET_FOLLOW_ANGLE;
        bool bleedEnabled = true;
        uint32 bleedCooldownMs = 6000;
        uint32 bleedDurationMs = 4000;
        uint32 bleedTickMs = 1000;
        uint32 bleedBaseDamage = 3;
        uint32 bleedDamagePerAttackPowerPct = 20;
        uint32 bleedDamagePerLevelPct = 0;
        uint32 bleedDamagePerIntellectPct = 0;
        uint32 bleedDamagePerShadowPowerPct = 0;
        bool alphaEchoEnabled = true;
        uint32 alphaEchoCreatureEntry = 920101;
        std::string alphaEchoName = "Echo Destroyer";
        float alphaEchoProcChancePct = 7.5f;
        uint32 alphaEchoMaxActive = 40;
        uint32 alphaEchoDamagePct = 100;
        float alphaEchoFollowDistance = 2.6f;
        float alphaEchoFollowAngle = PET_FOLLOW_ANGLE;
        float alphaEchoHuntRadius = 35.0f;
        bool alphaEchoCountAuraEnabled = true;
        uint32 alphaEchoCountAuraSpellId = 467;
        uint32 alphaEchoCountAuraRefreshMs = 3000;
        bool priestEchoEnabled = true;
        uint32 priestEchoCreatureEntry = 920103;
        std::string priestEchoName = "Echo Restorer";
        uint32 priestEchoDisplayId = 11397;
        uint32 priestEchoVirtualItem1 = 0;
        uint32 priestEchoVirtualItem2 = 0;
        uint32 priestEchoVirtualItem3 = 0;
        std::vector<uint32> priestEchoStaffItemEntries = {18842, 22800, 19909, 21275, 21452, 22335, 19570, 19566};
        float priestEchoScaleMultiplier = 0.9f;
        float priestEchoProcChancePct = 5.0f;
        uint32 priestEchoMaxActive = 10;
        uint32 priestEchoPityAfterWarriorSpawns = 6;
        uint32 priestEchoDamagePct = 35;
        float priestEchoSupportRadius = 45.0f;
        uint32 priestEchoHealBelowHealthPct = 95;
        uint32 priestEchoHealSpellId = 2061;
        uint32 priestEchoHealBasePct = 12;
        uint32 priestEchoHealCooldownMs = 2500;
        uint32 priestEchoRenewSpellId = 139;
        uint32 priestEchoRenewBasePct = 5;
        uint32 priestEchoRenewCooldownMs = 10000;
        uint32 priestEchoShieldSpellId = 17;
        uint32 priestEchoShieldBasePct = 10;
        uint32 priestEchoShieldCooldownMs = 12000;
        uint32 priestEchoDiseaseDispelSpellId = 528;
        uint32 priestEchoCurseDispelSpellId = 475;
        uint32 priestEchoDispelCooldownMs = 8000;
        uint32 priestEchoMassDispelSpellId = 32375;
        uint32 priestEchoMassDispelCooldownMs = 180000;
        uint32 priestEchoMassDispelMinAffected = 3;
        uint32 priestEchoMassDispelMinSeverity = 8;
        uint32 priestEchoMassDispelMaxRemovals = 8;
        uint32 priestEchoDpsSpellId = 8092;
        uint32 priestEchoDpsDamageSpellId = 8092;
        uint32 priestEchoDpsCastTimeMs = 1500;
        uint32 priestEchoDpsDamagePct = 19;
        uint32 priestEchoDpsCooldownMs = 2500;
        float priestEchoDpsMaxRange = 100.0f;
        uint32 priestEchoSpellPowerToHealingPct = 35;
        uint32 priestEchoSpellPowerToShieldPct = 30;
        uint32 priestEchoSpellPowerToDamagePct = 45;
        float priestEchoSafeFollowDistance = 1.8f;
        float priestEchoSafeMinEnemyDistance = 6.0f;
        bool cleaveEnabled = true;
        uint32 cleaveCooldownMs = 3000;
        float cleaveRadius = 5.0f;
        uint32 cleaveMaxTargets = 4;
        uint32 alphaCleaveDamagePct = 45;
        uint32 echoCleaveDamagePct = 25;
    };

    struct BehaviorRecord
    {
        uint32 shellSpellId = 0;
        std::string behaviorKind;
        std::string configJson;
        std::string status;
    };

    struct IntellectBlockPassiveConfig
    {
        uint32 shellSpellId = 0;
        float intellectToBlockRatingScale = 1.0f;
        float spellPowerToBlockRatingScale = 1.0f;
        uint32 spellSchoolMask = SPELL_SCHOOL_MASK_MAGIC;
        uint32 maxBlockRating = 0;
    };

    struct BoneboundEchoStasisConfig
    {
        uint32 shellSpellId = 946600;
        uint32 alphaShellSpellId = 940001;
        uint32 soulShardItemId = 6265;
        uint32 soulShardCount = 1;
    };

    RuntimeConfig const& GetConfig();
    void LoadConfig();
    bool IsPlayerAllowed(Player* player);
    bool IsBoneboundShellSpell(Player* player, uint32 spellId);
    bool IsSupportedBehaviorKind(std::string const& behaviorKind);
    std::optional<BehaviorRecord> LoadBehaviorRecord(uint32 shellSpellId);
    SpellCastResult CheckShellCast(Player* player, uint32 shellSpellId = 0);
    SpellCastResult CheckBoneboundCorpseTarget(Player* player, uint32 shellSpellId = 0);
    BehaviorExecutionResult ExecuteBoneboundServant(Player* player, uint32 createdBySpellId, bool persistPet);
    BehaviorExecutionResult ExecuteBoneboundEchoStasis(Player* player, uint32 shellSpellId);
    BehaviorExecutionResult ExecuteShellBehavior(Player* player, uint32 shellSpellId, bool persistPetFallback);
    BehaviorExecutionResult ExecuteBoneboundEchoMode(Player* player, std::string const& mode, std::optional<float> huntRadiusOverride = std::nullopt);
    BehaviorExecutionResult ExecuteBoneboundEchoSeekRange(Player* player, float huntRadius);
    BehaviorExecutionResult ExecuteBoneboundEchoTeleport(Player* player);
    void UpdateTrackedCompanions(uint32 diff);
    void MaintainBoneboundSummons(Player* player);
    void ForgetBoneboundCompanions(Player* player);
    void ReapplyBoneboundOverlay(Pet* pet);
    void HandleBoneboundMeleeDamage(Unit* attacker, Unit* victim, uint32& damage);
    void MaintainIntellectBlockPassive(Player* player);
    void MaintainCombatProficiencies(Player* player);
    void ForgetIntellectBlockPassive(Player* player);
    void MaintainNightWatchersLens(Player* player, uint32 diff);
    void ForgetNightWatchersLens(Player* player);
    bool IsNightWatchersLensMarked(Unit const* unit);
    void HandleNightWatchersLensWeaponDamage(Unit* attacker, Unit* victim, uint32& damage);
    void HandleNightWatchersLensSpellDamage(Unit* attacker, Unit* victim, int32& damage, SpellInfo const* spellInfo);
    void HandleNightWatchersLensDefenseExposure(
        Unit const* attacker,
        Unit const* victim,
        WeaponAttackType attType,
        int32& attackerMaxSkillValueForLevel,
        int32& victimMaxSkillValueForLevel,
        int32& attackerWeaponSkill,
        int32& victimDefenseSkill,
        int32& crit_chance,
        int32& miss_chance,
        int32& dodge_chance,
        int32& parry_chance,
        int32& block_chance);
    void PollDebugRequests(uint32 diff);
}
