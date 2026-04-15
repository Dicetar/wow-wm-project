#pragma once

#include "Common.h"
#include "ObjectGuid.h"
#include "Pet.h"
#include "Player.h"

#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>

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
        uint32 boneboundCreatureEntry = 1860;
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
        uint32 creatureEntry = 1860;
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
        uint32 omegaCreatureEntry = 1860;
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
        bool shadowDotEnabled = true;
        uint32 shadowDotCooldownMs = 6000;
        uint32 shadowDotDurationMs = 4000;
        uint32 shadowDotTickMs = 1000;
        uint32 shadowDotBaseDamage = 3;
        uint32 shadowDotDamagePerLevelPct = 25;
        uint32 shadowDotDamagePerIntellectPct = 1;
        uint32 shadowDotDamagePerShadowPowerPct = 0;
        bool alphaEchoEnabled = true;
        uint32 alphaEchoCreatureEntry = 920101;
        float alphaEchoProcChancePct = 5.0f;
        uint32 alphaEchoMaxActive = 3;
        uint32 alphaEchoDamagePct = 100;
        float alphaEchoFollowDistance = 2.6f;
        float alphaEchoFollowAngle = PET_FOLLOW_ANGLE;
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

    RuntimeConfig const& GetConfig();
    void LoadConfig();
    bool IsPlayerAllowed(Player* player);
    bool IsBoneboundShellSpell(Player* player, uint32 spellId);
    bool IsSupportedBehaviorKind(std::string const& behaviorKind);
    std::optional<BehaviorRecord> LoadBehaviorRecord(uint32 shellSpellId);
    SpellCastResult CheckBoneboundCorpseTarget(Player* player, uint32 shellSpellId = 0);
    BehaviorExecutionResult ExecuteBoneboundServant(Player* player, uint32 createdBySpellId, bool persistPet);
    BehaviorExecutionResult ExecuteShellBehavior(Player* player, uint32 shellSpellId, bool persistPetFallback);
    void UpdateTrackedCompanions(uint32 diff);
    void MaintainBoneboundSummons(Player* player);
    void ForgetBoneboundCompanions(Player* player);
    void ReapplyBoneboundOverlay(Pet* pet);
    void HandleBoneboundMeleeDamage(Unit* attacker, Unit* victim, uint32& damage);
    void MaintainIntellectBlockPassive(Player* player);
    void MaintainCombatProficiencies(Player* player);
    void ForgetIntellectBlockPassive(Player* player);
    void PollDebugRequests(uint32 diff);
}
