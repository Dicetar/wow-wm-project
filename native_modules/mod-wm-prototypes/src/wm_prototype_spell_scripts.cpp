#include "Config.h"
#include "Log.h"
#include "MotionMaster.h"
#include "Pet.h"
#include "PetDefines.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "TemporarySummon.h"
#include "Unit.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <list>
#include <string>
#include <vector>
#include <unordered_set>

namespace
{
    constexpr uint32 LEGACY_SKELETAL_PET_ENTRY = 6412;
    constexpr uint32 LEGACY_BAD_MANUAL_SPELL_1 = 28140;
    constexpr uint32 LEGACY_BAD_MANUAL_SPELL_2 = 26542;

    struct PrototypeConfig
    {
        bool enabled = true;
        bool twinSkeletonEnabled = false;
        bool skeletalPetEnabled = true;
        std::unordered_set<uint32> playerGuidAllowList;
        std::unordered_set<uint32> twinSkeletonShellSpellIds;
        std::unordered_set<uint32> skeletalPetShellSpellIds;
        uint32 primaryCreatureEntry = 1890;
        uint32 secondaryCreatureEntry = 201;
        uint32 durationMs = 45000;
        float spawnDistance = 1.8f;
        uint32 baseHealth = 90;
        uint32 healthPerLevel = 18;
        uint32 healthPerIntellect = 3;
        uint32 healthPerShadowSpellPower = 1;
        uint32 baseMinDamage = 4;
        uint32 baseMaxDamage = 8;
        uint32 damagePerLevelPct = 100;
        uint32 damagePerIntellectPct = 5;
        uint32 damagePerShadowSpellPowerPct = 12;
        uint32 skeletalPetEntry = 6412;
        std::string skeletalPetName = "Bonebound Servant";
        float skeletalPetScale = 1.0f;
        uint32 skeletalPetBaseHealth = 120;
        uint32 skeletalPetHealthPerLevel = 22;
        uint32 skeletalPetHealthPerIntellect = 4;
        uint32 skeletalPetHealthPerShadowSpellPower = 2;
        uint32 skeletalPetBaseMinDamage = 6;
        uint32 skeletalPetBaseMaxDamage = 10;
        uint32 skeletalPetDamagePerLevelPct = 120;
        uint32 skeletalPetDamagePerIntellectPct = 8;
        uint32 skeletalPetDamagePerShadowSpellPowerPct = 18;
        uint32 skeletalPetAppearanceDisplayId = 734;
        uint32 skeletalPetVirtualItem1 = 1897;
        uint32 skeletalPetVirtualItem2 = 0;
        uint32 skeletalPetVirtualItem3 = 0;
        uint32 skeletalPetAttackTimeMs = 1850;
        std::vector<uint32> skeletalPetPassiveSpellIds;
        std::vector<uint32> skeletalPetAutoSpellIds;
        std::vector<uint32> skeletalPetManualSpellIds;
    };

    PrototypeConfig gConfig;

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

    void ParseUIntVector(std::string const& raw, std::vector<uint32>& target)
    {
        target.clear();
        std::string token;
        for (char ch : raw)
        {
            if (ch == ',')
            {
                if (!token.empty())
                {
                    target.push_back(static_cast<uint32>(std::stoul(token)));
                    token.clear();
                }
                continue;
            }

            if (ch >= '0' && ch <= '9')
                token.push_back(ch);
        }

        if (!token.empty())
            target.push_back(static_cast<uint32>(std::stoul(token)));
    }

    void LoadPrototypeConfig()
    {
        gConfig.enabled = sConfigMgr->GetOption<bool>("WmPrototypes.Enable", true);
        gConfig.twinSkeletonEnabled = sConfigMgr->GetOption<bool>("WmPrototypes.TwinSkeleton.Enable", false);
        gConfig.skeletalPetEnabled = sConfigMgr->GetOption<bool>("WmPrototypes.SkeletalPet.Enable", true);
        ParseUIntSet(sConfigMgr->GetOption<std::string>("WmPrototypes.PlayerGuidAllowList", ""), gConfig.playerGuidAllowList);
        ParseUIntSet(
            sConfigMgr->GetOption<std::string>("WmPrototypes.TwinSkeleton.ShellSpellIds", ""),
            gConfig.twinSkeletonShellSpellIds
        );
        ParseUIntSet(
            sConfigMgr->GetOption<std::string>("WmPrototypes.SkeletalPet.ShellSpellIds", ""),
            gConfig.skeletalPetShellSpellIds
        );
        gConfig.primaryCreatureEntry = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.PrimaryCreatureEntry", 1890u);
        gConfig.secondaryCreatureEntry = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.SecondaryCreatureEntry", 201u);
        gConfig.durationMs = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.DurationMs", 45000u);
        gConfig.spawnDistance = sConfigMgr->GetOption<float>("WmPrototypes.TwinSkeleton.SpawnDistance", 1.8f);
        gConfig.baseHealth = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.BaseHealth", 90u);
        gConfig.healthPerLevel = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.HealthPerLevel", 18u);
        gConfig.healthPerIntellect = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.HealthPerIntellect", 3u);
        gConfig.healthPerShadowSpellPower = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.HealthPerShadowSpellPower", 1u);
        gConfig.baseMinDamage = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.BaseMinDamage", 4u);
        gConfig.baseMaxDamage = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.BaseMaxDamage", 8u);
        gConfig.damagePerLevelPct = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.DamagePerLevelPct", 100u);
        gConfig.damagePerIntellectPct = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.DamagePerIntellectPct", 5u);
        gConfig.damagePerShadowSpellPowerPct = sConfigMgr->GetOption<uint32>("WmPrototypes.TwinSkeleton.DamagePerShadowSpellPowerPct", 12u);
        gConfig.skeletalPetEntry = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.Entry", 6412u);
        gConfig.skeletalPetName = sConfigMgr->GetOption<std::string>("WmPrototypes.SkeletalPet.Name", "Bonebound Servant");
        gConfig.skeletalPetScale = sConfigMgr->GetOption<float>("WmPrototypes.SkeletalPet.Scale", 1.02f);
        gConfig.skeletalPetBaseHealth = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.BaseHealth", 180u);
        gConfig.skeletalPetHealthPerLevel = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.HealthPerLevel", 28u);
        gConfig.skeletalPetHealthPerIntellect = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.HealthPerIntellect", 6u);
        gConfig.skeletalPetHealthPerShadowSpellPower = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.HealthPerShadowSpellPower", 3u);
        gConfig.skeletalPetBaseMinDamage = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.BaseMinDamage", 8u);
        gConfig.skeletalPetBaseMaxDamage = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.BaseMaxDamage", 13u);
        gConfig.skeletalPetDamagePerLevelPct = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.DamagePerLevelPct", 145u);
        gConfig.skeletalPetDamagePerIntellectPct = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.DamagePerIntellectPct", 12u);
        gConfig.skeletalPetDamagePerShadowSpellPowerPct = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.DamagePerShadowSpellPowerPct", 24u);
        gConfig.skeletalPetAppearanceDisplayId = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.AppearanceDisplayId", 734u);
        gConfig.skeletalPetVirtualItem1 = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.VirtualItem1", 1897u);
        gConfig.skeletalPetVirtualItem2 = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.VirtualItem2", 0u);
        gConfig.skeletalPetVirtualItem3 = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.VirtualItem3", 0u);
        gConfig.skeletalPetAttackTimeMs = sConfigMgr->GetOption<uint32>("WmPrototypes.SkeletalPet.AttackTimeMs", 1850u);
        ParseUIntVector(
            sConfigMgr->GetOption<std::string>("WmPrototypes.SkeletalPet.PassiveSpellIds", "32233"),
            gConfig.skeletalPetPassiveSpellIds
        );
        ParseUIntVector(
            sConfigMgr->GetOption<std::string>("WmPrototypes.SkeletalPet.AutoSpellIds", "47480"),
            gConfig.skeletalPetAutoSpellIds
        );
        ParseUIntVector(
            sConfigMgr->GetOption<std::string>("WmPrototypes.SkeletalPet.ManualSpellIds", ""),
            gConfig.skeletalPetManualSpellIds
        );
    }

    bool IsAllowedPlayer(Player* player)
    {
        return player
            && gConfig.enabled
            && !gConfig.playerGuidAllowList.empty()
            && gConfig.playerGuidAllowList.find(static_cast<uint32>(player->GetGUID().GetCounter())) != gConfig.playerGuidAllowList.end();
    }

    bool IsTwinSkeletonSpell(Player* player, uint32 spellId)
    {
        return IsAllowedPlayer(player)
            && gConfig.twinSkeletonEnabled
            && gConfig.twinSkeletonShellSpellIds.find(spellId) != gConfig.twinSkeletonShellSpellIds.end();
    }

    bool IsSkeletalPetSpell(Player* player, uint32 spellId)
    {
        return IsAllowedPlayer(player)
            && gConfig.skeletalPetEnabled
            && gConfig.skeletalPetShellSpellIds.find(spellId) != gConfig.skeletalPetShellSpellIds.end();
    }

    uint32 BuildHealth(Player* player, float roleMultiplier)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float health = static_cast<float>(gConfig.baseHealth)
            + static_cast<float>(gConfig.healthPerLevel * player->GetLevel())
            + static_cast<float>(gConfig.healthPerIntellect) * intellect
            + static_cast<float>(gConfig.healthPerShadowSpellPower) * std::max<int32>(0, shadowPower);
        return std::max<uint32>(1u, static_cast<uint32>(std::round(health * roleMultiplier)));
    }

    float BuildDamage(Player* player, uint32 baseValue, float roleMultiplier)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float damage = static_cast<float>(baseValue)
            + static_cast<float>(player->GetLevel()) * (static_cast<float>(gConfig.damagePerLevelPct) / 100.0f)
            + intellect * (static_cast<float>(gConfig.damagePerIntellectPct) / 100.0f)
            + static_cast<float>(std::max<int32>(0, shadowPower)) * (static_cast<float>(gConfig.damagePerShadowSpellPowerPct) / 100.0f);
        return std::max(1.0f, damage * roleMultiplier);
    }

    uint32 BuildSkeletalPetHealth(Player* player)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float health = static_cast<float>(gConfig.skeletalPetBaseHealth)
            + static_cast<float>(gConfig.skeletalPetHealthPerLevel * player->GetLevel())
            + static_cast<float>(gConfig.skeletalPetHealthPerIntellect) * intellect
            + static_cast<float>(gConfig.skeletalPetHealthPerShadowSpellPower) * std::max<int32>(0, shadowPower);
        return std::max<uint32>(1u, static_cast<uint32>(std::round(health)));
    }

    float BuildSkeletalPetDamage(Player* player, uint32 baseValue)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float damage = static_cast<float>(baseValue)
            + static_cast<float>(player->GetLevel()) * (static_cast<float>(gConfig.skeletalPetDamagePerLevelPct) / 100.0f)
            + intellect * (static_cast<float>(gConfig.skeletalPetDamagePerIntellectPct) / 100.0f)
            + static_cast<float>(std::max<int32>(0, shadowPower)) * (static_cast<float>(gConfig.skeletalPetDamagePerShadowSpellPowerPct) / 100.0f);
        return std::max(1.0f, damage);
    }

    float BuildSkeletalPetScale(Player* player)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float extraScale = static_cast<float>(player->GetLevel()) * 0.0065f
            + intellect * 0.0015f
            + static_cast<float>(std::max<int32>(0, shadowPower)) * 0.0009f;
        return std::clamp(gConfig.skeletalPetScale + extraScale, 0.9f, 1.4f);
    }

    void ApplySkeletalPetAppearance(Pet* pet)
    {
        if (!pet)
            return;

        if (gConfig.skeletalPetAppearanceDisplayId != 0)
        {
            pet->SetDisplayId(gConfig.skeletalPetAppearanceDisplayId);
            pet->SetNativeDisplayId(gConfig.skeletalPetAppearanceDisplayId);
        }

        pet->SetVirtualItem(0, gConfig.skeletalPetVirtualItem1);
        pet->SetVirtualItem(1, gConfig.skeletalPetVirtualItem2);
        pet->SetVirtualItem(2, gConfig.skeletalPetVirtualItem3);
    }

    void RemoveLegacySkeletalPetSpells(Pet* pet)
    {
        if (!pet)
            return;

        pet->unlearnSpell(LEGACY_BAD_MANUAL_SPELL_1, false);
        pet->unlearnSpell(LEGACY_BAD_MANUAL_SPELL_2, false);
    }

    void TeachSkeletalPetSpells(Player* player, Pet* pet)
    {
        if (!player || !pet)
            return;

        bool initialized = false;

        for (uint32 spellId : gConfig.skeletalPetPassiveSpellIds)
        {
            if (!spellId)
                continue;

            if (pet->learnSpell(spellId))
                initialized = true;
        }

        for (uint32 spellId : gConfig.skeletalPetAutoSpellIds)
        {
            if (!spellId)
                continue;

            if (pet->addSpell(spellId, ACT_ENABLED, PETSPELL_NEW, PETSPELL_NORMAL))
                initialized = true;
        }

        for (uint32 spellId : gConfig.skeletalPetManualSpellIds)
        {
            if (!spellId)
                continue;

            if (pet->addSpell(spellId, ACT_DISABLED, PETSPELL_NEW, PETSPELL_NORMAL))
                initialized = true;
        }

        if (initialized)
            player->PetSpellInitialize();
    }

    void ConfigureSkeletalPetPower(Pet* pet)
    {
        if (!pet)
            return;

        pet->setPowerType(POWER_ENERGY);
        if (pet->GetMaxPower(POWER_ENERGY) < 100)
            pet->SetMaxPower(POWER_ENERGY, 100);
        pet->SetPower(POWER_ENERGY, pet->GetMaxPower(POWER_ENERGY));
    }

    bool IsManagedSkeletalPet(Pet* pet, uint32 shellSpellId)
    {
        if (!pet)
            return false;

        if (pet->GetEntry() == gConfig.skeletalPetEntry || pet->GetEntry() == LEGACY_SKELETAL_PET_ENTRY)
            return true;

        if (shellSpellId != 0 && pet->GetUInt32Value(UNIT_CREATED_BY_SPELL) == shellSpellId)
            return true;

        return pet->GetName() == gConfig.skeletalPetName;
    }

    Unit* GetDeadSelectedTarget(Player* player)
    {
        if (!player)
            return nullptr;

        Unit* target = player->GetSelectedUnit();
        if (!target || target->IsAlive())
            return nullptr;

        return target;
    }

    void DespawnOwnedSkeletons(Player* player)
    {
        std::list<Creature*> creatures;
        player->GetCreatureListWithEntryInGrid(creatures, gConfig.primaryCreatureEntry, 80.0f);
        player->GetCreatureListWithEntryInGrid(creatures, gConfig.secondaryCreatureEntry, 80.0f);
        for (Creature* creature : creatures)
        {
            if (!creature)
                continue;
            if (creature->GetOwnerGUID() != player->GetGUID())
                continue;
            if (TempSummon* summon = creature->ToTempSummon())
                summon->UnSummon();
        }
    }

    void PrepareSkeleton(Player* player, TempSummon* summon, std::string const& name, float scale, float healthMultiplier, float damageMultiplier, float followAngle)
    {
        if (!player || !summon)
            return;

        summon->SetOwnerGUID(player->GetGUID());
        summon->SetCreatorGUID(player->GetGUID());
        summon->SetFaction(player->GetFaction());
        summon->SetLevel(player->GetLevel());
        summon->SetPhaseMask(player->GetPhaseMask(), false);
        summon->SetName(name);
        summon->SetObjectScale(scale);
        summon->SetReactState(REACT_AGGRESSIVE);

        uint32 maxHealth = BuildHealth(player, healthMultiplier);
        float minDamage = BuildDamage(player, gConfig.baseMinDamage, damageMultiplier);
        float maxDamage = std::max(minDamage + 1.0f, BuildDamage(player, gConfig.baseMaxDamage, damageMultiplier));

        summon->SetCreateHealth(maxHealth);
        summon->SetMaxHealth(maxHealth);
        summon->SetHealth(maxHealth);
        summon->SetBaseWeaponDamage(BASE_ATTACK, MINDAMAGE, minDamage);
        summon->SetBaseWeaponDamage(BASE_ATTACK, MAXDAMAGE, maxDamage);
        summon->UpdateAllStats();

        if (Unit* target = player->GetSelectedUnit())
        {
            if (target->IsAlive() && player->IsValidAttackTarget(target))
            {
                if (summon->AI())
                {
                    summon->AI()->AttackStart(target);
                    return;
                }
            }
        }

        summon->GetMotionMaster()->MoveFollow(player, gConfig.spawnDistance, followAngle);
    }

    void SummonTwinSkeletons(Player* player)
    {
        if (!player)
            return;

        DespawnOwnedSkeletons(player);

        if (Pet* pet = player->GetPet())
            player->RemovePet(pet, PET_SAVE_NOT_IN_SLOT);

        float const leftAngle = player->GetOrientation() + 1.15f;
        float const rightAngle = player->GetOrientation() - 1.15f;

        Position leftPosition;
        leftPosition.Relocate(
            player->GetPositionX() + std::cos(leftAngle) * gConfig.spawnDistance,
            player->GetPositionY() + std::sin(leftAngle) * gConfig.spawnDistance,
            player->GetPositionZ(),
            player->GetOrientation()
        );

        Position rightPosition;
        rightPosition.Relocate(
            player->GetPositionX() + std::cos(rightAngle) * gConfig.spawnDistance,
            player->GetPositionY() + std::sin(rightAngle) * gConfig.spawnDistance,
            player->GetPositionZ(),
            player->GetOrientation()
        );

        if (TempSummon* left = player->SummonCreature(
            gConfig.primaryCreatureEntry,
            leftPosition,
            TEMPSUMMON_TIMED_OR_DEAD_DESPAWN,
            gConfig.durationMs))
        {
            PrepareSkeleton(player, left, "Boneguard Skeleton", 1.05f, 1.15f, 0.92f, 1.15f);
        }

        if (TempSummon* right = player->SummonCreature(
            gConfig.secondaryCreatureEntry,
            rightPosition,
            TEMPSUMMON_TIMED_OR_DEAD_DESPAWN,
            gConfig.durationMs))
        {
            PrepareSkeleton(player, right, "Soulrend Skeleton", 0.92f, 0.9f, 1.15f, -1.15f);
        }
    }

    void PrepareSkeletalPet(Player* player, Pet* pet, uint32 shellSpellId)
    {
        if (!player || !pet)
            return;

        pet->SetCreatorGUID(player->GetGUID());
        pet->SetOwnerGUID(player->GetGUID());
        pet->SetUInt32Value(UNIT_CREATED_BY_SPELL, shellSpellId);
        pet->SetFaction(player->GetFaction());
        pet->SetPhaseMask(player->GetPhaseMask(), false);
        pet->SetLevel(player->GetLevel());
        pet->SetName(gConfig.skeletalPetName);
        pet->SetObjectScale(BuildSkeletalPetScale(player));
        pet->SetReactState(REACT_DEFENSIVE);

        uint32 maxHealth = BuildSkeletalPetHealth(player);
        float minDamage = BuildSkeletalPetDamage(player, gConfig.skeletalPetBaseMinDamage);
        float maxDamage = std::max(minDamage + 1.0f, BuildSkeletalPetDamage(player, gConfig.skeletalPetBaseMaxDamage));

        pet->SetCreateHealth(maxHealth);
        pet->SetMaxHealth(maxHealth);
        pet->SetHealth(maxHealth);
        pet->SetBaseWeaponDamage(BASE_ATTACK, MINDAMAGE, minDamage);
        pet->SetBaseWeaponDamage(BASE_ATTACK, MAXDAMAGE, maxDamage);
        pet->UpdateAllStats();
        ApplySkeletalPetAppearance(pet);
        pet->SetAttackTime(BASE_ATTACK, gConfig.skeletalPetAttackTimeMs);
        ConfigureSkeletalPetPower(pet);
        RemoveLegacySkeletalPetSpells(pet);
        pet->SetFullHealth();
        TeachSkeletalPetSpells(player, pet);
        pet->SavePetToDB(PET_SAVE_AS_CURRENT);
        player->PetSpellInitialize();
    }
}

class wm_prototypes_world_script : public WorldScript
{
public:
    wm_prototypes_world_script() : WorldScript("wm_prototypes_world_script")
    {
        LoadPrototypeConfig();
    }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        LoadPrototypeConfig();
    }
};

class spell_wm_twin_skeleton_shell : public SpellScript
{
    PrepareSpellScript(spell_wm_twin_skeleton_shell);

    void HandleAfterCast()
    {
        Player* player = GetCaster() ? GetCaster()->ToPlayer() : nullptr;
        uint32 spellId = GetSpellInfo() ? GetSpellInfo()->Id : 0;
        if (!IsTwinSkeletonSpell(player, spellId))
            return;

        SummonTwinSkeletons(player);
    }

    void Register() override
    {
        AfterCast += SpellCastFn(spell_wm_twin_skeleton_shell::HandleAfterCast);
    }
};

class spell_wm_skeletal_pet_shell : public SpellScript
{
    PrepareSpellScript(spell_wm_skeletal_pet_shell);

    SpellCastResult CheckCast()
    {
        Player* player = GetCaster() ? GetCaster()->ToPlayer() : nullptr;
        uint32 spellId = GetSpellInfo() ? GetSpellInfo()->Id : 0;
        if (!IsSkeletalPetSpell(player, spellId))
            return SPELL_CAST_OK;

        if (!GetDeadSelectedTarget(player))
        {
            LOG_INFO(
                "module.wm_prototypes",
                "skeletal pet checkcast rejected: player_guid={} spell_id={} reason=no_dead_target",
                player ? player->GetGUID().GetCounter() : 0,
                spellId
            );
            return SPELL_FAILED_TARGET_NOT_DEAD;
        }

        LOG_INFO(
            "module.wm_prototypes",
            "skeletal pet checkcast ok: player_guid={} spell_id={}",
            player ? player->GetGUID().GetCounter() : 0,
            spellId
        );
        return SPELL_CAST_OK;
    }

    void HandleSummonPet(SpellEffIndex effIndex)
    {
        Player* player = GetCaster() ? GetCaster()->ToPlayer() : nullptr;
        uint32 spellId = GetSpellInfo() ? GetSpellInfo()->Id : 0;
        if (!IsSkeletalPetSpell(player, spellId))
            return;

        PreventHitDefaultEffect(effIndex);

        Unit* target = GetDeadSelectedTarget(player);
        float x = player->GetPositionX();
        float y = player->GetPositionY();
        float z = player->GetPositionZ();
        float o = player->GetOrientation();

        if (target)
        {
            x = target->GetPositionX();
            y = target->GetPositionY();
            z = target->GetPositionZ();
        }

        LOG_INFO(
            "module.wm_prototypes",
            "skeletal pet summon attempt: player_guid={} spell_id={} eff_index={} target_guid={} target_entry={}",
            player ? player->GetGUID().GetCounter() : 0,
            spellId,
            uint32(effIndex),
            target ? target->GetGUID().GetCounter() : 0,
            target && target->ToCreature() ? target->ToCreature()->GetEntry() : 0
        );

        if (Pet* currentPet = player->GetPet())
        {
            if (IsManagedSkeletalPet(currentPet, spellId))
            {
                LOG_INFO(
                    "module.wm_prototypes",
                    "skeletal pet replacing active servant: player_guid={} spell_id={} active_pet_guid={} active_pet_entry={}",
                    player ? player->GetGUID().GetCounter() : 0,
                    spellId,
                    currentPet->GetGUID().GetCounter(),
                    currentPet->GetEntry()
                );
                player->RemovePet(currentPet, PET_SAVE_AS_DELETED);
            }
        }

        if (Pet* pet = player->SummonPet(gConfig.skeletalPetEntry, x, y, z, o, SUMMON_PET))
        {
            PrepareSkeletalPet(player, pet, spellId);
            LOG_INFO(
                "module.wm_prototypes",
                "skeletal pet summon success: player_guid={} spell_id={} pet_guid={} pet_entry={}",
                player ? player->GetGUID().GetCounter() : 0,
                spellId,
                pet->GetGUID().GetCounter(),
                pet->GetEntry()
            );
        }
        else if (Pet* loadedPet = player->GetPet())
        {
            if (IsManagedSkeletalPet(loadedPet, spellId) && loadedPet->GetOwnerGUID() == player->GetGUID())
            {
                PrepareSkeletalPet(player, loadedPet, spellId);
                LOG_INFO(
                    "module.wm_prototypes",
                    "skeletal pet resummon refresh: player_guid={} spell_id={} pet_guid={} pet_entry={}",
                    player ? player->GetGUID().GetCounter() : 0,
                    spellId,
                    loadedPet->GetGUID().GetCounter(),
                    loadedPet->GetEntry()
                );
                return;
            }

            LOG_INFO(
                "module.wm_prototypes",
                "skeletal pet summon blocked by existing different pet: player_guid={} spell_id={} active_pet_guid={} active_pet_entry={}",
                player ? player->GetGUID().GetCounter() : 0,
                spellId,
                loadedPet->GetGUID().GetCounter(),
                loadedPet->GetEntry()
            );
        }
        else
        {
            LOG_INFO(
                "module.wm_prototypes",
                "skeletal pet summon failed: player_guid={} spell_id={} pet_entry={}",
                player ? player->GetGUID().GetCounter() : 0,
                spellId,
                gConfig.skeletalPetEntry
            );
        }
    }

    void Register() override
    {
        OnCheckCast += SpellCheckCastFn(spell_wm_skeletal_pet_shell::CheckCast);
        OnEffectHit += SpellEffectFn(spell_wm_skeletal_pet_shell::HandleSummonPet, EFFECT_0, SPELL_EFFECT_SUMMON_PET);
        OnEffectHit += SpellEffectFn(spell_wm_skeletal_pet_shell::HandleSummonPet, EFFECT_0, SPELL_EFFECT_SUMMON);
    }
};

void AddSC_mod_wm_prototypes_spell_scripts()
{
    new wm_prototypes_world_script();
    RegisterSpellScript(spell_wm_twin_skeleton_shell);
    RegisterSpellScript(spell_wm_skeletal_pet_shell);
}
