#pragma once

#include "Common.h"
#include "Pet.h"
#include "Player.h"

#include <string>
#include <unordered_set>

namespace WmSpells
{
    struct RuntimeConfig
    {
        bool enabled = true;
        bool labOnlyDebugInvokeEnable = false;
        uint32 debugPollIntervalMs = 1000;
        std::unordered_set<uint32> playerGuidAllowList;
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

    RuntimeConfig const& GetConfig();
    void LoadConfig();
    bool IsPlayerAllowed(Player* player);
    bool IsBoneboundShellSpell(Player* player, uint32 spellId);
    SpellCastResult CheckBoneboundCorpseTarget(Player* player);
    BehaviorExecutionResult ExecuteBoneboundServant(Player* player, uint32 createdBySpellId, bool persistPet);
    void ReapplyBoneboundOverlay(Pet* pet);
    void PollDebugRequests(uint32 diff);
}
