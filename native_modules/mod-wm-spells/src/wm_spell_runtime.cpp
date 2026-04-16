#include "wm_spell_runtime.h"

#include "Config.h"
#include "Creature.h"
#include "CreatureAI.h"
#include "DatabaseEnv.h"
#include "Item.h"
#include "MotionMaster.h"
#include "ObjectAccessor.h"
#include "PetDefines.h"
#include "Random.h"
#include "SpellAuras.h"
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
    constexpr uint32 NIGHT_WATCHERS_LENS_ITEM_ENTRY = 910006;
    // Detect Invisibility is a client-known, visible marker aura that fits the lens fantasy.
    // The WM-owned proc mechanic below is gated on this aura plus the equipped item.
    constexpr uint32 NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID = 132;
    // Faerie Fire is a visible target debuff with matching "exposed defenses" semantics.
    constexpr uint32 NIGHT_WATCHERS_LENS_MARK_DEBUFF_SPELL_ID = 770;
    constexpr uint32 NIGHT_WATCHERS_LENS_MARK_DURATION_MS = 10000;
    constexpr float NIGHT_WATCHERS_LENS_PROC_CHANCE_PCT = 10.0f;
    constexpr float NIGHT_WATCHERS_LENS_MARK_PROC_MULTIPLIER = 2.0f;
    constexpr float WM_PI = 3.14159265358979323846f;

    WmSpells::RuntimeConfig gConfig;
    uint32 gDebugPollTimer = 0;
    std::unordered_map<uint32, ObjectGuid> gBoneboundOmegaByPlayer;
    std::unordered_map<uint32, int32> gIntellectBlockRatingByPlayer;
    std::unordered_set<uint32> gNightWatchersLensAuraAppliedByPlayer;

    struct NightWatchersLensMarkState
    {
        ObjectGuid casterGuid;
        uint32 remainingMs = 0;
    };

    struct BoneboundShadowDotState
    {
        ObjectGuid casterGuid;
        ObjectGuid targetGuid;
        uint32 ownerGuid = 0;
        uint32 remainingMs = 0;
        uint32 tickMs = 1000;
        uint32 tickTimerMs = 1000;
        uint32 tickDamage = 1;
    };

    struct BoneboundAlphaEchoState
    {
        ObjectGuid echoGuid;
        uint32 ownerGuid = 0;
        uint32 creatureEntry = 0;
        uint32 remainingMs = 0;
        uint32 damagePct = 100;
        float followDistance = 2.2f;
        float followAngle = PET_FOLLOW_ANGLE;
    };

    std::vector<BoneboundShadowDotState> gBoneboundShadowDots;
    std::unordered_map<uint32, BoneboundAlphaEchoState> gBoneboundAlphaEchoes;
    std::unordered_map<uint32, uint32> gBoneboundShadowDotCooldownByPet;
    std::unordered_map<uint64, NightWatchersLensMarkState> gNightWatchersLensMarksByTarget;

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

    struct BoneboundDamageRange
    {
        float minDamage = BASE_MINDAMAGE;
        float maxDamage = BASE_MAXDAMAGE;
    };

    float ResolveOmegaDamageScale(WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (config.preserveBaseStats)
            return 1.0f;
        return static_cast<float>(std::max<uint32>(1u, config.omegaDamagePct)) / 100.0f;
    }

    BoneboundDamageRange ResolveOmegaWeaponDamage(Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!alphaPet)
            return {};

        float damageScale = ResolveOmegaDamageScale(config);
        BoneboundDamageRange damage{
            alphaPet->GetWeaponDamageRange(BASE_ATTACK, MINDAMAGE) * damageScale,
            alphaPet->GetWeaponDamageRange(BASE_ATTACK, MAXDAMAGE) * damageScale,
        };
        if (damage.minDamage <= 0.0f)
            damage.minDamage = BASE_MINDAMAGE;
        if (damage.maxDamage < damage.minDamage)
            damage.maxDamage = damage.minDamage;
        return damage;
    }

    BoneboundDamageRange ResolveOmegaFinalDamage(Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!alphaPet)
            return {};

        float damageScale = ResolveOmegaDamageScale(config);
        BoneboundDamageRange damage{
            alphaPet->GetFloatValue(UNIT_FIELD_MINDAMAGE) * damageScale,
            alphaPet->GetFloatValue(UNIT_FIELD_MAXDAMAGE) * damageScale,
        };
        if (damage.minDamage <= 0.0f || damage.maxDamage <= 0.0f)
            return ResolveOmegaWeaponDamage(alphaPet, config);
        if (damage.maxDamage < damage.minDamage)
            damage.maxDamage = damage.minDamage;
        return damage;
    }

    void ApplyOmegaFinalDamageFields(TempSummon* omega, BoneboundDamageRange const& finalDamage)
    {
        if (!omega)
            return;

        omega->SetStatFloatValue(UNIT_FIELD_MINDAMAGE, finalDamage.minDamage);
        omega->SetStatFloatValue(UNIT_FIELD_MAXDAMAGE, finalDamage.maxDamage);
    }

    uint32 ResolveOmegaMaxHealth(Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config);

    uint32 PreserveRuntimeValuePct(uint32 previousValue, uint32 previousMaxValue, uint32 desiredMaxValue, bool refill)
    {
        if (desiredMaxValue == 0)
            return 0;
        if (refill)
            return desiredMaxValue;
        if (previousMaxValue == 0)
            return std::min(previousValue, desiredMaxValue);

        uint64 scaledValue = (static_cast<uint64>(previousValue) * desiredMaxValue) / previousMaxValue;
        scaledValue = std::clamp<uint64>(scaledValue, 0ULL, static_cast<uint64>(desiredMaxValue));
        return static_cast<uint32>(scaledValue);
    }

    void CopyAlphaFinalStatsToOmega(Pet* alphaPet, TempSummon* omega, WmSpells::BoneboundBehaviorConfig const& config, bool refill)
    {
        if (!alphaPet || !omega)
            return;

        uint32 previousHealth = omega->GetHealth();
        uint32 previousMaxHealth = omega->GetMaxHealth();
        uint32 desiredMaxHealth = ResolveOmegaMaxHealth(alphaPet, config);

        omega->SetCreateHealth(alphaPet->GetCreateHealth());
        omega->SetMaxHealth(desiredMaxHealth);
        omega->SetHealth(PreserveRuntimeValuePct(previousHealth, previousMaxHealth, desiredMaxHealth, refill));

        omega->SetCreateMana(alphaPet->GetCreateMana());
        for (uint8 powerIndex = POWER_MANA; powerIndex < MAX_POWERS; ++powerIndex)
        {
            Powers power = Powers(powerIndex);
            uint32 previousPower = omega->GetPower(power);
            uint32 previousMaxPower = omega->GetMaxPower(power);
            uint32 desiredMaxPower = alphaPet->GetMaxPower(power);
            omega->SetMaxPower(power, desiredMaxPower);
            omega->SetPower(power, PreserveRuntimeValuePct(previousPower, previousMaxPower, desiredMaxPower, refill));
        }

        for (uint8 statIndex = STAT_STRENGTH; statIndex < MAX_STATS; ++statIndex)
        {
            Stats stat = Stats(statIndex);
            omega->SetCreateStat(stat, alphaPet->GetCreateStat(stat));
            omega->SetStat(stat, static_cast<int32>(alphaPet->GetStat(stat)));
            omega->SetFloatValue(static_cast<uint16>(UNIT_FIELD_POSSTAT0) + statIndex, alphaPet->GetPosStat(stat));
            omega->SetFloatValue(static_cast<uint16>(UNIT_FIELD_NEGSTAT0) + statIndex, alphaPet->GetNegStat(stat));
        }

        for (uint8 schoolIndex = SPELL_SCHOOL_NORMAL; schoolIndex < MAX_SPELL_SCHOOL; ++schoolIndex)
        {
            SpellSchools school = SpellSchools(schoolIndex);
            omega->SetResistance(school, static_cast<int32>(alphaPet->GetResistance(school)));
        }

        omega->SetInt32Value(UNIT_FIELD_ATTACK_POWER, alphaPet->GetInt32Value(UNIT_FIELD_ATTACK_POWER));
        omega->SetInt32Value(UNIT_FIELD_ATTACK_POWER_MODS, alphaPet->GetInt32Value(UNIT_FIELD_ATTACK_POWER_MODS));
        omega->SetFloatValue(UNIT_FIELD_ATTACK_POWER_MULTIPLIER, alphaPet->GetFloatValue(UNIT_FIELD_ATTACK_POWER_MULTIPLIER));
        omega->SetInt32Value(UNIT_FIELD_RANGED_ATTACK_POWER, alphaPet->GetInt32Value(UNIT_FIELD_RANGED_ATTACK_POWER));
        omega->SetInt32Value(UNIT_FIELD_RANGED_ATTACK_POWER_MODS, alphaPet->GetInt32Value(UNIT_FIELD_RANGED_ATTACK_POWER_MODS));
        omega->SetFloatValue(UNIT_FIELD_RANGED_ATTACK_POWER_MULTIPLIER, alphaPet->GetFloatValue(UNIT_FIELD_RANGED_ATTACK_POWER_MULTIPLIER));
        ApplyOmegaFinalDamageFields(omega, ResolveOmegaFinalDamage(alphaPet, config));
    }

    uint32 ResolveOmegaMaxHealth(Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!alphaPet)
            return 1u;

        uint32 healthPct = std::max<uint32>(1u, config.omegaHealthPct);
        return std::max<uint32>(1u, (alphaPet->GetMaxHealth() * healthPct) / 100u);
    }

    void ApplyBoneboundOmegaRuntime(Player* owner, Pet* alphaPet, TempSummon* omega, WmSpells::BoneboundBehaviorConfig const& config, bool refillHealth)
    {
        if (!owner || !alphaPet || !omega)
            return;

        BoneboundDamageRange weaponDamage = ResolveOmegaWeaponDamage(alphaPet, config);

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
        omega->SetBaseWeaponDamage(BASE_ATTACK, MINDAMAGE, weaponDamage.minDamage);
        omega->SetBaseWeaponDamage(BASE_ATTACK, MAXDAMAGE, weaponDamage.maxDamage);
        omega->SetAttackTime(BASE_ATTACK, alphaPet->GetAttackTime(BASE_ATTACK));
        MirrorMeleeAttackPower(alphaPet, omega);
        omega->UpdateAttackPowerAndDamage(false);
        omega->UpdateDamagePhysical(BASE_ATTACK);
        CopyAlphaFinalStatsToOmega(alphaPet, omega, config, refillHealth);
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
        return behaviorKind == "summon_bonebound_servant_v1"
            || behaviorKind == "summon_bonebound_twin_v2"
            || behaviorKind == "summon_bonebound_alpha_v3";
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
        if (record.behaviorKind == "summon_bonebound_alpha_v3")
        {
            config.spawnOmega = false;
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
        if (std::optional<bool> value = ExtractJsonBool(configJson, "shadow_dot_enabled"))
            config.shadowDotEnabled = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_cooldown_ms"))
            config.shadowDotCooldownMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_duration_ms"))
            config.shadowDotDurationMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_tick_ms"))
            config.shadowDotTickMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_base_damage"))
            config.shadowDotBaseDamage = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_damage_per_level_pct"))
            config.shadowDotDamagePerLevelPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_damage_per_intellect_pct"))
            config.shadowDotDamagePerIntellectPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_damage_per_shadow_power_pct"))
            config.shadowDotDamagePerShadowPowerPct = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "alpha_echo_enabled"))
            config.alphaEchoEnabled = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "alpha_echo_proc_chance_pct"))
            config.alphaEchoProcChancePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_echo_max_active"))
            config.alphaEchoMaxActive = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_echo_creature_entry"))
            config.alphaEchoCreatureEntry = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_echo_damage_pct"))
            config.alphaEchoDamagePct = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "alpha_echo_follow_distance"))
            config.alphaEchoFollowDistance = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "alpha_echo_follow_angle"))
            config.alphaEchoFollowAngle = *value;

        if (record.behaviorKind == "summon_bonebound_alpha_v3")
            config.spawnOmega = false;

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

    std::optional<WmSpells::BoneboundBehaviorConfig> LoadActiveBoneboundConfig(uint32 shellSpellId, bool persistPetFallback)
    {
        std::optional<WmSpells::BehaviorRecord> behaviorRecord = WmSpells::LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return std::nullopt;
        return BuildBoneboundBehaviorConfig(*behaviorRecord, persistPetFallback);
    }

    uint32 ResolveShadowDotTickDamage(Player* owner, Unit* caster, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner)
            return 1u;

        float intellect = std::max(0.0f, owner->GetTotalStatValue(STAT_INTELLECT));
        int32 shadowPower = std::max<int32>(0, owner->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW));
        uint32 level = caster ? caster->GetLevel() : owner->GetLevel();
        float damage = static_cast<float>(config.shadowDotBaseDamage)
            + static_cast<float>(level) * (static_cast<float>(config.shadowDotDamagePerLevelPct) / 100.0f)
            + intellect * (static_cast<float>(config.shadowDotDamagePerIntellectPct) / 100.0f)
            + static_cast<float>(shadowPower) * (static_cast<float>(config.shadowDotDamagePerShadowPowerPct) / 100.0f);
        return std::max<uint32>(1u, static_cast<uint32>(std::round(damage)));
    }

    void StartBoneboundShadowDot(Player* owner, Unit* caster, Unit* target, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner || !caster || !target || !target->IsAlive() || !config.shadowDotEnabled)
            return;

        uint32 durationMs = std::max<uint32>(1000u, config.shadowDotDurationMs);
        uint32 tickMs = std::max<uint32>(500u, config.shadowDotTickMs);
        uint32 tickDamage = ResolveShadowDotTickDamage(owner, caster, config);

        for (BoneboundShadowDotState& dot : gBoneboundShadowDots)
        {
            if (dot.casterGuid == caster->GetGUID() && dot.targetGuid == target->GetGUID())
            {
                dot.ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
                dot.remainingMs = durationMs;
                dot.tickMs = tickMs;
                dot.tickTimerMs = tickMs;
                dot.tickDamage = tickDamage;
                return;
            }
        }

        BoneboundShadowDotState dot;
        dot.casterGuid = caster->GetGUID();
        dot.targetGuid = target->GetGUID();
        dot.ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        dot.remainingMs = durationMs;
        dot.tickMs = tickMs;
        dot.tickTimerMs = tickMs;
        dot.tickDamage = tickDamage;
        gBoneboundShadowDots.push_back(dot);
    }

    uint32 CountActiveBoneboundAlphaEchoes(uint32 ownerGuid)
    {
        uint32 count = 0;
        for (auto const& [_, echo] : gBoneboundAlphaEchoes)
        {
            if (echo.ownerGuid == ownerGuid)
                ++count;
        }
        return count;
    }

    uint32 ResolveAlphaEchoDurationMs(Player* owner)
    {
        if (!owner)
            return 1000u;

        uint32 seconds = std::max<uint32>(1u, static_cast<uint32>(std::round(std::max(0.0f, owner->GetTotalStatValue(STAT_INTELLECT)))));
        return seconds * 1000u;
    }

    float RandomAlphaEchoFollowAngle()
    {
        return -WM_PI + (static_cast<float>(urand(0, 10000)) / 10000.0f) * (WM_PI * 2.0f);
    }

    float RandomAlphaEchoFollowDistance(WmSpells::BoneboundBehaviorConfig const& config)
    {
        float baseDistance = std::max(1.5f, config.alphaEchoFollowDistance);
        float minDistance = std::max(1.0f, baseDistance - 0.8f);
        float maxDistance = baseDistance + 1.2f;
        return minDistance + (static_cast<float>(urand(0, 10000)) / 10000.0f) * (maxDistance - minDistance);
    }

    uint32 ResolveAlphaMeleeDamageRoll(Pet* alphaPet, Player* owner, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!alphaPet)
            return owner ? std::max<uint32>(1u, static_cast<uint32>(std::round(BuildDamage(owner, config.baseMinDamage, config)))) : 1u;

        float minDamage = alphaPet->GetFloatValue(UNIT_FIELD_MINDAMAGE);
        float maxDamage = alphaPet->GetFloatValue(UNIT_FIELD_MAXDAMAGE);
        if (minDamage <= 0.0f || maxDamage <= 0.0f)
        {
            minDamage = alphaPet->GetWeaponDamageRange(BASE_ATTACK, MINDAMAGE);
            maxDamage = alphaPet->GetWeaponDamageRange(BASE_ATTACK, MAXDAMAGE);
        }
        if (minDamage <= 0.0f || maxDamage <= 0.0f)
        {
            minDamage = BuildDamage(owner, config.baseMinDamage, config);
            maxDamage = BuildDamage(owner, config.baseMaxDamage, config);
        }

        uint32 low = std::max<uint32>(1u, static_cast<uint32>(std::floor(minDamage)));
        uint32 high = std::max<uint32>(low, static_cast<uint32>(std::ceil(maxDamage)));
        return urand(low, high);
    }

    void CopyAlphaFinalStatsToEcho(Pet* alphaPet, TempSummon* echo, bool refill)
    {
        if (!alphaPet || !echo)
            return;

        uint32 previousHealth = echo->GetHealth();
        uint32 previousMaxHealth = echo->GetMaxHealth();
        uint32 desiredMaxHealth = std::max<uint32>(1u, alphaPet->GetMaxHealth());

        echo->SetCreateHealth(alphaPet->GetCreateHealth());
        echo->SetMaxHealth(desiredMaxHealth);
        echo->SetHealth(PreserveRuntimeValuePct(previousHealth, previousMaxHealth, desiredMaxHealth, refill));

        echo->SetCreateMana(alphaPet->GetCreateMana());
        for (uint8 powerIndex = POWER_MANA; powerIndex < MAX_POWERS; ++powerIndex)
        {
            Powers power = Powers(powerIndex);
            uint32 previousPower = echo->GetPower(power);
            uint32 previousMaxPower = echo->GetMaxPower(power);
            uint32 desiredMaxPower = alphaPet->GetMaxPower(power);
            echo->SetMaxPower(power, desiredMaxPower);
            echo->SetPower(power, PreserveRuntimeValuePct(previousPower, previousMaxPower, desiredMaxPower, refill));
        }

        for (uint8 statIndex = STAT_STRENGTH; statIndex < MAX_STATS; ++statIndex)
        {
            Stats stat = Stats(statIndex);
            echo->SetCreateStat(stat, alphaPet->GetCreateStat(stat));
            echo->SetStat(stat, static_cast<int32>(alphaPet->GetStat(stat)));
            echo->SetFloatValue(static_cast<uint16>(UNIT_FIELD_POSSTAT0) + statIndex, alphaPet->GetPosStat(stat));
            echo->SetFloatValue(static_cast<uint16>(UNIT_FIELD_NEGSTAT0) + statIndex, alphaPet->GetNegStat(stat));
        }

        for (uint8 schoolIndex = SPELL_SCHOOL_NORMAL; schoolIndex < MAX_SPELL_SCHOOL; ++schoolIndex)
        {
            SpellSchools school = SpellSchools(schoolIndex);
            echo->SetResistance(school, static_cast<int32>(alphaPet->GetResistance(school)));
        }

        echo->SetBaseWeaponDamage(BASE_ATTACK, MINDAMAGE, alphaPet->GetWeaponDamageRange(BASE_ATTACK, MINDAMAGE));
        echo->SetBaseWeaponDamage(BASE_ATTACK, MAXDAMAGE, alphaPet->GetWeaponDamageRange(BASE_ATTACK, MAXDAMAGE));
        echo->SetAttackTime(BASE_ATTACK, alphaPet->GetAttackTime(BASE_ATTACK));
        MirrorMeleeAttackPower(alphaPet, echo);
        echo->UpdateAttackPowerAndDamage(false);
        echo->UpdateDamagePhysical(BASE_ATTACK);
        echo->SetStatFloatValue(UNIT_FIELD_MINDAMAGE, alphaPet->GetFloatValue(UNIT_FIELD_MINDAMAGE));
        echo->SetStatFloatValue(UNIT_FIELD_MAXDAMAGE, alphaPet->GetFloatValue(UNIT_FIELD_MAXDAMAGE));
    }

    void ApplyBoneboundAlphaEchoRuntime(Player* owner, Pet* alphaPet, TempSummon* echo, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner || !alphaPet || !echo)
            return;

        echo->SetCreatorGUID(owner->GetGUID());
        echo->SetOwnerGUID(owner->GetGUID());
        echo->SetFaction(owner->GetFaction());
        echo->SetLevel(alphaPet->GetLevel());
        echo->SetUInt32Value(UNIT_CREATED_BY_SPELL, config.shellSpellId);
        ApplyBoneboundCreatureAppearance(
            echo,
            config.name,
            config.displayId,
            config.virtualItem1,
            config.virtualItem2,
            config.virtualItem3,
            alphaPet->GetObjectScale());
        // Creature stat recalculation restores template fields; copy Alpha values after it.
        ApplyOwnerTransferBonuses(echo, owner, config, false);
        CopyAlphaFinalStatsToEcho(alphaPet, echo, true);
        echo->SetReactState(REACT_DEFENSIVE);
    }

    TempSummon* SpawnBoneboundAlphaEchoFromState(
        Player* owner,
        Pet* alphaPet,
        Unit* victim,
        BoneboundAlphaEchoState& state,
        WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner || !alphaPet || state.remainingMs == 0)
            return nullptr;

        uint32 echoEntry = state.creatureEntry != 0
            ? state.creatureEntry
            : (config.alphaEchoCreatureEntry != 0 ? config.alphaEchoCreatureEntry : config.creatureEntry);

        Position pos;
        owner->GetClosePoint(pos.m_positionX, pos.m_positionY, pos.m_positionZ, 1.0f, state.followDistance, state.followAngle);
        TempSummon* echo = owner->SummonCreature(
            echoEntry,
            pos.m_positionX,
            pos.m_positionY,
            pos.m_positionZ,
            owner->GetOrientation(),
            TEMPSUMMON_TIMED_DESPAWN,
            state.remainingMs);
        if (!echo)
            return nullptr;

        ApplyBoneboundAlphaEchoRuntime(owner, alphaPet, echo, config);
        if (victim && victim->IsAlive() && echo->AI())
            echo->AI()->AttackStart(victim);
        else
            echo->GetMotionMaster()->MoveFollow(owner, state.followDistance, state.followAngle);

        state.echoGuid = echo->GetGUID();
        state.creatureEntry = echoEntry;
        return echo;
    }

    void TrySpawnBoneboundAlphaEcho(Player* owner, Pet* alphaPet, Unit* victim, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner || !alphaPet || !victim || !victim->IsAlive() || !config.alphaEchoEnabled)
            return;

        uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        if (CountActiveBoneboundAlphaEchoes(ownerGuid) >= std::max<uint32>(1u, config.alphaEchoMaxActive))
            return;

        uint32 durationMs = ResolveAlphaEchoDurationMs(owner);
        float followDistance = RandomAlphaEchoFollowDistance(config);
        float followAngle = RandomAlphaEchoFollowAngle();
        uint32 echoEntry = config.alphaEchoCreatureEntry != 0 ? config.alphaEchoCreatureEntry : config.creatureEntry;

        BoneboundAlphaEchoState state;
        state.ownerGuid = ownerGuid;
        state.creatureEntry = echoEntry;
        state.remainingMs = durationMs;
        state.damagePct = std::max<uint32>(1u, config.alphaEchoDamagePct);
        state.followDistance = followDistance;
        state.followAngle = followAngle;

        TempSummon* echo = SpawnBoneboundAlphaEchoFromState(owner, alphaPet, victim, state, config);
        if (!echo)
            return;

        gBoneboundAlphaEchoes[static_cast<uint32>(echo->GetGUID().GetCounter())] = state;
    }

    void MaintainBoneboundAlphaAbilities(Player* owner, Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config, uint32 diff)
    {
        if (!owner || !alphaPet)
            return;

        uint32 petGuid = static_cast<uint32>(alphaPet->GetGUID().GetCounter());
        uint32& cooldown = gBoneboundShadowDotCooldownByPet[petGuid];
        cooldown = cooldown > diff ? cooldown - diff : 0u;

        Unit* victim = alphaPet->GetVictim();
        if (!victim || !victim->IsAlive())
            return;

        if (config.shadowDotEnabled && cooldown == 0)
        {
            StartBoneboundShadowDot(owner, alphaPet, victim, config);
            cooldown = std::max<uint32>(1000u, config.shadowDotCooldownMs);
        }
    }

    void RemoveBoneboundAlphaEchoes(Player* owner)
    {
        if (!owner)
            return;

        uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        for (auto it = gBoneboundAlphaEchoes.begin(); it != gBoneboundAlphaEchoes.end();)
        {
            if (it->second.ownerGuid != ownerGuid)
            {
                ++it;
                continue;
            }

            if (Creature* echo = ObjectAccessor::GetCreature(*owner, it->second.echoGuid))
                echo->DespawnOrUnsummon();
            it = gBoneboundAlphaEchoes.erase(it);
        }

        gBoneboundShadowDots.erase(
            std::remove_if(
                gBoneboundShadowDots.begin(),
                gBoneboundShadowDots.end(),
                [ownerGuid](BoneboundShadowDotState const& dot) { return dot.ownerGuid == ownerGuid; }),
            gBoneboundShadowDots.end());
    }

    void UpdateBoneboundShadowDots(uint32 diff)
    {
        for (auto it = gBoneboundShadowDots.begin(); it != gBoneboundShadowDots.end();)
        {
            Player* owner = ObjectAccessor::FindPlayerByLowGUID(it->ownerGuid);
            if (!owner)
            {
                it = gBoneboundShadowDots.erase(it);
                continue;
            }

            Unit* caster = ObjectAccessor::GetUnit(*owner, it->casterGuid);
            Unit* target = ObjectAccessor::GetUnit(*owner, it->targetGuid);
            if (!caster || !target || !target->IsAlive())
            {
                it = gBoneboundShadowDots.erase(it);
                continue;
            }

            if (it->tickTimerMs > diff)
            {
                it->tickTimerMs -= diff;
            }
            else
            {
                Unit::DealDamage(caster, target, it->tickDamage, nullptr, DOT, SPELL_SCHOOL_MASK_NORMAL, nullptr, true);
                it->tickTimerMs = it->tickMs;
            }

            if (it->remainingMs > diff)
            {
                it->remainingMs -= diff;
                ++it;
            }
            else
            {
                it = gBoneboundShadowDots.erase(it);
            }
        }
    }

    void UpdateBoneboundAlphaEchoes(uint32 diff)
    {
        for (auto it = gBoneboundAlphaEchoes.begin(); it != gBoneboundAlphaEchoes.end();)
        {
            Player* owner = ObjectAccessor::FindPlayerByLowGUID(it->second.ownerGuid);
            if (!owner)
            {
                it = gBoneboundAlphaEchoes.erase(it);
                continue;
            }

            if (it->second.remainingMs <= diff)
            {
                if (Creature* echo = ObjectAccessor::GetCreature(*owner, it->second.echoGuid))
                    echo->DespawnOrUnsummon();
                it = gBoneboundAlphaEchoes.erase(it);
                continue;
            }
            it->second.remainingMs -= diff;

            Creature* echo = ObjectAccessor::GetCreature(*owner, it->second.echoGuid);
            if (!echo || !echo->IsAlive())
            {
                // Mounting temporarily unsummons pets and can despawn related TempSummons.
                // Keep the Echo state alive until the main Bonebound pet can return.
                if (owner->IsPetNeedBeTemporaryUnsummoned())
                {
                    ++it;
                    continue;
                }

                Pet* alphaPet = owner->GetPet();
                if (!alphaPet && RestoreTemporarilyUnsummonedBoneboundPet(owner))
                    alphaPet = owner->GetPet();

                if (!alphaPet || !IsBoneboundPet(alphaPet))
                {
                    it = gBoneboundAlphaEchoes.erase(it);
                    continue;
                }

                std::optional<WmSpells::BoneboundBehaviorConfig> runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
                if (!runtimeConfig.has_value() || !runtimeConfig->alphaEchoEnabled)
                {
                    it = gBoneboundAlphaEchoes.erase(it);
                    continue;
                }

                Unit* victim = alphaPet->GetVictim();
                BoneboundAlphaEchoState state = it->second;
                TempSummon* restored = SpawnBoneboundAlphaEchoFromState(owner, alphaPet, victim, state, *runtimeConfig);
                if (!restored)
                {
                    it = gBoneboundAlphaEchoes.erase(it);
                    continue;
                }

                it = gBoneboundAlphaEchoes.erase(it);
                gBoneboundAlphaEchoes[static_cast<uint32>(restored->GetGUID().GetCounter())] = state;
                continue;
            }

            Pet* alphaPet = owner->GetPet();
            if (alphaPet && IsBoneboundPet(alphaPet))
            {
                if (Unit* victim = alphaPet->GetVictim())
                {
                    if (echo->AI())
                        echo->AI()->AttackStart(victim);
                }
                else if (!echo->IsInCombat())
                {
                    echo->GetMotionMaster()->MoveFollow(owner, it->second.followDistance, it->second.followAngle);
                }
            }

            ++it;
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

    bool IsNightWatchersLensEquipped(Player* player)
    {
        if (!player)
            return false;

        Item* headItem = player->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_HEAD);
        return headItem && headItem->GetTemplate() && headItem->GetTemplate()->ItemId == NIGHT_WATCHERS_LENS_ITEM_ENTRY;
    }

    void EnsureNightWatchersLensAura(Player* player)
    {
        if (!player || player->HasAura(NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID))
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        player->AddAura(NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID, player);
        if (player->HasAura(NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID))
            gNightWatchersLensAuraAppliedByPlayer.insert(playerGuid);
    }

    bool HasNightWatchersLensReady(Player* player)
    {
        return player
            && WmSpells::IsPlayerAllowed(player)
            && IsNightWatchersLensEquipped(player)
            && player->HasAura(NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID);
    }

    bool RefreshNightWatchersLensMark(Player* caster, Unit* target)
    {
        if (!caster || !target || !target->IsAlive())
            return false;

        Aura* aura = caster->AddAura(NIGHT_WATCHERS_LENS_MARK_DEBUFF_SPELL_ID, target);
        if (!aura)
            aura = target->GetAura(NIGHT_WATCHERS_LENS_MARK_DEBUFF_SPELL_ID, caster->GetGUID());
        if (!aura)
            return false;

        aura->SetMaxDuration(static_cast<int32>(NIGHT_WATCHERS_LENS_MARK_DURATION_MS));
        aura->SetDuration(static_cast<int32>(NIGHT_WATCHERS_LENS_MARK_DURATION_MS));

        gNightWatchersLensMarksByTarget[target->GetGUID().GetRawValue()] = {
            aura->GetCasterGUID(),
            NIGHT_WATCHERS_LENS_MARK_DURATION_MS,
        };
        return true;
    }

    void UpdateNightWatchersLensMarks(uint32 diff)
    {
        if (diff == 0 || gNightWatchersLensMarksByTarget.empty())
            return;

        for (auto it = gNightWatchersLensMarksByTarget.begin(); it != gNightWatchersLensMarksByTarget.end();)
        {
            if (it->second.remainingMs <= diff)
            {
                it = gNightWatchersLensMarksByTarget.erase(it);
                continue;
            }

            it->second.remainingMs -= diff;
            ++it;
        }
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

        RemoveBoneboundAlphaEchoes(player);
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

    void UpdateTrackedCompanions(uint32 diff)
    {
        UpdateBoneboundShadowDots(diff);
        UpdateBoneboundAlphaEchoes(diff);
        UpdateNightWatchersLensMarks(diff);

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
            if (owner->IsPetNeedBeTemporaryUnsummoned())
            {
                RemoveBoneboundOmega(owner);
                return;
            }

            RemoveBoneboundAlphaEchoes(owner);
            RemoveBoneboundOmega(owner);
            return;
        }

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL));
        if (!behaviorRecord.has_value())
        {
            RemoveBoneboundAlphaEchoes(owner);
            RemoveBoneboundOmega(owner);
            return;
        }

        std::optional<BoneboundBehaviorConfig> runtimeConfig = BuildBoneboundBehaviorConfig(*behaviorRecord, false);
        if (!runtimeConfig.has_value())
        {
            RemoveBoneboundAlphaEchoes(owner);
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
        MaintainBoneboundAlphaAbilities(owner, alphaPet, *runtimeConfig, 1000u);

        if (runtimeConfig->spawnOmega)
            SyncBoneboundOmega(owner, alphaPet, *runtimeConfig);
        else
            RemoveBoneboundOmega(owner);
    }

    void HandleBoneboundMeleeDamage(Unit* attacker, Unit* victim, uint32& damage)
    {
        if (!attacker || !victim || damage == 0)
            return;

        if (Pet* alphaPet = attacker->ToPet())
        {
            if (!IsBoneboundPet(alphaPet))
                return;

            Unit* ownerUnit = alphaPet->GetOwner();
            Player* owner = ownerUnit ? ownerUnit->ToPlayer() : nullptr;
            if (!owner || !IsPlayerAllowed(owner))
                return;

            std::optional<BoneboundBehaviorConfig> runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
            if (!runtimeConfig.has_value() || !runtimeConfig->alphaEchoEnabled)
                return;

            float procChance = std::clamp(runtimeConfig->alphaEchoProcChancePct, 0.0f, 100.0f);
            if (IsNightWatchersLensMarked(victim))
                procChance = std::clamp(procChance * NIGHT_WATCHERS_LENS_MARK_PROC_MULTIPLIER, 0.0f, 100.0f);
            if (procChance > 0.0f && roll_chance_f(procChance))
                TrySpawnBoneboundAlphaEcho(owner, alphaPet, victim, *runtimeConfig);
            return;
        }

        auto echoIt = gBoneboundAlphaEchoes.find(static_cast<uint32>(attacker->GetGUID().GetCounter()));
        if (echoIt == gBoneboundAlphaEchoes.end())
            return;

        Player* owner = ObjectAccessor::FindPlayerByLowGUID(echoIt->second.ownerGuid);
        if (!owner || !IsPlayerAllowed(owner))
            return;

        Pet* alphaPet = owner->GetPet();
        if (!alphaPet || !IsBoneboundPet(alphaPet))
            return;

        std::optional<BoneboundBehaviorConfig> runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
        if (!runtimeConfig.has_value())
            return;

        uint32 alphaRoll = ResolveAlphaMeleeDamageRoll(alphaPet, owner, *runtimeConfig);
        uint32 scaledRoll = std::max<uint32>(1u, (alphaRoll * std::max<uint32>(1u, echoIt->second.damagePct)) / 100u);
        damage = std::max<uint32>(damage, scaledRoll);
    }

    void ForgetBoneboundCompanions(Player* owner)
    {
        RemoveBoneboundAlphaEchoes(owner);
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

    void MaintainNightWatchersLens(Player* player, uint32 /*diff*/)
    {
        if (!player)
            return;

        if (!IsPlayerAllowed(player) || !IsNightWatchersLensEquipped(player))
        {
            ForgetNightWatchersLens(player);
            return;
        }

        EnsureNightWatchersLensAura(player);
    }

    void ForgetNightWatchersLens(Player* player)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        if (gNightWatchersLensAuraAppliedByPlayer.erase(playerGuid) > 0)
            player->RemoveAurasDueToSpell(NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID);
    }

    bool IsNightWatchersLensMarked(Unit const* unit)
    {
        if (!unit)
            return false;

        auto markIt = gNightWatchersLensMarksByTarget.find(unit->GetGUID().GetRawValue());
        if (markIt == gNightWatchersLensMarksByTarget.end())
            return false;

        Aura* aura = unit->GetAura(NIGHT_WATCHERS_LENS_MARK_DEBUFF_SPELL_ID, markIt->second.casterGuid);
        return aura && aura->GetDuration() > 0;
    }

    void HandleNightWatchersLensDamage(Unit* attacker, Unit* victim, uint32& damage)
    {
        if (!attacker || !victim || damage == 0 || attacker == victim)
            return;

        Player* player = attacker->ToPlayer();
        if (!HasNightWatchersLensReady(player))
            return;

        float procChance = NIGHT_WATCHERS_LENS_PROC_CHANCE_PCT;
        if (IsNightWatchersLensMarked(victim))
            procChance *= NIGHT_WATCHERS_LENS_MARK_PROC_MULTIPLIER;

        if (!roll_chance_f(std::clamp(procChance, 0.0f, 100.0f)))
            return;

        RefreshNightWatchersLensMark(player, victim);
    }

    void HandleNightWatchersLensDefenseBypass(
        Unit const* /*attacker*/,
        Unit const* victim,
        WeaponAttackType /*attType*/,
        int32& /*attackerMaxSkillValueForLevel*/,
        int32& victimMaxSkillValueForLevel,
        int32& attackerWeaponSkill,
        int32& victimDefenseSkill,
        int32& /*crit_chance*/,
        int32& miss_chance,
        int32& dodge_chance,
        int32& parry_chance,
        int32& block_chance)
    {
        if (!IsNightWatchersLensMarked(victim))
            return;

        victimMaxSkillValueForLevel = attackerWeaponSkill;
        victimDefenseSkill = 0;
        miss_chance = 0;
        dodge_chance = 0;
        parry_chance = 0;
        block_chance = 0;
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
