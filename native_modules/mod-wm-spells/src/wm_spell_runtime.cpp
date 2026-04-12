#include "wm_spell_runtime.h"

#include "Config.h"
#include "DatabaseEnv.h"
#include "ObjectAccessor.h"
#include "PetDefines.h"

#include <algorithm>
#include <cmath>
#include <string>

namespace
{
    using namespace std::chrono_literals;

    WmSpells::RuntimeConfig gConfig;
    uint32 gDebugPollTimer = 0;

    void ParseUIntSet(std::string const& raw, std::unordered_set<uint32>& target)
    {
        target.clear();
        std::string token;
        for (char ch : raw)
        {
            if (ch == ',')
            {
                if (!token.empty())
                {
                    target.insert(static_cast<uint32>(std::stoul(token)));
                    token.clear();
                }
                continue;
            }

            if (ch >= '0' && ch <= '9')
                token.push_back(ch);
        }

        if (!token.empty())
            target.insert(static_cast<uint32>(std::stoul(token)));
    }

    Unit* GetCorpseTarget(Player* player)
    {
        if (!player)
            return nullptr;

        Unit* target = ObjectAccessor::GetUnit(*player, player->GetTarget());
        if (!target || target->IsAlive())
            return nullptr;
        return target;
    }

    uint32 BuildHealth(Player* player)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float health = static_cast<float>(gConfig.boneboundBaseHealth)
            + static_cast<float>(gConfig.boneboundHealthPerLevel * player->GetLevel())
            + static_cast<float>(gConfig.boneboundHealthPerIntellect) * intellect
            + static_cast<float>(gConfig.boneboundHealthPerShadowPower) * std::max<int32>(0, shadowPower);
        return std::max<uint32>(1u, static_cast<uint32>(std::round(health)));
    }

    float BuildDamage(Player* player, uint32 baseValue)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float damage = static_cast<float>(baseValue)
            + static_cast<float>(player->GetLevel()) * (static_cast<float>(gConfig.boneboundDamagePerLevelPct) / 100.0f)
            + intellect * (static_cast<float>(gConfig.boneboundDamagePerIntellectPct) / 100.0f)
            + static_cast<float>(std::max<int32>(0, shadowPower)) * (static_cast<float>(gConfig.boneboundDamagePerShadowPowerPct) / 100.0f);
        return std::max(1.0f, damage);
    }

    float BuildScale(Player* player)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float scale = gConfig.boneboundScaleBase
            + static_cast<float>(player->GetLevel()) * gConfig.boneboundScalePerLevel
            + intellect * gConfig.boneboundScalePerIntellect
            + static_cast<float>(std::max<int32>(0, shadowPower)) * gConfig.boneboundScalePerShadowPower;
        return std::clamp(scale, 0.9f, 1.45f);
    }

    bool IsBoneboundPet(Pet* pet)
    {
        if (!pet)
            return false;

        if (pet->GetEntry() != gConfig.boneboundCreatureEntry)
            return false;

        if (gConfig.boneboundDisplayId != 0 && pet->GetDisplayId() == gConfig.boneboundDisplayId)
            return true;

        return pet->GetUInt32Value(UNIT_CREATED_BY_SPELL) != 0
            && gConfig.boneboundShellSpellIds.find(pet->GetUInt32Value(UNIT_CREATED_BY_SPELL)) != gConfig.boneboundShellSpellIds.end();
    }

    void ApplyBoneboundOverlay(Player* owner, Pet* pet, uint32 createdBySpellId, bool persistPet)
    {
        if (!owner || !pet)
            return;

        if (createdBySpellId != 0)
            pet->SetUInt32Value(UNIT_CREATED_BY_SPELL, createdBySpellId);

        pet->SetName(gConfig.boneboundName);
        if (gConfig.boneboundDisplayId != 0)
        {
            pet->SetDisplayId(gConfig.boneboundDisplayId);
            pet->SetNativeDisplayId(gConfig.boneboundDisplayId);
        }

        pet->SetVirtualItem(0, gConfig.boneboundVirtualItem1);
        pet->SetVirtualItem(1, gConfig.boneboundVirtualItem2);
        pet->SetVirtualItem(2, gConfig.boneboundVirtualItem3);
        pet->SetObjectScale(BuildScale(owner));
        pet->SetMaxHealth(BuildHealth(owner));
        pet->SetHealth(pet->GetMaxHealth());
        pet->SetBaseWeaponDamage(BASE_ATTACK, MINDAMAGE, BuildDamage(owner, gConfig.boneboundBaseMinDamage));
        pet->SetBaseWeaponDamage(BASE_ATTACK, MAXDAMAGE, BuildDamage(owner, gConfig.boneboundBaseMaxDamage));
        pet->SetAttackTime(BASE_ATTACK, gConfig.boneboundAttackTimeMs);
        pet->UpdateDamagePhysical(BASE_ATTACK);

        owner->PetSpellInitialize();
        if (persistPet)
            pet->SavePetToDB(PET_SAVE_AS_CURRENT);
    }

    std::string EscapeForSql(std::string value)
    {
        WorldDatabase.EscapeString(value);
        return value;
    }

    std::string SqlString(std::string const& value)
    {
        return "'" + EscapeForSql(value) + "'";
    }

    std::string JsonResult(bool ok, std::string const& behaviorKind, std::string const& message)
    {
        std::string payload = "{\"ok\":";
        payload += ok ? "true" : "false";
        payload += ",\"behavior_kind\":\"" + behaviorKind + "\"";
        payload += ",\"message\":\"" + message + "\"}";
        return payload;
    }

    void CompleteDebugRequest(uint64 requestId, std::string const& status, std::string const& resultJson, std::string const& errorText = "")
    {
        WorldDatabase.Execute(
            "UPDATE wm_spell_debug_request "
            "SET Status = {}, ProcessedAt = NOW(), ResultJSON = {}, ErrorText = {}, UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE RequestID = {}",
            SqlString(status),
            SqlString(resultJson),
            errorText.empty() ? "NULL" : SqlString(errorText),
            requestId);
    }
}

namespace WmSpells
{
    RuntimeConfig const& GetConfig()
    {
        return gConfig;
    }

    void LoadConfig()
    {
        gConfig.enabled = sConfigMgr->GetOption<bool>("WmSpells.Enable", true);
        ParseUIntSet(sConfigMgr->GetOption<std::string>("WmSpells.PlayerGuidAllowList", ""), gConfig.playerGuidAllowList);
        gConfig.labOnlyDebugInvokeEnable = sConfigMgr->GetOption<bool>("WmSpells.LabOnlyDebugInvokeEnable", false);
        gConfig.debugPollIntervalMs = sConfigMgr->GetOption<uint32>("WmSpells.DebugPollIntervalMs", 1000u);
        gConfig.boneboundServantEnabled = sConfigMgr->GetOption<bool>("WmSpells.BoneboundServant.Enable", true);
        ParseUIntSet(sConfigMgr->GetOption<std::string>("WmSpells.BoneboundServant.ShellSpellIds", "940000"), gConfig.boneboundShellSpellIds);
        gConfig.boneboundRequireCorpse = sConfigMgr->GetOption<bool>("WmSpells.BoneboundServant.RequireCorpse", true);
        gConfig.boneboundCreatureEntry = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.CreatureEntry", 1860u);
        gConfig.boneboundName = sConfigMgr->GetOption<std::string>("WmSpells.BoneboundServant.Name", "Bonebound Servant");
        gConfig.boneboundDisplayId = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.DisplayId", 734u);
        gConfig.boneboundVirtualItem1 = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.VirtualItem1", 1897u);
        gConfig.boneboundVirtualItem2 = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.VirtualItem2", 0u);
        gConfig.boneboundVirtualItem3 = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.VirtualItem3", 0u);
        gConfig.boneboundAttackTimeMs = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.AttackTimeMs", 2000u);
        gConfig.boneboundScaleBase = sConfigMgr->GetOption<float>("WmSpells.BoneboundServant.ScaleBase", 1.0f);
        gConfig.boneboundScalePerLevel = sConfigMgr->GetOption<float>("WmSpells.BoneboundServant.ScalePerLevel", 0.005f);
        gConfig.boneboundScalePerIntellect = sConfigMgr->GetOption<float>("WmSpells.BoneboundServant.ScalePerIntellect", 0.001f);
        gConfig.boneboundScalePerShadowPower = sConfigMgr->GetOption<float>("WmSpells.BoneboundServant.ScalePerShadowPower", 0.0007f);
        gConfig.boneboundBaseHealth = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.BaseHealth", 140u);
        gConfig.boneboundHealthPerLevel = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.HealthPerLevel", 24u);
        gConfig.boneboundHealthPerIntellect = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.HealthPerIntellect", 5u);
        gConfig.boneboundHealthPerShadowPower = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.HealthPerShadowPower", 2u);
        gConfig.boneboundBaseMinDamage = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.BaseMinDamage", 7u);
        gConfig.boneboundBaseMaxDamage = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.BaseMaxDamage", 11u);
        gConfig.boneboundDamagePerLevelPct = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.DamagePerLevelPct", 125u);
        gConfig.boneboundDamagePerIntellectPct = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.DamagePerIntellectPct", 8u);
        gConfig.boneboundDamagePerShadowPowerPct = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.DamagePerShadowPowerPct", 16u);
    }

    bool IsPlayerAllowed(Player* player)
    {
        return player
            && gConfig.enabled
            && !gConfig.playerGuidAllowList.empty()
            && gConfig.playerGuidAllowList.find(static_cast<uint32>(player->GetGUID().GetCounter())) != gConfig.playerGuidAllowList.end();
    }

    bool IsBoneboundShellSpell(Player* player, uint32 spellId)
    {
        return IsPlayerAllowed(player)
            && gConfig.boneboundServantEnabled
            && gConfig.boneboundShellSpellIds.find(spellId) != gConfig.boneboundShellSpellIds.end();
    }

    SpellCastResult CheckBoneboundCorpseTarget(Player* player)
    {
        if (!player)
            return SPELL_FAILED_CASTER_DEAD;

        if (!IsPlayerAllowed(player) || !gConfig.boneboundServantEnabled)
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        if (!gConfig.boneboundRequireCorpse)
            return SPELL_CAST_OK;

        return GetCorpseTarget(player) ? SPELL_CAST_OK : SPELL_FAILED_BAD_TARGETS;
    }

    BehaviorExecutionResult ExecuteBoneboundServant(Player* player, uint32 createdBySpellId, bool persistPet)
    {
        if (!player)
            return {false, "player_not_online"};

        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        if (!gConfig.boneboundServantEnabled)
            return {false, "bonebound_disabled"};

        if (gConfig.boneboundRequireCorpse && !GetCorpseTarget(player))
            return {false, "corpse_required"};

        if (Pet* currentPet = player->GetPet())
            player->RemovePet(currentPet, PET_SAVE_AS_DELETED);

        Position pos;
        player->GetClosePoint(pos.m_positionX, pos.m_positionY, pos.m_positionZ, 1.0f, 2.0f);

        Pet* pet = player->SummonPet(
            gConfig.boneboundCreatureEntry,
            pos.m_positionX,
            pos.m_positionY,
            pos.m_positionZ,
            player->GetOrientation(),
            SUMMON_PET,
            0ms,
            createdBySpellId
        );

        if (!pet)
            return {false, "summon_failed"};

        ApplyBoneboundOverlay(player, pet, createdBySpellId, persistPet);
        return {true, "bonebound_servant_summoned"};
    }

    void ReapplyBoneboundOverlay(Pet* pet)
    {
        if (!pet || !pet->GetOwner() || !pet->GetOwner()->ToPlayer())
            return;

        Player* owner = pet->GetOwner()->ToPlayer();
        if (!IsPlayerAllowed(owner) || !IsBoneboundPet(pet))
            return;

        ApplyBoneboundOverlay(owner, pet, pet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
    }

    void PollDebugRequests(uint32 diff)
    {
        if (!gConfig.enabled || !gConfig.labOnlyDebugInvokeEnable)
            return;

        if (gDebugPollTimer > diff)
        {
            gDebugPollTimer -= diff;
            return;
        }

        gDebugPollTimer = gConfig.debugPollIntervalMs;

        QueryResult result = WorldDatabase.Query(
            "SELECT RequestID, PlayerGUID, BehaviorKind FROM wm_spell_debug_request "
            "WHERE Status = 'pending' ORDER BY RequestID ASC LIMIT 1");

        if (!result)
            return;

        Field* fields = result->Fetch();
        uint64 requestId = fields[0].Get<uint64>();
        uint32 playerGuid = fields[1].Get<uint32>();
        std::string behaviorKind = fields[2].Get<std::string>();

        WorldDatabase.Execute(
            "UPDATE wm_spell_debug_request SET Status = 'claimed', UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE RequestID = {} AND Status = 'pending'",
            requestId);

        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (behaviorKind == "summon_bonebound_servant_v1")
        {
            BehaviorExecutionResult exec = ExecuteBoneboundServant(player, 0, false);
            if (exec.ok)
            {
                CompleteDebugRequest(requestId, "done", JsonResult(true, behaviorKind, exec.message));
            }
            else
            {
                CompleteDebugRequest(requestId, "failed", JsonResult(false, behaviorKind, exec.message), exec.message);
            }
            return;
        }

        CompleteDebugRequest(requestId, "failed", JsonResult(false, behaviorKind, "unknown_behavior_kind"), "unknown_behavior_kind");
    }
}
