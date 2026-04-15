#include "wm_spell_runtime.h"

#include "Config.h"
#include "Creature.h"
#include "CreatureAI.h"
#include "DatabaseEnv.h"
#include "MotionMaster.h"
#include "ObjectAccessor.h"
#include "PetDefines.h"
#include "TemporarySummon.h"

#include <algorithm>
#include <cmath>
#include <optional>
#include <regex>
#include <string>
#include <vector>

namespace
{
    using namespace std::chrono_literals;

    constexpr uint32 COMBAT_PROFICIENCY_SHELL_ID = 944000;
    constexpr uint32 DUAL_WIELD_SPELL_ID = 674;

    WmSpells::RuntimeConfig gConfig;
    uint32 gDebugPollTimer = 0;
    std::unordered_map<uint32, ObjectGuid> gBoneboundOmegaByPlayer;
    std::unordered_map<uint32, int32> gIntellectBlockRatingByPlayer;

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

    uint32 BuildHealth(Player* player, WmSpells::BoneboundBehaviorConfig const& config)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float health = static_cast<float>(config.baseHealth)
            + static_cast<float>(config.healthPerLevel * player->GetLevel())
            + static_cast<float>(config.healthPerIntellect) * intellect
            + static_cast<float>(config.healthPerShadowPower) * std::max<int32>(0, shadowPower);
        return std::max<uint32>(1u, static_cast<uint32>(std::round(health)));
    }

    float BuildDamage(Player* player, uint32 baseValue, WmSpells::BoneboundBehaviorConfig const& config)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float damage = static_cast<float>(baseValue)
            + static_cast<float>(player->GetLevel()) * (static_cast<float>(config.damagePerLevelPct) / 100.0f)
            + intellect * (static_cast<float>(config.damagePerIntellectPct) / 100.0f)
            + static_cast<float>(std::max<int32>(0, shadowPower)) * (static_cast<float>(config.damagePerShadowPowerPct) / 100.0f);
        return std::max(1.0f, damage);
    }

    float BuildScale(Player* player, WmSpells::BoneboundBehaviorConfig const& config)
    {
        float intellect = player->GetTotalStatValue(STAT_INTELLECT);
        int32 shadowPower = player->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW);
        float scale = config.scaleBase
            + static_cast<float>(player->GetLevel()) * config.scalePerLevel
            + intellect * config.scalePerIntellect
            + static_cast<float>(std::max<int32>(0, shadowPower)) * config.scalePerShadowPower;
        return std::clamp(scale, 0.9f, 1.45f);
    }

    float ResolveAlphaVisualScale(Player* owner, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (config.preserveBaseStats)
            return std::max(0.1f, config.scaleBase);

        return BuildScale(owner, config);
    }

    float ResolveOmegaVisualScale(Player* owner, Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config)
    {
        float baseScale = alphaPet ? alphaPet->GetObjectScale() : ResolveAlphaVisualScale(owner, config);
        if (config.preserveBaseStats)
            baseScale = ResolveAlphaVisualScale(owner, config);

        float multiplier = std::max(0.1f, config.omegaScaleMultiplier);
        return std::clamp(baseScale * multiplier, 0.1f, 5.0f);
    }

    void ApplyBoneboundCreatureAppearance(
        Creature* creature,
        std::string const& name,
        uint32 displayId,
        uint32 virtualItem1,
        uint32 virtualItem2,
        uint32 virtualItem3,
        float scale)
    {
        if (!creature)
            return;

        creature->SetName(name);
        if (displayId != 0)
        {
            creature->SetDisplayId(displayId);
            creature->SetNativeDisplayId(displayId);
        }

        creature->SetVirtualItem(0, virtualItem1);
        creature->SetVirtualItem(1, virtualItem2);
        creature->SetVirtualItem(2, virtualItem3);
        creature->SetObjectScale(scale);
    }

    void ApplyOwnerTransferBonuses(Unit* summon, Player* owner, WmSpells::BoneboundBehaviorConfig const& config, bool refillHealth)
    {
        if (!summon || !owner)
            return;

        float statBonus = 0.0f;
        if (config.ownerIntellectToAllStats)
            statBonus = owner->GetTotalStatValue(STAT_INTELLECT) * config.ownerIntellectToAllStatsScale;

        for (uint8 stat = 0; stat < MAX_STATS; ++stat)
            summon->SetStatFlatModifier(UnitMods(UNIT_MOD_STAT_START + stat), TOTAL_VALUE, statBonus);

        float attackPowerBonus = 0.0f;
        if (config.ownerShadowPowerToAttackPower)
            attackPowerBonus = static_cast<float>(std::max<int32>(0, owner->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW))) * config.ownerShadowPowerToAttackPowerScale;

        summon->SetStatFlatModifier(UNIT_MOD_ATTACK_POWER, TOTAL_VALUE, attackPowerBonus);
        summon->UpdateAllStats();
        summon->UpdateAttackPowerAndDamage();

        if (refillHealth)
            summon->SetHealth(summon->GetMaxHealth());
        else if (summon->GetHealth() > summon->GetMaxHealth())
            summon->SetHealth(summon->GetMaxHealth());
    }

    void MirrorMeleeAttackPower(Unit* source, Unit* target)
    {
        if (!source || !target)
            return;

        target->SetStatFlatModifier(UNIT_MOD_ATTACK_POWER, BASE_VALUE, source->GetFlatModifierValue(UNIT_MOD_ATTACK_POWER, BASE_VALUE));
        target->SetStatFlatModifier(UNIT_MOD_ATTACK_POWER, TOTAL_VALUE, source->GetFlatModifierValue(UNIT_MOD_ATTACK_POWER, TOTAL_VALUE));
        target->SetStatPctModifier(UNIT_MOD_ATTACK_POWER, BASE_PCT, source->GetPctModifierValue(UNIT_MOD_ATTACK_POWER, BASE_PCT));
        target->SetStatPctModifier(UNIT_MOD_ATTACK_POWER, TOTAL_PCT, source->GetPctModifierValue(UNIT_MOD_ATTACK_POWER, TOTAL_PCT));
    }

    uint32 ResolveOmegaMaxHealth(Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!alphaPet)
            return 1u;

        uint32 healthPct = std::max<uint32>(1u, config.omegaHealthPct);
        return std::max<uint32>(1u, (alphaPet->GetMaxHealth() * healthPct) / 100u);
    }

    void ApplyOmegaHealth(TempSummon* omega, uint32 desiredMaxHealth, uint32 previousHealth, uint32 previousMaxHealth, bool refillHealth)
    {
        if (!omega)
            return;

        previousMaxHealth = std::max<uint32>(1u, previousMaxHealth);
        desiredMaxHealth = std::max<uint32>(1u, desiredMaxHealth);
        omega->SetMaxHealth(desiredMaxHealth);

        if (refillHealth)
        {
            omega->SetHealth(desiredMaxHealth);
            return;
        }

        if (previousHealth == 0)
        {
            omega->SetHealth(0);
            return;
        }

        uint64 scaledHealth = (static_cast<uint64>(previousHealth) * desiredMaxHealth) / previousMaxHealth;
        scaledHealth = std::clamp<uint64>(scaledHealth, 1u, desiredMaxHealth);
        omega->SetHealth(static_cast<uint32>(scaledHealth));
    }

    void ApplyBoneboundOmegaRuntime(Player* owner, Pet* alphaPet, TempSummon* omega, WmSpells::BoneboundBehaviorConfig const& config, bool refillHealth)
    {
        if (!owner || !alphaPet || !omega)
            return;

        uint32 previousHealth = omega->GetHealth();
        uint32 previousMaxHealth = omega->GetMaxHealth();
        float minDamage = alphaPet->GetWeaponDamageRange(BASE_ATTACK, MINDAMAGE);
        float maxDamage = alphaPet->GetWeaponDamageRange(BASE_ATTACK, MAXDAMAGE);
        if (!config.preserveBaseStats)
        {
            float damageScale = static_cast<float>(std::max<uint32>(1u, config.omegaDamagePct)) / 100.0f;
            minDamage *= damageScale;
            maxDamage *= damageScale;
        }

        omega->SetCreatorGUID(owner->GetGUID());
        omega->SetOwnerGUID(owner->GetGUID());
        omega->SetFaction(owner->GetFaction());
        ApplyBoneboundCreatureAppearance(
            omega,
            config.omegaName,
            config.omegaDisplayId,
            config.omegaVirtualItem1,
            config.omegaVirtualItem2,
            config.omegaVirtualItem3,
            ResolveOmegaVisualScale(owner, alphaPet, config));
        omega->SetLevel(alphaPet->GetLevel());

        // Creature stat recalculation can restore template health, so do it before
        // writing the final Alpha-derived Omega health and damage.
        ApplyOwnerTransferBonuses(omega, owner, config, false);
        ApplyOmegaHealth(omega, ResolveOmegaMaxHealth(alphaPet, config), previousHealth, previousMaxHealth, refillHealth);
        omega->SetBaseWeaponDamage(BASE_ATTACK, MINDAMAGE, minDamage);
        omega->SetBaseWeaponDamage(BASE_ATTACK, MAXDAMAGE, maxDamage);
        omega->SetAttackTime(BASE_ATTACK, alphaPet->GetAttackTime(BASE_ATTACK));
        MirrorMeleeAttackPower(alphaPet, omega);
        omega->UpdateDamagePhysical(BASE_ATTACK);
    }

    WmSpells::BoneboundBehaviorConfig DefaultBoneboundBehaviorConfig(uint32 shellSpellId, bool persistPet)
    {
        WmSpells::BoneboundBehaviorConfig config;
        config.shellSpellId = shellSpellId;
        config.persistPet = persistPet;
        config.requireCorpse = gConfig.boneboundRequireCorpse;
        config.creatureEntry = gConfig.boneboundCreatureEntry;
        config.name = gConfig.boneboundName;
        config.displayId = gConfig.boneboundDisplayId;
        config.virtualItem1 = gConfig.boneboundVirtualItem1;
        config.virtualItem2 = gConfig.boneboundVirtualItem2;
        config.virtualItem3 = gConfig.boneboundVirtualItem3;
        config.attackTimeMs = gConfig.boneboundAttackTimeMs;
        config.scaleBase = gConfig.boneboundScaleBase;
        config.scalePerLevel = gConfig.boneboundScalePerLevel;
        config.scalePerIntellect = gConfig.boneboundScalePerIntellect;
        config.scalePerShadowPower = gConfig.boneboundScalePerShadowPower;
        config.baseHealth = gConfig.boneboundBaseHealth;
        config.healthPerLevel = gConfig.boneboundHealthPerLevel;
        config.healthPerIntellect = gConfig.boneboundHealthPerIntellect;
        config.healthPerShadowPower = gConfig.boneboundHealthPerShadowPower;
        config.baseMinDamage = gConfig.boneboundBaseMinDamage;
        config.baseMaxDamage = gConfig.boneboundBaseMaxDamage;
        config.damagePerLevelPct = gConfig.boneboundDamagePerLevelPct;
        config.damagePerIntellectPct = gConfig.boneboundDamagePerIntellectPct;
        config.damagePerShadowPowerPct = gConfig.boneboundDamagePerShadowPowerPct;
        config.omegaCreatureEntry = gConfig.boneboundCreatureEntry;
        config.omegaDisplayId = gConfig.boneboundDisplayId;
        config.omegaVirtualItem1 = gConfig.boneboundVirtualItem1;
        config.omegaVirtualItem2 = gConfig.boneboundVirtualItem2;
        config.omegaVirtualItem3 = gConfig.boneboundVirtualItem3;
        return config;
    }

    bool IsBoneboundBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "summon_bonebound_servant_v1" || behaviorKind == "summon_bonebound_twin_v2";
    }

    bool IsIntellectBlockBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "passive_intellect_block_v1";
    }

    bool IsBoneboundShellOrBehavior(uint32 shellSpellId)
    {
        if (shellSpellId == 0)
            return false;

        if (gConfig.boneboundShellSpellIds.find(shellSpellId) != gConfig.boneboundShellSpellIds.end())
            return true;

        std::optional<WmSpells::BehaviorRecord> behaviorRecord = WmSpells::LoadBehaviorRecord(shellSpellId);
        return behaviorRecord.has_value()
            && IsBoneboundBehaviorKind(behaviorRecord->behaviorKind)
            && behaviorRecord->status != "disabled";
    }

    std::optional<std::string> ExtractJsonString(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
        std::smatch match;
        if (std::regex_search(json, match, pattern) && match.size() > 1)
            return match[1].str();
        return std::nullopt;
    }

    std::optional<uint32> ExtractJsonUInt(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*(-?\\d+)");
        std::smatch match;
        if (std::regex_search(json, match, pattern) && match.size() > 1)
        {
            long long value = std::stoll(match[1].str());
            if (value < 0)
                return 0u;
            return static_cast<uint32>(value);
        }
        return std::nullopt;
    }

    std::optional<float> ExtractJsonFloat(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)");
        std::smatch match;
        if (std::regex_search(json, match, pattern) && match.size() > 1)
            return std::stof(match[1].str());
        return std::nullopt;
    }

    std::optional<bool> ExtractJsonBool(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*(true|false)");
        std::smatch match;
        if (std::regex_search(json, match, pattern) && match.size() > 1)
            return match[1].str() == "true";
        return std::nullopt;
    }

    std::optional<WmSpells::BoneboundBehaviorConfig> BuildBoneboundBehaviorConfig(
        WmSpells::BehaviorRecord const& record,
        bool persistPetFallback)
    {
        if (!IsBoneboundBehaviorKind(record.behaviorKind))
            return std::nullopt;

        WmSpells::BoneboundBehaviorConfig config = DefaultBoneboundBehaviorConfig(record.shellSpellId, persistPetFallback);
        if (record.behaviorKind == "summon_bonebound_twin_v2")
        {
            config.spawnOmega = true;
            config.preserveBaseStats = true;
        }

        if (record.status == "disabled")
            return std::nullopt;

        std::string const& configJson = record.configJson;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "name"))
            config.name = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "creature_entry"))
            config.creatureEntry = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "display_id"))
            config.displayId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "virtual_item_1"))
            config.virtualItem1 = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "virtual_item_2"))
            config.virtualItem2 = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "virtual_item_3"))
            config.virtualItem3 = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "attack_time_ms"))
            config.attackTimeMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "base_health"))
            config.baseHealth = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "health_per_level"))
            config.healthPerLevel = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "health_per_intellect"))
            config.healthPerIntellect = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "health_per_shadow_power"))
            config.healthPerShadowPower = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "base_min_damage"))
            config.baseMinDamage = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "base_max_damage"))
            config.baseMaxDamage = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "damage_per_level_pct"))
            config.damagePerLevelPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "damage_per_intellect_pct"))
            config.damagePerIntellectPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "damage_per_shadow_power_pct"))
            config.damagePerShadowPowerPct = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "owner_intellect_to_all_stats"))
            config.ownerIntellectToAllStats = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "owner_shadow_power_to_attack_power"))
            config.ownerShadowPowerToAttackPower = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "owner_intellect_to_all_stats_scale"))
            config.ownerIntellectToAllStatsScale = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "owner_shadow_power_to_attack_power_scale"))
            config.ownerShadowPowerToAttackPowerScale = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "scale_base"))
            config.scaleBase = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "scale_per_level"))
            config.scalePerLevel = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "scale_per_intellect"))
            config.scalePerIntellect = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "scale_per_shadow_power"))
            config.scalePerShadowPower = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "require_corpse"))
            config.requireCorpse = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "persist_pet"))
            config.persistPet = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "spawn_omega"))
            config.spawnOmega = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "preserve_base_stats"))
            config.preserveBaseStats = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "omega_creature_entry"))
            config.omegaCreatureEntry = *value;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "omega_name"))
            config.omegaName = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "omega_display_id"))
            config.omegaDisplayId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "omega_virtual_item_1"))
            config.omegaVirtualItem1 = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "omega_virtual_item_2"))
            config.omegaVirtualItem2 = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "omega_virtual_item_3"))
            config.omegaVirtualItem3 = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "omega_scale_multiplier"))
            config.omegaScaleMultiplier = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "omega_health_pct"))
            config.omegaHealthPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "omega_damage_pct"))
            config.omegaDamagePct = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "omega_follow_distance"))
            config.omegaFollowDistance = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "omega_follow_angle"))
            config.omegaFollowAngle = *value;

        return config;
    }

    std::optional<WmSpells::IntellectBlockPassiveConfig> BuildIntellectBlockPassiveConfig(WmSpells::BehaviorRecord const& record)
    {
        if (!IsIntellectBlockBehaviorKind(record.behaviorKind) || record.status == "disabled")
            return std::nullopt;

        WmSpells::IntellectBlockPassiveConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "intellect_to_block_rating_scale"))
            config.intellectToBlockRatingScale = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "spell_power_to_block_rating_scale"))
            config.spellPowerToBlockRatingScale = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "spell_school_mask"))
            config.spellSchoolMask = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "max_block_rating"))
            config.maxBlockRating = *value;

        return config;
    }

    bool IsBoneboundPet(Pet* pet)
    {
        if (!pet)
            return false;

        uint32 createdBySpellId = pet->GetUInt32Value(UNIT_CREATED_BY_SPELL);
        if (IsBoneboundShellOrBehavior(createdBySpellId))
            return true;

        if (pet->GetEntry() == gConfig.boneboundCreatureEntry && gConfig.boneboundDisplayId != 0 && pet->GetDisplayId() == gConfig.boneboundDisplayId)
            return true;

        return false;
    }

    void RemoveBoneboundOmega(Player* owner);

    bool RestoreTemporarilyUnsummonedBoneboundPet(Player* owner)
    {
        if (!owner || owner->GetPetGUID() || owner->GetPet())
            return false;

        uint32 petNumber = owner->GetTemporaryUnsummonedPetNumber();
        uint32 shellSpellId = owner->GetLastPetSpell();
        if (petNumber == 0 || !IsBoneboundShellOrBehavior(shellSpellId))
            return false;

        if (owner->IsPetNeedBeTemporaryUnsummoned())
        {
            RemoveBoneboundOmega(owner);
            return false;
        }

        Pet* restoredPet = new Pet(owner);
        if (!restoredPet->LoadPetFromDB(owner, 0, petNumber, true))
        {
            delete restoredPet;
            return false;
        }

        owner->SetTemporaryUnsummonedPetNumber(0);
        WmSpells::ReapplyBoneboundOverlay(restoredPet);
        return true;
    }

    void ApplyBoneboundOverlay(Player* owner, Pet* pet, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner || !pet)
            return;

        if (config.shellSpellId != 0)
            pet->SetUInt32Value(UNIT_CREATED_BY_SPELL, config.shellSpellId);

        float desiredScale = ResolveAlphaVisualScale(owner, config);
        ApplyBoneboundCreatureAppearance(
            pet,
            config.name,
            config.displayId,
            config.virtualItem1,
            config.virtualItem2,
            config.virtualItem3,
            desiredScale);
        if (config.preserveBaseStats)
        {
        }
        else
        {
            pet->SetMaxHealth(BuildHealth(owner, config));
            pet->SetBaseWeaponDamage(BASE_ATTACK, MINDAMAGE, BuildDamage(owner, config.baseMinDamage, config));
            pet->SetBaseWeaponDamage(BASE_ATTACK, MAXDAMAGE, BuildDamage(owner, config.baseMaxDamage, config));
            pet->SetAttackTime(BASE_ATTACK, config.attackTimeMs);
            pet->UpdateDamagePhysical(BASE_ATTACK);
        }

        ApplyOwnerTransferBonuses(pet, owner, config, true);

        owner->PetSpellInitialize();
        if (config.persistPet)
            pet->SavePetToDB(PET_SAVE_AS_CURRENT);
    }

    void RemoveBoneboundOmega(Player* owner)
    {
        if (!owner)
            return;

        uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        auto it = gBoneboundOmegaByPlayer.find(ownerGuid);
        if (it == gBoneboundOmegaByPlayer.end())
            return;

        if (Creature* omega = ObjectAccessor::GetCreature(*owner, it->second))
            omega->DespawnOrUnsummon();

        gBoneboundOmegaByPlayer.erase(it);
    }

    TempSummon* EnsureBoneboundOmega(Player* owner, Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner || !alphaPet || !config.spawnOmega)
            return nullptr;

        uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        if (auto it = gBoneboundOmegaByPlayer.find(ownerGuid); it != gBoneboundOmegaByPlayer.end())
        {
            if (Creature* existing = ObjectAccessor::GetCreature(*owner, it->second))
                return existing->ToTempSummon();
            gBoneboundOmegaByPlayer.erase(it);
        }

        Position pos;
        owner->GetClosePoint(pos.m_positionX, pos.m_positionY, pos.m_positionZ, 1.0f, config.omegaFollowDistance);
        TempSummon* omega = owner->SummonCreature(
            config.omegaCreatureEntry,
            pos.m_positionX,
            pos.m_positionY,
            pos.m_positionZ,
            owner->GetOrientation(),
            TEMPSUMMON_MANUAL_DESPAWN,
            0);
        if (!omega)
            return nullptr;

        ApplyBoneboundOmegaRuntime(owner, alphaPet, omega, config, true);
        omega->SetReactState(REACT_DEFENSIVE);
        omega->GetMotionMaster()->MoveFollow(owner, config.omegaFollowDistance, config.omegaFollowAngle);

        gBoneboundOmegaByPlayer[ownerGuid] = omega->GetGUID();
        return omega;
    }

    void SyncBoneboundOmega(Player* owner, Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner)
            return;

        if (!alphaPet || !config.spawnOmega)
        {
            RemoveBoneboundOmega(owner);
            return;
        }

        TempSummon* omega = EnsureBoneboundOmega(owner, alphaPet, config);
        if (!omega)
            return;

        ApplyBoneboundOmegaRuntime(owner, alphaPet, omega, config, false);

        if (Unit* victim = alphaPet->GetVictim())
        {
            if (omega->AI())
                omega->AI()->AttackStart(victim);
        }
        else
        {
            if (omega->IsInCombat())
                omega->CombatStop(true);
            omega->SetWalk(false);
            omega->GetMotionMaster()->MoveFollow(owner, config.omegaFollowDistance, config.omegaFollowAngle);
        }
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

    std::string JsonResult(bool ok, std::string const& behaviorKind, std::string const& message, uint32 shellSpellId = 0)
    {
        std::string payload = "{\"ok\":";
        payload += ok ? "true" : "false";
        payload += ",\"behavior_kind\":\"" + behaviorKind + "\"";
        payload += ",\"message\":\"" + message + "\"}";
        if (shellSpellId != 0)
            payload.insert(payload.size() - 1, ",\"shell_spell_id\":" + std::to_string(shellSpellId));
        return payload;
    }

    void ApplyIntellectBlockRating(Player* player, int32 desiredRating)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        int32 currentRating = 0;
        if (auto it = gIntellectBlockRatingByPlayer.find(playerGuid); it != gIntellectBlockRatingByPlayer.end())
            currentRating = it->second;

        if (currentRating == desiredRating)
            return;

        if (currentRating > 0)
            player->ApplyRatingMod(CR_BLOCK, currentRating, false);

        if (desiredRating > 0)
        {
            player->ApplyRatingMod(CR_BLOCK, desiredRating, true);
            gIntellectBlockRatingByPlayer[playerGuid] = desiredRating;
        }
        else
        {
            gIntellectBlockRatingByPlayer.erase(playerGuid);
        }
    }

    std::optional<WmSpells::IntellectBlockPassiveConfig> LoadActiveIntellectBlockPassiveConfig(Player* player)
    {
        if (!player || !WmSpells::IsPlayerAllowed(player) || !gConfig.intellectBlockPassiveEnabled)
            return std::nullopt;

        QueryResult result = WorldDatabase.Query(
            "SELECT b.ShellSpellID, b.ConfigJSON, b.Status "
            "FROM wm_spell_grant g "
            "JOIN wm_spell_behavior b ON b.ShellSpellID = g.ShellSpellID "
            "WHERE g.PlayerGUID = {} "
            "  AND g.RevokedAt IS NULL "
            "  AND b.BehaviorKind = 'passive_intellect_block_v1' "
            "  AND b.Status = 'active' "
            "ORDER BY g.GrantID DESC LIMIT 1",
            static_cast<uint32>(player->GetGUID().GetCounter()));

        if (!result)
            return std::nullopt;

        Field* fields = result->Fetch();
        WmSpells::BehaviorRecord record;
        record.shellSpellId = fields[0].Get<uint32>();
        record.behaviorKind = "passive_intellect_block_v1";
        record.configJson = fields[1].Get<std::string>();
        record.status = fields[2].Get<std::string>();
        return BuildIntellectBlockPassiveConfig(record);
    }

    bool HasActiveCombatProficiencyGrant(Player* player)
    {
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return false;

        QueryResult result = WorldDatabase.Query(
            "SELECT 1 FROM wm_spell_grant "
            "WHERE PlayerGUID = {} "
            "  AND ShellSpellID = {} "
            "  AND GrantKind = 'combat_proficiency' "
            "  AND RevokedAt IS NULL "
            "LIMIT 1",
            static_cast<uint32>(player->GetGUID().GetCounter()),
            COMBAT_PROFICIENCY_SHELL_ID);

        return result != nullptr;
    }

    int32 ResolveIntellectBlockRating(Player* player, WmSpells::IntellectBlockPassiveConfig const& config)
    {
        if (!player)
            return 0;

        float intellect = std::max(0.0f, player->GetTotalStatValue(STAT_INTELLECT));
        int32 spellPower = std::max<int32>(0, player->SpellBaseDamageBonusDone(static_cast<SpellSchoolMask>(config.spellSchoolMask)));
        float rating = intellect * config.intellectToBlockRatingScale
            + static_cast<float>(spellPower) * config.spellPowerToBlockRatingScale;

        int32 resolved = std::max<int32>(0, static_cast<int32>(std::round(rating)));
        if (config.maxBlockRating > 0)
            resolved = std::min<int32>(resolved, static_cast<int32>(config.maxBlockRating));

        return resolved;
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
        gConfig.intellectBlockPassiveEnabled = sConfigMgr->GetOption<bool>("WmSpells.IntellectBlockPassive.Enable", true);
        gConfig.boneboundServantEnabled = sConfigMgr->GetOption<bool>("WmSpells.BoneboundServant.Enable", true);
        ParseUIntSet(sConfigMgr->GetOption<std::string>("WmSpells.BoneboundServant.ShellSpellIds", "940000,940001"), gConfig.boneboundShellSpellIds);
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

    bool IsSupportedBehaviorKind(std::string const& behaviorKind)
    {
        return IsBoneboundBehaviorKind(behaviorKind) || IsIntellectBlockBehaviorKind(behaviorKind);
    }

    std::optional<BehaviorRecord> LoadBehaviorRecord(uint32 shellSpellId)
    {
        if (shellSpellId == 0)
            return std::nullopt;

        QueryResult result = WorldDatabase.Query(
            "SELECT BehaviorKind, ConfigJSON, Status FROM wm_spell_behavior WHERE ShellSpellID = {} LIMIT 1",
            shellSpellId);

        if (!result)
            return std::nullopt;

        Field* fields = result->Fetch();
        BehaviorRecord record;
        record.shellSpellId = shellSpellId;
        record.behaviorKind = fields[0].Get<std::string>();
        record.configJson = fields[1].Get<std::string>();
        record.status = fields[2].Get<std::string>();
        return record;
    }

    SpellCastResult CheckBoneboundCorpseTarget(Player* player, uint32 shellSpellId)
    {
        if (!player)
            return SPELL_FAILED_CASTER_DEAD;

        if (!IsPlayerAllowed(player) || !gConfig.boneboundServantEnabled)
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;
        std::optional<BoneboundBehaviorConfig> runtimeConfig = BuildBoneboundBehaviorConfig(*behaviorRecord, true);
        if (!runtimeConfig.has_value())
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        if (!runtimeConfig->requireCorpse)
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

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(createdBySpellId);
        if (!behaviorRecord.has_value())
            return {false, "shell_behavior_missing"};
        std::optional<BoneboundBehaviorConfig> runtimeConfig = BuildBoneboundBehaviorConfig(*behaviorRecord, persistPet);
        if (!runtimeConfig.has_value())
            return {false, "shell_behavior_disabled"};

        BoneboundBehaviorConfig const& config = *runtimeConfig;

        if (config.requireCorpse && !GetCorpseTarget(player))
            return {false, "corpse_required"};

        RemoveBoneboundOmega(player);
        if (Pet* currentPet = player->GetPet())
            player->RemovePet(currentPet, PET_SAVE_AS_DELETED);
        else
            player->RemovePet(nullptr, PET_SAVE_AS_DELETED);

        Position pos;
        player->GetClosePoint(pos.m_positionX, pos.m_positionY, pos.m_positionZ, 1.0f, 2.0f);

        Pet* pet = player->SummonPet(
            config.creatureEntry,
            pos.m_positionX,
            pos.m_positionY,
            pos.m_positionZ,
            player->GetOrientation(),
            SUMMON_PET,
            0ms,
            config.shellSpellId
        );

        if (!pet)
        {
            pet = player->GetPet();
            if (!pet)
                return {false, "summon_failed"};
        }

        ApplyBoneboundOverlay(player, pet, config);
        if (config.spawnOmega)
            SyncBoneboundOmega(player, pet, config);
        return {true, "bonebound_servant_summoned"};
    }

    BehaviorExecutionResult ExecuteShellBehavior(Player* player, uint32 shellSpellId, bool persistPetFallback)
    {
        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return {false, "shell_behavior_missing"};

        if (IsIntellectBlockBehaviorKind(behaviorRecord->behaviorKind))
        {
            MaintainIntellectBlockPassive(player);
            return {true, "intellect_block_passive_maintained"};
        }

        std::optional<BoneboundBehaviorConfig> runtimeConfig = BuildBoneboundBehaviorConfig(*behaviorRecord, persistPetFallback);
        if (!runtimeConfig.has_value())
            return {false, "shell_behavior_disabled"};

        if (IsBoneboundBehaviorKind(behaviorRecord->behaviorKind))
            return ExecuteBoneboundServant(player, shellSpellId, runtimeConfig->persistPet);

        return {false, "unsupported_shell_spell"};
    }

    void UpdateTrackedCompanions(uint32 /*diff*/)
    {
        if (gBoneboundOmegaByPlayer.empty())
            return;

        std::vector<uint32> ownerGuids;
        ownerGuids.reserve(gBoneboundOmegaByPlayer.size());
        for (auto const& [ownerGuid, _] : gBoneboundOmegaByPlayer)
            ownerGuids.push_back(ownerGuid);

        std::vector<uint32> staleOwners;
        for (uint32 ownerGuid : ownerGuids)
        {
            Player* owner = ObjectAccessor::FindPlayerByLowGUID(ownerGuid);
            if (!owner || !IsPlayerAllowed(owner))
            {
                staleOwners.push_back(ownerGuid);
                continue;
            }

            MaintainBoneboundSummons(owner);
        }

        for (uint32 ownerGuid : staleOwners)
            gBoneboundOmegaByPlayer.erase(ownerGuid);
    }

    void MaintainBoneboundSummons(Player* owner)
    {
        if (!owner || !IsPlayerAllowed(owner) || !gConfig.boneboundServantEnabled)
            return;

        if (RestoreTemporarilyUnsummonedBoneboundPet(owner))
            return;

        Pet* alphaPet = owner->GetPet();
        if (!alphaPet || !IsBoneboundPet(alphaPet))
        {
            RemoveBoneboundOmega(owner);
            return;
        }

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL));
        if (!behaviorRecord.has_value())
        {
            RemoveBoneboundOmega(owner);
            return;
        }

        std::optional<BoneboundBehaviorConfig> runtimeConfig = BuildBoneboundBehaviorConfig(*behaviorRecord, false);
        if (!runtimeConfig.has_value())
        {
            RemoveBoneboundOmega(owner);
            return;
        }

        if (alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL) != runtimeConfig->shellSpellId)
            alphaPet->SetUInt32Value(UNIT_CREATED_BY_SPELL, runtimeConfig->shellSpellId);

        ApplyBoneboundCreatureAppearance(
            alphaPet,
            runtimeConfig->name,
            runtimeConfig->displayId,
            runtimeConfig->virtualItem1,
            runtimeConfig->virtualItem2,
            runtimeConfig->virtualItem3,
            ResolveAlphaVisualScale(owner, *runtimeConfig));
        ApplyOwnerTransferBonuses(alphaPet, owner, *runtimeConfig, false);

        if (runtimeConfig->spawnOmega)
            SyncBoneboundOmega(owner, alphaPet, *runtimeConfig);
        else
            RemoveBoneboundOmega(owner);
    }

    void ForgetBoneboundCompanions(Player* owner)
    {
        RemoveBoneboundOmega(owner);
    }

    void MaintainIntellectBlockPassive(Player* player)
    {
        if (!player)
            return;

        std::optional<IntellectBlockPassiveConfig> config = LoadActiveIntellectBlockPassiveConfig(player);
        if (!config.has_value())
        {
            ApplyIntellectBlockRating(player, 0);
            return;
        }

        ApplyIntellectBlockRating(player, ResolveIntellectBlockRating(player, *config));
    }

    void MaintainCombatProficiencies(Player* player)
    {
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return;

        if (!player->HasSpell(DUAL_WIELD_SPELL_ID) || player->CanDualWield())
            return;

        if (!HasActiveCombatProficiencyGrant(player))
            return;

        // character_spell is the persistent truth; AzerothCore keeps Dual Wield
        // as a volatile runtime flag, so materialize it only for explicit WM grants.
        player->CastSpell(player, DUAL_WIELD_SPELL_ID, true);
        if (!player->CanDualWield())
            player->SetCanDualWield(true);
    }

    void ForgetIntellectBlockPassive(Player* player)
    {
        if (!player)
            return;

        ApplyIntellectBlockRating(player, 0);
    }

    void ReapplyBoneboundOverlay(Pet* pet)
    {
        if (!pet || !pet->GetOwner() || !pet->GetOwner()->ToPlayer())
            return;

        Player* owner = pet->GetOwner()->ToPlayer();
        if (!IsPlayerAllowed(owner) || !IsBoneboundPet(pet))
            return;

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(pet->GetUInt32Value(UNIT_CREATED_BY_SPELL));
        if (!behaviorRecord.has_value())
            return;
        std::optional<BoneboundBehaviorConfig> runtimeConfig = BuildBoneboundBehaviorConfig(*behaviorRecord, false);
        if (!runtimeConfig.has_value())
            return;

        ApplyBoneboundOverlay(owner, pet, *runtimeConfig);
        if (runtimeConfig->spawnOmega)
            SyncBoneboundOmega(owner, pet, *runtimeConfig);
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
            "SELECT RequestID, PlayerGUID, BehaviorKind, PayloadJSON FROM wm_spell_debug_request "
            "WHERE Status = 'pending' ORDER BY RequestID ASC LIMIT 1");

        if (!result)
            return;

        Field* fields = result->Fetch();
        uint64 requestId = fields[0].Get<uint64>();
        uint32 playerGuid = fields[1].Get<uint32>();
        std::string behaviorKind = fields[2].Get<std::string>();
        std::string payloadJson = fields[3].Get<std::string>();
        uint32 shellSpellId = ExtractJsonUInt(payloadJson, "shell_spell_id").value_or(0u);

        WorldDatabase.Execute(
            "UPDATE wm_spell_debug_request SET Status = 'claimed', UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE RequestID = {} AND Status = 'pending'",
            requestId);

        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (IsSupportedBehaviorKind(behaviorKind))
        {
            BehaviorExecutionResult exec = ExecuteShellBehavior(player, shellSpellId, false);
            if (exec.ok)
            {
                CompleteDebugRequest(requestId, "done", JsonResult(true, behaviorKind, exec.message, shellSpellId));
            }
            else
            {
                CompleteDebugRequest(requestId, "failed", JsonResult(false, behaviorKind, exec.message, shellSpellId), exec.message);
            }
            return;
        }

        CompleteDebugRequest(requestId, "failed", JsonResult(false, behaviorKind, "unknown_behavior_kind", shellSpellId), "unknown_behavior_kind");
    }
}
