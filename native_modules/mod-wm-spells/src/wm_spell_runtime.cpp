#include "wm_spell_runtime.h"

#include "CellImpl.h"
#include "Config.h"
#include "Creature.h"
#include "CreatureAI.h"
#include "DatabaseEnv.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Group.h"
#include "GroupReference.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "MotionMaster.h"
#include "ObjectAccessor.h"
#include "PetDefines.h"
#include "Random.h"
#include "SpellAuraEffects.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "TemporarySummon.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <list>
#include <limits>
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
    // Rend is a client-known bleed debuff. WM owns the damage; this aura is the visible status/timer.
    constexpr uint32 BONEBOUND_BLEED_VISIBLE_AURA_SPELL_ID = 772;
    // Thorns is a client-known positive buff marker; WM strips its effects and only uses the stack count.
    constexpr uint32 BONEBOUND_ECHO_COUNT_DEFAULT_AURA_SPELL_ID = 467;
    constexpr uint32 BONEBOUND_SLASH_SPELL_ID = 945000;
    constexpr float BONEBOUND_ECHO_MIN_FOLLOW_SEPARATION_YARDS = 1.6f;
    constexpr float WM_PI = 3.14159265358979323846f;

    WmSpells::RuntimeConfig gConfig;
    uint32 gDebugPollTimer = 0;
    std::unordered_map<uint32, ObjectGuid> gBoneboundOmegaByPlayer;
    std::unordered_map<uint32, int32> gIntellectBlockRatingByPlayer;
    std::unordered_set<uint32> gNightWatchersLensAuraAppliedByPlayer;
    std::unordered_map<uint32, bool> gBoneboundEchoHuntModeByPlayer;
    std::unordered_map<uint32, float> gBoneboundEchoHuntRadiusByPlayer;
    std::unordered_map<uint32, uint32> gBoneboundEchoCountAuraByPlayer;

    struct NightWatchersLensMarkState
    {
        ObjectGuid casterGuid;
        uint32 remainingMs = 0;
    };

    struct BoneboundBleedState
    {
        ObjectGuid casterGuid;
        ObjectGuid targetGuid;
        uint32 ownerGuid = 0;
        uint32 remainingMs = 0;
        uint32 tickMs = 1000;
        uint32 tickTimerMs = 1000;
        uint32 tickDamage = 1;
    };

    enum class BoneboundEchoRole
    {
        Warrior,
        Priest
    };

    struct BoneboundAlphaEchoState
    {
        ObjectGuid echoGuid;
        uint32 ownerGuid = 0;
        uint32 creatureEntry = 0;
        uint32 remainingMs = 0;
        uint32 damagePct = 100;
        BoneboundEchoRole role = BoneboundEchoRole::Warrior;
        uint32 virtualItem1 = 0;
        uint32 virtualItem2 = 0;
        uint32 virtualItem3 = 0;
        float followDistance = 2.2f;
        float followAngle = PET_FOLLOW_ANGLE;
    };

    struct BoneboundEchoStasisCounts
    {
        uint32 destroyers = 0;
        uint32 restorers = 0;

        uint32 Total() const
        {
            return destroyers + restorers;
        }
    };

    struct BoneboundEchoFormationSlot
    {
        float followDistance = 2.2f;
        float followAngle = PET_FOLLOW_ANGLE;
    };

    struct BoneboundPriestDispelCandidate
    {
        Unit* target = nullptr;
        uint32 spellId = 0;
        ObjectGuid casterGuid;
        uint32 dispelType = DISPEL_NONE;
        uint32 severity = 0;
    };

    struct BoneboundPriestDpsCastState
    {
        ObjectGuid targetGuid;
        uint32 ownerGuid = 0;
        uint32 visualSpellId = 0;
        uint32 damageSpellId = 0;
        uint32 damage = 1;
        uint32 remainingMs = 0;
        float maxRange = 100.0f;
    };

    std::vector<BoneboundBleedState> gBoneboundBleeds;
    std::unordered_map<uint32, BoneboundAlphaEchoState> gBoneboundAlphaEchoes;
    std::unordered_map<uint32, uint32> gBoneboundBleedCooldownByCaster;
    std::unordered_map<uint32, uint32> gBoneboundCleaveCooldownByCaster;
    std::unordered_map<uint32, uint32> gBoneboundPriestHealCooldownByCaster;
    std::unordered_map<uint32, uint32> gBoneboundPriestRenewCooldownByCaster;
    std::unordered_map<uint32, uint32> gBoneboundPriestShieldCooldownByCaster;
    std::unordered_map<uint32, uint32> gBoneboundPriestDpsCooldownByCaster;
    std::unordered_map<uint32, uint32> gBoneboundPriestDispelCooldownByCaster;
    std::unordered_map<uint32, uint32> gBoneboundPriestMassDispelCooldownByCaster;
    std::unordered_map<uint32, BoneboundPriestDpsCastState> gBoneboundPriestDpsCastByCaster;
    std::unordered_map<uint32, uint32> gBoneboundWarriorEchoesSincePriestByPlayer;
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

        bool nameChanged = creature->GetName() != name;
        creature->SetName(name);
        if (nameChanged)
            creature->UpdateObjectVisibility();
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
        config.alphaEchoCountAuraSpellId = BONEBOUND_ECHO_COUNT_DEFAULT_AURA_SPELL_ID;
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

    bool IsBoneboundEchoModeBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "bonebound_echo_mode_v1";
    }

    bool IsBoneboundEchoStasisBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "bonebound_echo_stasis_v1";
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

    std::optional<std::vector<uint32>> ExtractJsonUIntArray(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*\\[([^\\]]*)\\]");
        std::smatch match;
        if (!std::regex_search(json, match, pattern) || match.size() <= 1)
            return std::nullopt;

        std::vector<uint32> values;
        std::string raw = match[1].str();
        std::regex numberPattern("(\\d+)");
        for (std::sregex_iterator it(raw.begin(), raw.end(), numberPattern), end; it != end; ++it)
            values.push_back(static_cast<uint32>(std::stoul((*it)[1].str())));

        return values;
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
            config.bleedEnabled = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_cooldown_ms"))
            config.bleedCooldownMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_duration_ms"))
            config.bleedDurationMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_tick_ms"))
            config.bleedTickMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_base_damage"))
            config.bleedBaseDamage = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_damage_per_level_pct"))
            config.bleedDamagePerLevelPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_damage_per_intellect_pct"))
            config.bleedDamagePerIntellectPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_damage_per_shadow_power_pct"))
            config.bleedDamagePerShadowPowerPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "shadow_dot_damage_per_attack_power_pct"))
            config.bleedDamagePerAttackPowerPct = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "bleed_enabled"))
            config.bleedEnabled = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "bleed_cooldown_ms"))
            config.bleedCooldownMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "bleed_duration_ms"))
            config.bleedDurationMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "bleed_tick_ms"))
            config.bleedTickMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "bleed_base_damage"))
            config.bleedBaseDamage = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "bleed_damage_per_level_pct"))
            config.bleedDamagePerLevelPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "bleed_damage_per_intellect_pct"))
            config.bleedDamagePerIntellectPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "bleed_damage_per_shadow_power_pct"))
            config.bleedDamagePerShadowPowerPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "bleed_damage_per_attack_power_pct"))
            config.bleedDamagePerAttackPowerPct = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "alpha_echo_enabled"))
            config.alphaEchoEnabled = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "alpha_echo_proc_chance_pct"))
            config.alphaEchoProcChancePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_echo_max_active"))
            config.alphaEchoMaxActive = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_echo_creature_entry"))
            config.alphaEchoCreatureEntry = *value;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "alpha_echo_name"))
            config.alphaEchoName = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_echo_damage_pct"))
            config.alphaEchoDamagePct = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "alpha_echo_follow_distance"))
            config.alphaEchoFollowDistance = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "alpha_echo_follow_angle"))
            config.alphaEchoFollowAngle = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "alpha_echo_hunt_radius"))
            config.alphaEchoHuntRadius = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "alpha_echo_count_aura_enabled"))
            config.alphaEchoCountAuraEnabled = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_echo_count_aura_spell_id"))
            config.alphaEchoCountAuraSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_echo_count_aura_refresh_ms"))
            config.alphaEchoCountAuraRefreshMs = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "priest_echo_enabled"))
            config.priestEchoEnabled = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_creature_entry"))
            config.priestEchoCreatureEntry = *value;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "priest_echo_name"))
            config.priestEchoName = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_display_id"))
            config.priestEchoDisplayId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_virtual_item_1"))
            config.priestEchoVirtualItem1 = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_virtual_item_2"))
            config.priestEchoVirtualItem2 = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_virtual_item_3"))
            config.priestEchoVirtualItem3 = *value;
        if (std::optional<std::vector<uint32>> value = ExtractJsonUIntArray(configJson, "priest_echo_staff_item_entries"))
            config.priestEchoStaffItemEntries = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "priest_echo_scale_multiplier"))
            config.priestEchoScaleMultiplier = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "priest_echo_proc_chance_pct"))
            config.priestEchoProcChancePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_max_active"))
            config.priestEchoMaxActive = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_pity_after_warrior_spawns"))
            config.priestEchoPityAfterWarriorSpawns = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_damage_pct"))
            config.priestEchoDamagePct = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "priest_echo_support_radius"))
            config.priestEchoSupportRadius = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_heal_below_health_pct"))
            config.priestEchoHealBelowHealthPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_heal_spell_id"))
            config.priestEchoHealSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_heal_base_pct"))
            config.priestEchoHealBasePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_heal_cooldown_ms"))
            config.priestEchoHealCooldownMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_renew_spell_id"))
            config.priestEchoRenewSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_renew_base_pct"))
            config.priestEchoRenewBasePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_renew_cooldown_ms"))
            config.priestEchoRenewCooldownMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_shield_spell_id"))
            config.priestEchoShieldSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_shield_base_pct"))
            config.priestEchoShieldBasePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_shield_cooldown_ms"))
            config.priestEchoShieldCooldownMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_disease_dispel_spell_id"))
            config.priestEchoDiseaseDispelSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_curse_dispel_spell_id"))
            config.priestEchoCurseDispelSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_dispel_cooldown_ms"))
            config.priestEchoDispelCooldownMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_mass_dispel_spell_id"))
            config.priestEchoMassDispelSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_mass_dispel_cooldown_ms"))
            config.priestEchoMassDispelCooldownMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_mass_dispel_min_affected"))
            config.priestEchoMassDispelMinAffected = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_mass_dispel_min_severity"))
            config.priestEchoMassDispelMinSeverity = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_mass_dispel_max_removals"))
            config.priestEchoMassDispelMaxRemovals = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_dps_spell_id"))
            config.priestEchoDpsSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_dps_damage_spell_id"))
            config.priestEchoDpsDamageSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_dps_cast_time_ms"))
            config.priestEchoDpsCastTimeMs = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_dps_damage_pct"))
            config.priestEchoDpsDamagePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_dps_cooldown_ms"))
            config.priestEchoDpsCooldownMs = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "priest_echo_dps_max_range"))
            config.priestEchoDpsMaxRange = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_spell_power_to_healing_pct"))
            config.priestEchoSpellPowerToHealingPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_spell_power_to_shield_pct"))
            config.priestEchoSpellPowerToShieldPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "priest_echo_spell_power_to_damage_pct"))
            config.priestEchoSpellPowerToDamagePct = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "priest_echo_safe_follow_distance"))
            config.priestEchoSafeFollowDistance = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "priest_echo_safe_min_enemy_distance"))
            config.priestEchoSafeMinEnemyDistance = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "cleave_enabled"))
            config.cleaveEnabled = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "cleave_cooldown_ms"))
            config.cleaveCooldownMs = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "cleave_radius"))
            config.cleaveRadius = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "cleave_max_targets"))
            config.cleaveMaxTargets = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_cleave_damage_pct"))
            config.alphaCleaveDamagePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "echo_cleave_damage_pct"))
            config.echoCleaveDamagePct = *value;

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

    std::optional<WmSpells::BoneboundEchoStasisConfig> BuildBoneboundEchoStasisConfig(WmSpells::BehaviorRecord const& record)
    {
        if (!IsBoneboundEchoStasisBehaviorKind(record.behaviorKind) || record.status == "disabled")
            return std::nullopt;

        WmSpells::BoneboundEchoStasisConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "alpha_shell_spell_id"))
            config.alphaShellSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "soul_shard_item_id"))
            config.soulShardItemId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "soul_shard_count"))
            config.soulShardCount = *value;

        return config;
    }

    bool IsBoneboundPet(Pet* pet)
    {
        if (!pet)
            return false;

        uint32 createdBySpellId = pet->GetUInt32Value(UNIT_CREATED_BY_SPELL);
        if (IsBoneboundShellOrBehavior(createdBySpellId))
            return true;

        // Do not fall back to stock entry/display heuristics here. Bonebound
        // must stay structurally separate from stock warlock summons such as
        // Summon Voidwalker (697), even when they share visuals.
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

    float ResolveBoneboundCasterAttackPower(Unit* caster)
    {
        if (!caster)
            return 0.0f;

        float baseAttackPower = static_cast<float>(caster->GetInt32Value(UNIT_FIELD_ATTACK_POWER));
        float attackPowerMods = static_cast<float>(caster->GetInt32Value(UNIT_FIELD_ATTACK_POWER_MODS));
        float attackPowerMultiplier = caster->GetFloatValue(UNIT_FIELD_ATTACK_POWER_MULTIPLIER);
        return std::max(0.0f, (baseAttackPower + attackPowerMods) * (1.0f + attackPowerMultiplier));
    }

    uint32 ResolveBoneboundBleedTickDamage(Player* owner, Unit* caster, WmSpells::BoneboundBehaviorConfig const& config, uint32 damagePct)
    {
        if (!owner)
            return 1u;

        float intellect = std::max(0.0f, owner->GetTotalStatValue(STAT_INTELLECT));
        int32 shadowPower = std::max<int32>(0, owner->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW));
        float attackPower = ResolveBoneboundCasterAttackPower(caster);
        uint32 level = caster ? caster->GetLevel() : owner->GetLevel();
        float damage = static_cast<float>(config.bleedBaseDamage)
            + attackPower * (static_cast<float>(config.bleedDamagePerAttackPowerPct) / 100.0f)
            + static_cast<float>(level) * (static_cast<float>(config.bleedDamagePerLevelPct) / 100.0f)
            + intellect * (static_cast<float>(config.bleedDamagePerIntellectPct) / 100.0f)
            + static_cast<float>(shadowPower) * (static_cast<float>(config.bleedDamagePerShadowPowerPct) / 100.0f);
        uint32 resolved = std::max<uint32>(1u, static_cast<uint32>(std::round(damage)));
        if (damagePct == 100u)
            return resolved;

        uint64 scaled = (static_cast<uint64>(resolved) * static_cast<uint64>(std::max<uint32>(1u, damagePct)) + 50u) / 100u;
        return std::max<uint32>(1u, static_cast<uint32>(std::min<uint64>(scaled, std::numeric_limits<uint32>::max())));
    }

    Aura* ApplyBoneboundBleedVisibleAura(Unit* caster, Unit* target, uint32 durationMs)
    {
        if (!caster || !target)
            return nullptr;

        Aura* aura = caster->AddAura(BONEBOUND_BLEED_VISIBLE_AURA_SPELL_ID, target);
        if (!aura)
            aura = target->GetAura(BONEBOUND_BLEED_VISIBLE_AURA_SPELL_ID, caster->GetGUID());
        if (!aura)
            return nullptr;

        aura->SetMaxDuration(static_cast<int32>(durationMs));
        aura->SetDuration(static_cast<int32>(durationMs));
        for (uint8 effectIndex = 0; effectIndex < MAX_SPELL_EFFECTS; ++effectIndex)
        {
            if (AuraEffect* effect = aura->GetEffect(effectIndex))
            {
                effect->SetAmount(0);
                effect->SetPeriodic(false);
            }
        }
        return aura;
    }

    bool HasBoneboundBleedVisibleAura(Unit* caster, Unit* target)
    {
        if (!caster || !target)
            return false;

        Aura* aura = target->GetAura(BONEBOUND_BLEED_VISIBLE_AURA_SPELL_ID, caster->GetGUID());
        return aura && aura->GetDuration() > 0;
    }

    void StartBoneboundBleed(Player* owner, Unit* caster, Unit* target, WmSpells::BoneboundBehaviorConfig const& config, uint32 damagePct)
    {
        if (!owner || !caster || !target || !target->IsAlive() || !config.bleedEnabled)
            return;

        uint32 durationMs = std::max<uint32>(1000u, config.bleedDurationMs);
        Aura* visibleAura = ApplyBoneboundBleedVisibleAura(caster, target, durationMs);
        if (!visibleAura)
            return;

        uint32 tickMs = std::max<uint32>(500u, config.bleedTickMs);
        uint32 tickDamage = ResolveBoneboundBleedTickDamage(owner, caster, config, damagePct);

        for (BoneboundBleedState& bleed : gBoneboundBleeds)
        {
            if (bleed.casterGuid == caster->GetGUID() && bleed.targetGuid == target->GetGUID())
            {
                bleed.ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
                bleed.remainingMs = durationMs;
                bleed.tickMs = tickMs;
                bleed.tickTimerMs = tickMs;
                bleed.tickDamage = tickDamage;
                return;
            }
        }

        BoneboundBleedState bleed;
        bleed.casterGuid = caster->GetGUID();
        bleed.targetGuid = target->GetGUID();
        bleed.ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        bleed.remainingMs = durationMs;
        bleed.tickMs = tickMs;
        bleed.tickTimerMs = tickMs;
        bleed.tickDamage = tickDamage;
        gBoneboundBleeds.push_back(bleed);
    }

    void UpdateBoneboundBleedCooldowns(uint32 diff)
    {
        if (diff == 0 || gBoneboundBleedCooldownByCaster.empty())
            return;

        for (auto it = gBoneboundBleedCooldownByCaster.begin(); it != gBoneboundBleedCooldownByCaster.end();)
        {
            if (it->second > diff)
            {
                it->second -= diff;
                ++it;
            }
            else
            {
                it = gBoneboundBleedCooldownByCaster.erase(it);
            }
        }
    }

    void UpdateBoneboundCleaveCooldowns(uint32 diff)
    {
        if (diff == 0 || gBoneboundCleaveCooldownByCaster.empty())
            return;

        for (auto it = gBoneboundCleaveCooldownByCaster.begin(); it != gBoneboundCleaveCooldownByCaster.end();)
        {
            if (it->second > diff)
            {
                it->second -= diff;
                ++it;
            }
            else
            {
                it = gBoneboundCleaveCooldownByCaster.erase(it);
            }
        }
    }

    void UpdateBoneboundPriestEchoCooldowns(uint32 diff)
    {
        auto updateCooldowns = [diff](std::unordered_map<uint32, uint32>& cooldowns)
        {
            if (diff == 0 || cooldowns.empty())
                return;

            for (auto it = cooldowns.begin(); it != cooldowns.end();)
            {
                if (it->second > diff)
                {
                    it->second -= diff;
                    ++it;
                }
                else
                {
                    it = cooldowns.erase(it);
                }
            }
        };

        updateCooldowns(gBoneboundPriestHealCooldownByCaster);
        updateCooldowns(gBoneboundPriestRenewCooldownByCaster);
        updateCooldowns(gBoneboundPriestShieldCooldownByCaster);
        updateCooldowns(gBoneboundPriestDpsCooldownByCaster);
        updateCooldowns(gBoneboundPriestDispelCooldownByCaster);
        updateCooldowns(gBoneboundPriestMassDispelCooldownByCaster);
    }

    uint32 CountActiveBoneboundEchoes(uint32 ownerGuid, std::optional<BoneboundEchoRole> role = std::nullopt)
    {
        uint32 count = 0;
        for (auto const& [_, echo] : gBoneboundAlphaEchoes)
        {
            if (echo.ownerGuid == ownerGuid && (!role.has_value() || echo.role == *role))
                ++count;
        }
        return count;
    }

    uint32 CountActiveBoneboundAlphaEchoes(uint32 ownerGuid)
    {
        return CountActiveBoneboundEchoes(ownerGuid);
    }

    uint32 CountActiveBoneboundWarriorEchoes(uint32 ownerGuid)
    {
        return CountActiveBoneboundEchoes(ownerGuid, BoneboundEchoRole::Warrior);
    }

    uint32 CountActiveBoneboundPriestEchoes(uint32 ownerGuid)
    {
        return CountActiveBoneboundEchoes(ownerGuid, BoneboundEchoRole::Priest);
    }

    BoneboundEchoStasisCounts CountActiveBoneboundEchoesByRole(uint32 ownerGuid)
    {
        return {
            CountActiveBoneboundWarriorEchoes(ownerGuid),
            CountActiveBoneboundPriestEchoes(ownerGuid),
        };
    }

    uint32 SaturatingAddUInt32(uint32 left, uint32 right)
    {
        uint64 sum = static_cast<uint64>(left) + static_cast<uint64>(right);
        return static_cast<uint32>(std::min<uint64>(sum, std::numeric_limits<uint32>::max()));
    }

    BoneboundEchoStasisCounts AddBoneboundEchoStasisCounts(
        BoneboundEchoStasisCounts const& storedCounts,
        BoneboundEchoStasisCounts const& activeCounts)
    {
        return {
            SaturatingAddUInt32(storedCounts.destroyers, activeCounts.destroyers),
            SaturatingAddUInt32(storedCounts.restorers, activeCounts.restorers),
        };
    }

    BoneboundEchoStasisCounts SubtractBoneboundEchoStasisCounts(
        BoneboundEchoStasisCounts const& storedCounts,
        BoneboundEchoStasisCounts const& restoredCounts)
    {
        return {
            storedCounts.destroyers > restoredCounts.destroyers
                ? storedCounts.destroyers - restoredCounts.destroyers
                : 0u,
            storedCounts.restorers > restoredCounts.restorers
                ? storedCounts.restorers - restoredCounts.restorers
                : 0u,
        };
    }

    float ClampBoneboundEchoHuntRadius(float radius)
    {
        if (!std::isfinite(radius))
            return 35.0f;

        return std::clamp(radius, 5.0f, 100.0f);
    }

    float ResolveBoneboundEchoHuntRadius(uint32 ownerGuid, std::optional<WmSpells::BoneboundBehaviorConfig> const& runtimeConfig)
    {
        auto overrideIt = gBoneboundEchoHuntRadiusByPlayer.find(ownerGuid);
        if (overrideIt != gBoneboundEchoHuntRadiusByPlayer.end())
            return ClampBoneboundEchoHuntRadius(overrideIt->second);

        if (runtimeConfig.has_value())
            return ClampBoneboundEchoHuntRadius(runtimeConfig->alphaEchoHuntRadius);

        return 35.0f;
    }

    bool IsBoneboundEchoHuntMode(uint32 ownerGuid)
    {
        auto it = gBoneboundEchoHuntModeByPlayer.find(ownerGuid);
        return it != gBoneboundEchoHuntModeByPlayer.end() && it->second;
    }

    void ClearBoneboundEchoCountAura(Player* owner)
    {
        if (!owner)
            return;

        uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        auto it = gBoneboundEchoCountAuraByPlayer.find(ownerGuid);
        if (it == gBoneboundEchoCountAuraByPlayer.end())
            return;

        owner->RemoveAurasDueToSpell(it->second);
        gBoneboundEchoCountAuraByPlayer.erase(it);
    }

    void StripAuraEffects(Aura* aura)
    {
        if (!aura)
            return;

        for (uint8 effectIndex = 0; effectIndex < MAX_SPELL_EFFECTS; ++effectIndex)
        {
            if (AuraEffect* effect = aura->GetEffect(effectIndex))
            {
                effect->SetAmount(0);
                effect->SetPeriodic(false);
            }
        }
    }

    void RefreshBoneboundEchoCountAura(Player* owner, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner)
            return;

        uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        uint32 activeCount = CountActiveBoneboundAlphaEchoes(ownerGuid);
        if (!config.alphaEchoCountAuraEnabled || config.alphaEchoCountAuraSpellId == 0 || activeCount == 0)
        {
            ClearBoneboundEchoCountAura(owner);
            return;
        }

        auto existingAuraIt = gBoneboundEchoCountAuraByPlayer.find(ownerGuid);
        if (existingAuraIt != gBoneboundEchoCountAuraByPlayer.end() && existingAuraIt->second != config.alphaEchoCountAuraSpellId)
            ClearBoneboundEchoCountAura(owner);

        Aura* aura = owner->AddAura(config.alphaEchoCountAuraSpellId, owner);
        if (!aura)
            aura = owner->GetAura(config.alphaEchoCountAuraSpellId, owner->GetGUID());
        if (!aura)
            return;

        aura->SetMaxDuration(-1);
        aura->SetDuration(-1);
        aura->SetStackAmount(static_cast<uint8>(std::min<uint32>(255u, activeCount)));
        StripAuraEffects(aura);
        gBoneboundEchoCountAuraByPlayer[ownerGuid] = config.alphaEchoCountAuraSpellId;
    }

    void SeedBoneboundOwnerKillCredit(Player* owner, Unit* victim, uint32 creditedDamage = 0)
    {
        if (!owner || !victim || !victim->IsAlive() || !WmSpells::IsPlayerAllowed(owner))
            return;

        if (Creature* creature = victim->ToCreature())
        {
            if (!creature->hasLootRecipient())
                creature->SetLootRecipient(owner, true);

            if (creditedDamage > 0)
            {
                uint32 damageCredit = std::min<uint32>(
                    std::max<uint32>(1u, creditedDamage),
                    std::max<uint32>(1u, creature->GetHealth()));
                creature->LowerPlayerDamageReq(damageCredit, true);
            }
        }

        owner->SetInCombatWith(victim);
        victim->SetInCombatWith(owner);
        if (victim->CanHaveThreatList())
            victim->AddThreat(owner, 1.0f);
    }

    std::vector<Unit*> SelectBoneboundCleaveTargets(Unit* caster, Unit* primaryVictim, float radius, uint32 maxTargets)
    {
        std::vector<Unit*> targets;
        if (!caster || radius <= 0.0f || maxTargets == 0)
            return targets;

        std::list<Unit*> nearby;
        Acore::AnyUnfriendlyUnitInObjectRangeCheck check(caster, caster, radius);
        Acore::UnitListSearcher<Acore::AnyUnfriendlyUnitInObjectRangeCheck> searcher(caster, nearby, check);
        Cell::VisitObjects(caster, searcher, radius);

        for (Unit* target : nearby)
        {
            if (!target || target == caster || target == primaryVictim || !target->IsAlive() || caster->IsFriendlyTo(target))
                continue;

            targets.push_back(target);
            if (targets.size() >= maxTargets)
                break;
        }
        return targets;
    }

    Unit* SelectNearestBoneboundSeekTarget(Player* owner, Creature* seeker, float radius)
    {
        if (!owner || !seeker || radius <= 0.0f || owner->GetMapId() != seeker->GetMapId())
            return nullptr;

        std::list<Unit*> nearby;
        Acore::AnyUnfriendlyUnitInObjectRangeCheck check(owner, owner, radius);
        Acore::UnitListSearcher<Acore::AnyUnfriendlyUnitInObjectRangeCheck> searcher(owner, nearby, check);
        Cell::VisitObjects(owner, searcher, radius);

        Unit* bestTarget = nullptr;
        float bestDistance = std::numeric_limits<float>::max();
        for (Unit* candidate : nearby)
        {
            if (!candidate
                || candidate == owner
                || candidate == seeker
                || !candidate->IsAlive()
                || candidate->GetMapId() != owner->GetMapId()
                || !owner->IsWithinDistInMap(candidate, radius)
                || owner->IsFriendlyTo(candidate)
                || !seeker->CanCreatureAttack(candidate, true)
                || !seeker->IsWithinLOSInMap(candidate))
                continue;

            float distance = owner->GetDistance(candidate);
            if (!bestTarget || distance < bestDistance)
            {
                bestTarget = candidate;
                bestDistance = distance;
            }
        }

        return bestTarget;
    }

    void TryBoneboundCleave(
        Player* owner,
        Unit* caster,
        Unit* primaryVictim,
        WmSpells::BoneboundBehaviorConfig const& config,
        uint32 baseDamage,
        uint32 cleaveDamagePct)
    {
        if (!owner || !caster || !primaryVictim || !primaryVictim->IsAlive() || !config.cleaveEnabled || baseDamage == 0 || cleaveDamagePct == 0)
            return;

        uint32 casterGuid = static_cast<uint32>(caster->GetGUID().GetCounter());
        uint32& cooldown = gBoneboundCleaveCooldownByCaster[casterGuid];
        if (cooldown != 0)
            return;

        std::vector<Unit*> targets = SelectBoneboundCleaveTargets(
            caster,
            primaryVictim,
            std::max(1.0f, config.cleaveRadius),
            std::max<uint32>(1u, config.cleaveMaxTargets));
        if (targets.empty())
            return;

        uint32 damage = std::max<uint32>(1u, (static_cast<uint64>(baseDamage) * static_cast<uint64>(cleaveDamagePct)) / 100u);
        for (Unit* target : targets)
        {
            SeedBoneboundOwnerKillCredit(owner, target, damage);
            SpellCastResult result = caster->CastCustomSpell(
                BONEBOUND_SLASH_SPELL_ID,
                SPELLVALUE_BASE_POINT0,
                static_cast<int32>(std::min<uint32>(damage, static_cast<uint32>(std::numeric_limits<int32>::max()))),
                target,
                true);
            if (result != SPELL_CAST_OK)
                continue;
        }

        cooldown = std::max<uint32>(500u, config.cleaveCooldownMs);
    }

    uint32 ResolveAlphaEchoDurationMs(Player* owner)
    {
        if (!owner)
            return 1000u;

        uint32 seconds = std::max<uint32>(1u, static_cast<uint32>(std::round(std::max(0.0f, owner->GetTotalStatValue(STAT_INTELLECT)))));
        return seconds * 1000u;
    }

    uint32 BoneboundEchoFormationRingCapacity(float followDistance)
    {
        float circumference = std::max(1.0f, followDistance) * WM_PI * 2.0f;
        return std::max<uint32>(
            1u,
            static_cast<uint32>(std::floor(circumference / BONEBOUND_ECHO_MIN_FOLLOW_SEPARATION_YARDS)));
    }

    float NormalizeBoneboundEchoFollowAngle(float angle)
    {
        while (angle > WM_PI)
            angle -= WM_PI * 2.0f;
        while (angle < -WM_PI)
            angle += WM_PI * 2.0f;
        return angle;
    }

    BoneboundEchoFormationSlot ResolveBoneboundEchoFormationSlot(
        WmSpells::BoneboundBehaviorConfig const& config,
        BoneboundEchoRole role,
        uint32 ordinal)
    {
        bool priestEcho = role == BoneboundEchoRole::Priest;
        float baseDistance = priestEcho
            ? std::max(1.8f, config.priestEchoSafeFollowDistance)
            : std::max(3.2f, config.alphaEchoFollowDistance);

        uint32 ring = 0;
        uint32 slot = ordinal;
        float followDistance = baseDistance;
        for (;;)
        {
            uint32 capacity = BoneboundEchoFormationRingCapacity(followDistance);
            if (slot < capacity)
            {
                float angleStep = (WM_PI * 2.0f) / static_cast<float>(capacity);
                float roleOffset = priestEcho ? angleStep * 0.5f : 0.0f;
                float ringOffset = (ring % 2u == 0u) ? 0.0f : angleStep * 0.5f;
                return {
                    followDistance,
                    NormalizeBoneboundEchoFollowAngle(
                        config.alphaEchoFollowAngle
                        + roleOffset
                        + ringOffset
                        + static_cast<float>(slot) * angleStep),
                };
            }

            slot -= capacity;
            ++ring;
            followDistance += BONEBOUND_ECHO_MIN_FOLLOW_SEPARATION_YARDS;
        }
    }

    void RefreshBoneboundEchoFormationSlots(Player* owner, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!owner)
            return;

        uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        std::vector<uint32> warriorEchoes;
        std::vector<uint32> priestEchoes;
        for (auto const& [echoGuid, state] : gBoneboundAlphaEchoes)
        {
            if (state.ownerGuid != ownerGuid)
                continue;

            if (state.role == BoneboundEchoRole::Priest)
                priestEchoes.push_back(echoGuid);
            else
                warriorEchoes.push_back(echoGuid);
        }

        auto applySlots = [owner, &config](std::vector<uint32>& echoGuids, BoneboundEchoRole role)
        {
            std::sort(echoGuids.begin(), echoGuids.end());
            for (uint32 index = 0; index < echoGuids.size(); ++index)
            {
                auto stateIt = gBoneboundAlphaEchoes.find(echoGuids[index]);
                if (stateIt == gBoneboundAlphaEchoes.end())
                    continue;

                BoneboundEchoFormationSlot slot = ResolveBoneboundEchoFormationSlot(config, role, index);
                stateIt->second.followDistance = slot.followDistance;
                stateIt->second.followAngle = slot.followAngle;

                Creature* echo = ObjectAccessor::GetCreature(*owner, stateIt->second.echoGuid);
                if (echo && echo->IsAlive() && !echo->IsInCombat())
                    echo->GetMotionMaster()->MoveFollow(owner, slot.followDistance, slot.followAngle);
            }
        };

        applySlots(warriorEchoes, BoneboundEchoRole::Warrior);
        applySlots(priestEchoes, BoneboundEchoRole::Priest);
    }

    uint32 ResolveBoneboundPriestEchoStaffItem(WmSpells::BoneboundBehaviorConfig const& config);

    BoneboundAlphaEchoState BuildBoneboundAlphaEchoState(
        Player* owner,
        WmSpells::BoneboundBehaviorConfig const& config,
        BoneboundEchoRole requestedRole)
    {
        bool priestEcho = requestedRole == BoneboundEchoRole::Priest;
        uint32 echoEntry = priestEcho
            ? config.priestEchoCreatureEntry
            : (config.alphaEchoCreatureEntry != 0 ? config.alphaEchoCreatureEntry : config.creatureEntry);
        uint32 ownerGuid = owner ? static_cast<uint32>(owner->GetGUID().GetCounter()) : 0;
        BoneboundEchoFormationSlot formationSlot = ResolveBoneboundEchoFormationSlot(
            config,
            requestedRole,
            CountActiveBoneboundEchoes(ownerGuid, requestedRole));
        BoneboundAlphaEchoState state;
        state.ownerGuid = ownerGuid;
        state.creatureEntry = echoEntry;
        state.remainingMs = ResolveAlphaEchoDurationMs(owner);
        state.damagePct = std::max<uint32>(1u, priestEcho ? config.priestEchoDamagePct : config.alphaEchoDamagePct);
        state.role = priestEcho ? BoneboundEchoRole::Priest : BoneboundEchoRole::Warrior;
        state.virtualItem1 = priestEcho ? ResolveBoneboundPriestEchoStaffItem(config) : 0;
        state.virtualItem2 = priestEcho ? config.priestEchoVirtualItem2 : 0;
        state.virtualItem3 = priestEcho ? config.priestEchoVirtualItem3 : 0;
        state.followDistance = formationSlot.followDistance;
        state.followAngle = formationSlot.followAngle;
        return state;
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

        echo->SetLevel(alphaPet->GetLevel());
        echo->SetCreateHealth(desiredMaxHealth);
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
        echo->SetLevel(alphaPet->GetLevel());
    }

    void MatchBoneboundEchoMovementSpeed(Pet* alphaPet, TempSummon* echo)
    {
        if (!alphaPet || !echo)
            return;

        echo->SetWalk(false);
        echo->SetSpeed(MOVE_WALK, alphaPet->GetSpeedRate(MOVE_WALK), true);
        echo->SetSpeed(MOVE_RUN, alphaPet->GetSpeedRate(MOVE_RUN), true);
        echo->SetSpeed(MOVE_RUN_BACK, alphaPet->GetSpeedRate(MOVE_RUN_BACK), true);
        echo->SetSpeed(MOVE_SWIM, alphaPet->GetSpeedRate(MOVE_SWIM), true);
        echo->SetSpeed(MOVE_SWIM_BACK, alphaPet->GetSpeedRate(MOVE_SWIM_BACK), true);
        echo->SetSpeed(MOVE_FLIGHT, alphaPet->GetSpeedRate(MOVE_FLIGHT), true);
        echo->SetSpeed(MOVE_FLIGHT_BACK, alphaPet->GetSpeedRate(MOVE_FLIGHT_BACK), true);
    }

    bool IsBoneboundPriestEcho(BoneboundAlphaEchoState const& state)
    {
        return state.role == BoneboundEchoRole::Priest;
    }

    uint32 ResolveBoneboundPriestEchoStaffItem(WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (config.priestEchoVirtualItem1 != 0)
            return config.priestEchoVirtualItem1;

        if (config.priestEchoStaffItemEntries.empty())
            return 0;

        return config.priestEchoStaffItemEntries[urand(0, static_cast<uint32>(config.priestEchoStaffItemEntries.size() - 1))];
    }

    uint32 ResolvePercentOfMaxHealth(Unit* target, uint32 pct)
    {
        if (!target)
            return 1u;

        uint64 amount = (static_cast<uint64>(std::max<uint32>(1u, target->GetMaxHealth())) * std::max<uint32>(1u, pct)) / 100u;
        return std::max<uint32>(1u, static_cast<uint32>(std::min<uint64>(amount, std::numeric_limits<uint32>::max())));
    }

    uint32 ResolveBoneboundPriestSpellPowerBonus(Player* owner, uint32 pct)
    {
        if (!owner || pct == 0)
            return 0;

        uint32 shadowPower = static_cast<uint32>(std::max<int32>(0, owner->SpellBaseDamageBonusDone(SPELL_SCHOOL_MASK_SHADOW)));
        uint64 amount = (static_cast<uint64>(shadowPower) * static_cast<uint64>(pct)) / 100u;
        return static_cast<uint32>(std::min<uint64>(amount, std::numeric_limits<uint32>::max()));
    }

    uint32 AddBoneboundPriestSpellPowerBonus(uint32 baseAmount, Player* owner, uint32 pct)
    {
        uint64 amount = static_cast<uint64>(std::max<uint32>(1u, baseAmount)) + ResolveBoneboundPriestSpellPowerBonus(owner, pct);
        return static_cast<uint32>(std::min<uint64>(std::max<uint64>(1u, amount), std::numeric_limits<uint32>::max()));
    }

    int32 ClampSpellBasePoint(uint32 amount)
    {
        return static_cast<int32>(std::min<uint32>(std::max<uint32>(1u, amount), static_cast<uint32>(std::numeric_limits<int32>::max())));
    }

    bool TryCastBoneboundPriestEchoSpell(Creature* priestEcho, Unit* target, uint32 spellId, uint32 basePoint, bool triggered = true)
    {
        if (!priestEcho || !target || !target->IsAlive() || spellId == 0)
            return false;

        SpellCastResult result = priestEcho->CastCustomSpell(
            spellId,
            SPELLVALUE_BASE_POINT0,
            ClampSpellBasePoint(basePoint),
            target,
            triggered);
        return result == SPELL_CAST_OK;
    }

    bool DealBoneboundPriestDpsDamage(
        Creature* priestEcho,
        Unit* target,
        Player* owner,
        uint32 damage,
        uint32 damageSpellId)
    {
        if (!priestEcho || !target || !target->IsAlive() || !owner || damage == 0 || damageSpellId == 0)
            return false;

        SpellInfo const* spellInfo = sSpellMgr->GetSpellInfo(damageSpellId);
        if (!spellInfo)
            return false;

        uint32 adjustedDamage = std::max<uint32>(1u, damage);
        SpellNonMeleeDamage damageInfo(priestEcho, target, spellInfo, SPELL_SCHOOL_MASK_SHADOW);
        damageInfo.damage = adjustedDamage;
        Unit::DealDamageMods(target, damageInfo.damage, &damageInfo.absorb);
        damageInfo.overkill = damageInfo.damage > target->GetHealth() ? damageInfo.damage - target->GetHealth() : 0;

        priestEcho->SendSpellNonMeleeDamageLog(&damageInfo);
        priestEcho->DealSpellDamage(&damageInfo, false);
        SeedBoneboundOwnerKillCredit(owner, target, damageInfo.damage);
        return true;
    }

    float ClampBoneboundPriestDpsMaxRange(float maxRange)
    {
        if (!std::isfinite(maxRange) || maxRange <= 0.0f)
            return 100.0f;
        return std::clamp(maxRange, 5.0f, 100.0f);
    }

    float ResolveBoneboundPriestDpsMaxRange(WmSpells::BoneboundBehaviorConfig const& config)
    {
        return ClampBoneboundPriestDpsMaxRange(config.priestEchoDpsMaxRange);
    }

    float ResolveBoneboundPriestVisibleDpsCastRange(Creature* priestEcho, WmSpells::BoneboundBehaviorConfig const& config)
    {
        float configuredRange = ResolveBoneboundPriestDpsMaxRange(config);
        SpellInfo const* spellInfo = sSpellMgr->GetSpellInfo(config.priestEchoDpsSpellId);
        if (!spellInfo)
            return configuredRange;

        float spellRange = spellInfo->GetMaxRange(false, priestEcho);
        if (!std::isfinite(spellRange) || spellRange <= 0.0f)
            return configuredRange;

        return std::min(configuredRange, std::max(5.0f, spellRange + 1.5f));
    }

    bool UpdateBoneboundPriestDpsCast(
        Creature* priestEcho,
        Player* owner,
        uint32 diff)
    {
        if (!priestEcho || !owner)
            return false;

        uint32 echoGuid = static_cast<uint32>(priestEcho->GetGUID().GetCounter());
        auto it = gBoneboundPriestDpsCastByCaster.find(echoGuid);
        if (it == gBoneboundPriestDpsCastByCaster.end())
            return false;

        if (it->second.remainingMs > diff)
        {
            it->second.remainingMs -= diff;
            return true;
        }

        BoneboundPriestDpsCastState castState = it->second;
        gBoneboundPriestDpsCastByCaster.erase(it);

        Unit* target = ObjectAccessor::GetUnit(*owner, castState.targetGuid);
        if (!target || !target->IsAlive() || !priestEcho->CanCreatureAttack(target, true))
            return false;
        if (!priestEcho->IsWithinDistInMap(target, ClampBoneboundPriestDpsMaxRange(castState.maxRange)))
            return false;
        if (!priestEcho->IsWithinLOSInMap(target))
            return false;

        uint32 damageSpellId = castState.damageSpellId != 0 ? castState.damageSpellId : castState.visualSpellId;
        if (damageSpellId == castState.visualSpellId)
        {
            SpellCastResult result = priestEcho->CastCustomSpell(
                damageSpellId,
                SPELLVALUE_BASE_POINT0,
                ClampSpellBasePoint(castState.damage),
                target,
                true);
            if (result == SPELL_CAST_OK)
                SeedBoneboundOwnerKillCredit(owner, target, castState.damage);
        }
        else
        {
            DealBoneboundPriestDpsDamage(
                priestEcho,
                target,
                owner,
                castState.damage,
                damageSpellId);
        }
        return false;
    }

    bool TryStartBoneboundPriestDpsCast(
        Creature* priestEcho,
        Unit* target,
        Player* owner,
        WmSpells::BoneboundBehaviorConfig const& config,
        uint32 damage)
    {
        if (!priestEcho || !target || !target->IsAlive() || !owner || config.priestEchoDpsSpellId == 0)
            return false;

        uint32 echoGuid = static_cast<uint32>(priestEcho->GetGUID().GetCounter());
        if (gBoneboundPriestDpsCastByCaster.find(echoGuid) != gBoneboundPriestDpsCastByCaster.end())
            return false;

        SpellInfo const* visualSpellInfo = sSpellMgr->GetSpellInfo(config.priestEchoDpsSpellId);
        SpellInfo const* damageSpellInfo = sSpellMgr->GetSpellInfo(
            config.priestEchoDpsDamageSpellId != 0 ? config.priestEchoDpsDamageSpellId : config.priestEchoDpsSpellId);
        if (!visualSpellInfo || !damageSpellInfo)
            return false;

        uint32 desiredCastMs = std::max<uint32>(1u, config.priestEchoDpsCastTimeMs);
        float maxRange = ResolveBoneboundPriestDpsMaxRange(config);
        float visibleCastRange = ResolveBoneboundPriestVisibleDpsCastRange(priestEcho, config);
        if (!priestEcho->IsWithinDistInMap(target, visibleCastRange))
            return false;
        if (!priestEcho->IsWithinLOSInMap(target))
            return false;

        priestEcho->AttackStop();
        priestEcho->SetFacingToObject(target);

        uint32 damageSpellId = config.priestEchoDpsDamageSpellId != 0 ? config.priestEchoDpsDamageSpellId : config.priestEchoDpsSpellId;
        bool damageIsNativeSpellHit = damageSpellId == config.priestEchoDpsSpellId;
        if (damageIsNativeSpellHit)
        {
            uint32 baseCastMs = visualSpellInfo->CalcCastTime();
            float previousCastSpeed = priestEcho->GetFloatValue(UNIT_MOD_CAST_SPEED);
            bool adjustedCastSpeed = false;
            if (baseCastMs > 0 && desiredCastMs > 0)
            {
                float desiredCastSpeed = std::clamp(
                    static_cast<float>(desiredCastMs) / static_cast<float>(baseCastMs),
                    0.05f,
                    5.0f);
                priestEcho->SetFloatValue(UNIT_MOD_CAST_SPEED, desiredCastSpeed);
                adjustedCastSpeed = true;
            }

            SpellCastResult result = priestEcho->CastCustomSpell(
                damageSpellId,
                SPELLVALUE_BASE_POINT0,
                ClampSpellBasePoint(std::max<uint32>(1u, damage)),
                target,
                false);
            if (adjustedCastSpeed)
                priestEcho->SetFloatValue(UNIT_MOD_CAST_SPEED, previousCastSpeed);

            if (result == SPELL_CAST_OK)
                SeedBoneboundOwnerKillCredit(owner, target, damage);
            return result == SPELL_CAST_OK;
        }

        uint32 baseCastMs = visualSpellInfo->CalcCastTime();
        float previousCastSpeed = priestEcho->GetFloatValue(UNIT_MOD_CAST_SPEED);
        bool adjustedCastSpeed = false;
        if (baseCastMs > 0 && desiredCastMs > 0)
        {
            float desiredCastSpeed = std::clamp(
                static_cast<float>(desiredCastMs) / static_cast<float>(baseCastMs),
                0.05f,
                5.0f);
            priestEcho->SetFloatValue(UNIT_MOD_CAST_SPEED, desiredCastSpeed);
            adjustedCastSpeed = true;
        }

        SpellCastResult result = priestEcho->CastSpell(target, config.priestEchoDpsSpellId, false);
        if (adjustedCastSpeed)
            priestEcho->SetFloatValue(UNIT_MOD_CAST_SPEED, previousCastSpeed);

        if (result != SPELL_CAST_OK)
            return false;

        gBoneboundPriestDpsCastByCaster[echoGuid] = BoneboundPriestDpsCastState{
            target->GetGUID(),
            static_cast<uint32>(owner->GetGUID().GetCounter()),
            config.priestEchoDpsSpellId,
            damageSpellId,
            std::max<uint32>(1u, damage),
            desiredCastMs,
            maxRange,
        };
        return true;
    }

    void AddUniqueBoneboundPriestSupportTarget(std::vector<Unit*>& targets, Unit* candidate)
    {
        if (!candidate || !candidate->IsAlive())
            return;

        if (std::find(targets.begin(), targets.end(), candidate) == targets.end())
            targets.push_back(candidate);
    }

    std::vector<Unit*> CollectBoneboundPriestSupportTargets(
        Creature* priestEcho,
        Player* owner,
        Pet* alphaPet,
        WmSpells::BoneboundBehaviorConfig const& config)
    {
        std::vector<Unit*> targets;
        if (!priestEcho || !owner)
            return targets;

        float radius = std::max(5.0f, config.priestEchoSupportRadius);
        auto addIfValid = [&](Unit* candidate)
        {
            if (!candidate
                || !candidate->IsAlive()
                || candidate->GetMapId() != priestEcho->GetMapId()
                || !priestEcho->IsWithinDistInMap(candidate, radius)
                || !priestEcho->IsWithinLOSInMap(candidate)
                || !priestEcho->IsFriendlyTo(candidate))
                return;

            AddUniqueBoneboundPriestSupportTarget(targets, candidate);
        };

        addIfValid(owner);
        addIfValid(alphaPet);
        for (auto const& [_, state] : gBoneboundAlphaEchoes)
        {
            if (state.ownerGuid != static_cast<uint32>(owner->GetGUID().GetCounter()))
                continue;

            addIfValid(ObjectAccessor::GetCreature(*owner, state.echoGuid));
        }

        if (Group* group = owner->GetGroup())
        {
            for (GroupReference* ref = group->GetFirstMember(); ref; ref = ref->next())
            {
                Player* member = ref->GetSource();
                if (!member || !member->IsAlive() || member->IsGameMaster())
                    continue;

                addIfValid(member);
                addIfValid(member->GetPet());
                addIfValid(member->GetCharm());
            }
        }

        return targets;
    }

    bool IsBoneboundPriestTargetUnderThreat(Unit* candidate)
    {
        if (!candidate || !candidate->IsAlive())
            return false;

        for (Unit* attacker : candidate->getAttackers())
        {
            if (!attacker || !attacker->IsAlive())
                continue;

            if (attacker->GetVictim() == candidate || attacker->IsNonMeleeSpellCast(false))
                return true;
        }

        return false;
    }

    uint32 ScoreBoneboundPriestDebuff(AuraApplication const* auraApplication, SpellInfo const* spellInfo)
    {
        if (!auraApplication || !spellInfo || auraApplication->IsPositive())
            return 0;

        uint32 score = 0;
        switch (spellInfo->Dispel)
        {
            case DISPEL_CURSE:
            case DISPEL_DISEASE:
                score += 3;
                break;
            case DISPEL_MAGIC:
            case DISPEL_POISON:
                score += 2;
                break;
            default:
                return 0;
        }

        if (spellInfo->HasAura(SPELL_AURA_MOD_STUN)
            || spellInfo->HasAura(SPELL_AURA_MOD_FEAR)
            || spellInfo->HasAura(SPELL_AURA_MOD_CONFUSE)
            || spellInfo->HasAura(SPELL_AURA_MOD_PACIFY)
            || spellInfo->HasAura(SPELL_AURA_MOD_PACIFY_SILENCE)
            || spellInfo->HasAura(SPELL_AURA_MOD_SILENCE))
            score += 4;

        if (spellInfo->HasAura(SPELL_AURA_MOD_ROOT)
            || spellInfo->HasAura(SPELL_AURA_MOD_DECREASE_SPEED))
            score += 2;

        if (spellInfo->HasAura(SPELL_AURA_PERIODIC_DAMAGE)
            || spellInfo->HasAura(SPELL_AURA_PERIODIC_DAMAGE_PERCENT)
            || spellInfo->HasAura(SPELL_AURA_PERIODIC_LEECH)
            || spellInfo->HasAura(SPELL_AURA_PERIODIC_MANA_LEECH))
            score += 2;

        if (spellInfo->HasAura(SPELL_AURA_MOD_DAMAGE_PERCENT_TAKEN)
            || spellInfo->HasAura(SPELL_AURA_MOD_DAMAGE_TAKEN)
            || spellInfo->HasAura(SPELL_AURA_MOD_ATTACKSPEED)
            || spellInfo->HasAura(SPELL_AURA_MOD_STAT))
            score += 1;

        return score;
    }

    std::vector<BoneboundPriestDispelCandidate> CollectBoneboundPriestDispelCandidates(
        std::vector<Unit*> const& supportTargets,
        bool massDispel)
    {
        std::vector<BoneboundPriestDispelCandidate> candidates;
        for (Unit* target : supportTargets)
        {
            if (!target || !target->IsAlive())
                continue;

            for (auto const& [_, auraApplication] : target->GetAppliedAuras())
            {
                if (!auraApplication || auraApplication->IsPositive())
                    continue;

                Aura const* aura = auraApplication->GetBase();
                SpellInfo const* spellInfo = aura ? aura->GetSpellInfo() : nullptr;
                if (!aura || !spellInfo)
                    continue;

                bool singleEligible = spellInfo->Dispel == DISPEL_DISEASE || spellInfo->Dispel == DISPEL_CURSE;
                bool massEligible = singleEligible || spellInfo->Dispel == DISPEL_MAGIC || spellInfo->Dispel == DISPEL_POISON;
                if ((!massDispel && !singleEligible) || (massDispel && !massEligible))
                    continue;

                uint32 severity = ScoreBoneboundPriestDebuff(auraApplication, spellInfo);
                if (severity == 0)
                    continue;

                candidates.push_back({target, spellInfo->Id, aura->GetCasterGUID(), spellInfo->Dispel, severity});
            }
        }

        std::sort(
            candidates.begin(),
            candidates.end(),
            [](BoneboundPriestDispelCandidate const& left, BoneboundPriestDispelCandidate const& right)
            {
                if (left.severity != right.severity)
                    return left.severity > right.severity;
                if (left.dispelType != right.dispelType)
                    return left.dispelType == DISPEL_CURSE || left.dispelType == DISPEL_DISEASE;
                return left.spellId < right.spellId;
            });
        return candidates;
    }

    bool RemoveBoneboundPriestDebuff(BoneboundPriestDispelCandidate const& candidate)
    {
        if (!candidate.target || candidate.spellId == 0)
            return false;

        if (!candidate.target->HasAura(candidate.spellId, candidate.casterGuid))
            return false;

        candidate.target->RemoveAura(candidate.spellId, candidate.casterGuid);
        return true;
    }

    Unit* SelectBoneboundPriestShieldTarget(
        Creature* priestEcho,
        std::vector<Unit*> const& supportTargets,
        WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!priestEcho)
            return nullptr;

        Unit* bestTarget = nullptr;
        uint32 bestScore = 0;
        for (Unit* candidate : supportTargets)
        {
            if (!candidate || !candidate->IsAlive() || candidate->HasAura(config.priestEchoShieldSpellId, priestEcho->GetGUID()))
                continue;

            if (!IsBoneboundPriestTargetUnderThreat(candidate))
                continue;

            uint32 healthPct = std::min<uint32>(100u, static_cast<uint32>(candidate->GetHealthPct()));
            uint32 attackerScore = static_cast<uint32>(std::min<size_t>(candidate->getAttackers().size(), 5u)) * 10u;
            uint32 score = attackerScore + (100u - healthPct);
            if (!bestTarget || score > bestScore)
            {
                bestTarget = candidate;
                bestScore = score;
            }
        }

        return bestTarget;
    }

    bool TryBoneboundPriestSingleDispel(
        Creature* priestEcho,
        std::vector<Unit*> const& supportTargets,
        WmSpells::BoneboundBehaviorConfig const& config,
        uint32& dispelCooldown)
    {
        if (!priestEcho || dispelCooldown != 0)
            return false;

        std::vector<BoneboundPriestDispelCandidate> candidates = CollectBoneboundPriestDispelCandidates(supportTargets, false);
        if (candidates.empty())
            return false;

        BoneboundPriestDispelCandidate const& candidate = candidates.front();
        uint32 spellId = candidate.dispelType == DISPEL_CURSE
            ? config.priestEchoCurseDispelSpellId
            : config.priestEchoDiseaseDispelSpellId;
        if (spellId == 0)
            return false;

        bool castOk = TryCastBoneboundPriestEchoSpell(priestEcho, candidate.target, spellId, 1u);
        if (castOk)
            RemoveBoneboundPriestDebuff(candidate);

        dispelCooldown = castOk ? std::max<uint32>(1000u, config.priestEchoDispelCooldownMs) : 1000u;
        return castOk;
    }

    bool TryBoneboundPriestMassDispel(
        Creature* priestEcho,
        std::vector<Unit*> const& supportTargets,
        WmSpells::BoneboundBehaviorConfig const& config,
        uint32& massDispelCooldown)
    {
        if (!priestEcho || massDispelCooldown != 0 || config.priestEchoMassDispelSpellId == 0)
            return false;

        std::vector<BoneboundPriestDispelCandidate> candidates = CollectBoneboundPriestDispelCandidates(supportTargets, true);
        if (candidates.empty())
            return false;

        uint32 totalSeverity = 0;
        std::vector<Unit*> affectedTargets;
        for (BoneboundPriestDispelCandidate const& candidate : candidates)
        {
            totalSeverity += candidate.severity;
            AddUniqueBoneboundPriestSupportTarget(affectedTargets, candidate.target);
        }

        uint32 minAffected = std::max<uint32>(1u, config.priestEchoMassDispelMinAffected);
        uint32 minSeverity = std::max<uint32>(1u, config.priestEchoMassDispelMinSeverity);
        bool severeSingleTarget = candidates.front().severity >= minSeverity;
        bool enoughTargets = affectedTargets.size() >= minAffected;
        bool enoughSeverity = totalSeverity >= minSeverity;
        if (!severeSingleTarget && !enoughTargets && !enoughSeverity)
            return false;

        Unit* visualTarget = candidates.front().target;
        bool castOk = TryCastBoneboundPriestEchoSpell(priestEcho, visualTarget, config.priestEchoMassDispelSpellId, 1u);
        if (castOk)
        {
            uint32 removals = 0;
            uint32 maxRemovals = std::max<uint32>(1u, config.priestEchoMassDispelMaxRemovals);
            for (BoneboundPriestDispelCandidate const& candidate : candidates)
            {
                if (removals >= maxRemovals)
                    break;
                if (RemoveBoneboundPriestDebuff(candidate))
                    ++removals;
            }
        }

        massDispelCooldown = castOk ? std::max<uint32>(30000u, config.priestEchoMassDispelCooldownMs) : 1000u;
        return castOk;
    }

    void MoveBoneboundPriestEchoToSafePosition(
        Creature* priestEcho,
        Player* owner,
        Unit* enemy,
        BoneboundAlphaEchoState const& state,
        WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!priestEcho || !owner || priestEcho->IsNonMeleeSpellCast(false))
            return;

        priestEcho->AttackStop();
        float followDistance = std::max(1.2f, state.followDistance);
        float minEnemyDistance = std::max(3.0f, config.priestEchoSafeMinEnemyDistance);
        if (enemy && IsBoneboundEchoHuntMode(state.ownerGuid))
        {
            float castRange = ResolveBoneboundPriestVisibleDpsCastRange(priestEcho, config);
            float seekDistance = std::clamp(minEnemyDistance + 6.0f, 8.0f, std::max(8.0f, castRange - 2.0f));
            if (!priestEcho->IsWithinDistInMap(enemy, std::max(5.0f, castRange - 1.0f))
                || !priestEcho->IsWithinLOSInMap(enemy)
                || priestEcho->IsWithinDistInMap(enemy, minEnemyDistance))
            {
                priestEcho->GetMotionMaster()->MoveFollow(enemy, seekDistance, state.followAngle);
                return;
            }

            priestEcho->SetTarget(enemy->GetGUID());
            priestEcho->SetFacingToObject(enemy);
            return;
        }

        if ((enemy && priestEcho->IsWithinDistInMap(enemy, minEnemyDistance))
            || !priestEcho->IsWithinDistInMap(owner, followDistance + 5.0f))
            priestEcho->GetMotionMaster()->MoveFollow(owner, followDistance, state.followAngle);
    }

    void ConsiderBoneboundPriestSupportTarget(
        Creature* priestEcho,
        Unit* candidate,
        float radius,
        uint32 healthThresholdPct,
        uint32 skipAuraSpellId,
        Unit*& bestTarget,
        uint32& bestHealthPct,
        uint32& bestMissingHealth)
    {
        if (!priestEcho || !candidate || !candidate->IsAlive() || candidate->GetMaxHealth() == 0)
            return;

        if (candidate->GetMapId() != priestEcho->GetMapId()
            || !priestEcho->IsWithinDistInMap(candidate, radius)
            || !priestEcho->IsWithinLOSInMap(candidate)
            || !priestEcho->IsFriendlyTo(candidate))
            return;

        if (skipAuraSpellId != 0 && candidate->HasAura(skipAuraSpellId, priestEcho->GetGUID()))
            return;

        uint32 healthPct = std::min<uint32>(100u, static_cast<uint32>(candidate->GetHealthPct()));
        if (healthPct > healthThresholdPct)
            return;

        uint32 missingHealth = candidate->GetMaxHealth() > candidate->GetHealth()
            ? candidate->GetMaxHealth() - candidate->GetHealth()
            : 0u;

        if (!bestTarget || healthPct < bestHealthPct || (healthPct == bestHealthPct && missingHealth > bestMissingHealth))
        {
            bestTarget = candidate;
            bestHealthPct = healthPct;
            bestMissingHealth = missingHealth;
        }
    }

    Unit* SelectBoneboundPriestSupportTarget(
        Creature* priestEcho,
        Player* owner,
        Pet* alphaPet,
        WmSpells::BoneboundBehaviorConfig const& config,
        uint32 healthThresholdPct,
        uint32 skipAuraSpellId)
    {
        if (!priestEcho || !owner)
            return nullptr;

        float radius = std::max(5.0f, config.priestEchoSupportRadius);
        Unit* bestTarget = nullptr;
        uint32 bestHealthPct = 101u;
        uint32 bestMissingHealth = 0u;

        auto consider = [&](Unit* candidate)
        {
            ConsiderBoneboundPriestSupportTarget(
                priestEcho,
                candidate,
                radius,
                std::min<uint32>(100u, std::max<uint32>(1u, healthThresholdPct)),
                skipAuraSpellId,
                bestTarget,
                bestHealthPct,
                bestMissingHealth);
        };

        consider(owner);
        consider(alphaPet);
        for (auto const& [_, state] : gBoneboundAlphaEchoes)
        {
            if (state.ownerGuid != static_cast<uint32>(owner->GetGUID().GetCounter()))
                continue;

            consider(ObjectAccessor::GetCreature(*owner, state.echoGuid));
        }

        if (Group* group = owner->GetGroup())
        {
            for (GroupReference* ref = group->GetFirstMember(); ref; ref = ref->next())
            {
                Player* member = ref->GetSource();
                if (!member || !member->IsAlive() || member->IsGameMaster())
                    continue;

                consider(member);
                consider(member->GetPet());
                consider(member->GetCharm());
            }
        }

        return bestTarget;
    }

    Unit* SelectBoneboundPriestEnemyTarget(Creature* priestEcho, Player* owner, Pet* alphaPet, uint32 ownerGuid, WmSpells::BoneboundBehaviorConfig const& config)
    {
        if (!priestEcho || !owner)
            return nullptr;

        if (IsBoneboundEchoHuntMode(ownerGuid))
        {
            std::optional<WmSpells::BoneboundBehaviorConfig> runtimeConfig = config;
            Unit* sought = SelectNearestBoneboundSeekTarget(owner, priestEcho, ResolveBoneboundEchoHuntRadius(ownerGuid, runtimeConfig));
            if (sought)
                return sought;
        }

        Unit* victim = alphaPet ? alphaPet->GetVictim() : nullptr;
        if (!victim)
            victim = priestEcho->GetVictim();

        return victim && victim->IsAlive() && priestEcho->CanCreatureAttack(victim, true) ? victim : nullptr;
    }

    void CommandBoneboundPriestEchoSeek(Creature* priestEcho, Unit* victim)
    {
        if (!priestEcho || !victim || !victim->IsAlive() || !priestEcho->CanCreatureAttack(victim, true))
            return;

        priestEcho->AttackStop();
        priestEcho->SetTarget(victim->GetGUID());
        priestEcho->SetFacingToObject(victim);
        priestEcho->SetInCombatWith(victim);
        victim->SetInCombatWith(priestEcho);
    }

    void CommandBoneboundAlphaEchoAttack(Creature* echo, Unit* victim);

    void UpdateBoneboundPriestEcho(
        Creature* priestEcho,
        Player* owner,
        Pet* alphaPet,
        BoneboundAlphaEchoState const& state,
        WmSpells::BoneboundBehaviorConfig const& config,
        uint32 diff)
    {
        if (!priestEcho || !owner || !config.priestEchoEnabled)
            return;

        uint32 echoGuid = static_cast<uint32>(priestEcho->GetGUID().GetCounter());
        if (UpdateBoneboundPriestDpsCast(priestEcho, owner, diff))
        {
            MoveBoneboundPriestEchoToSafePosition(priestEcho, owner, nullptr, state, config);
            return;
        }

        std::vector<Unit*> supportTargets = CollectBoneboundPriestSupportTargets(priestEcho, owner, alphaPet, config);
        Unit* hurtTarget = SelectBoneboundPriestSupportTarget(
            priestEcho,
            owner,
            alphaPet,
            config,
            config.priestEchoHealBelowHealthPct,
            0);

        bool supportCast = false;
        uint32& massDispelCooldown = gBoneboundPriestMassDispelCooldownByCaster[echoGuid];
        supportCast = TryBoneboundPriestMassDispel(priestEcho, supportTargets, config, massDispelCooldown);

        uint32& dispelCooldown = gBoneboundPriestDispelCooldownByCaster[echoGuid];
        if (!supportCast)
            supportCast = TryBoneboundPriestSingleDispel(priestEcho, supportTargets, config, dispelCooldown);

        uint32& healCooldown = gBoneboundPriestHealCooldownByCaster[echoGuid];
        if (!supportCast && hurtTarget && healCooldown == 0 && config.priestEchoHealSpellId != 0)
        {
            uint32 healAmount = AddBoneboundPriestSpellPowerBonus(
                ResolvePercentOfMaxHealth(hurtTarget, config.priestEchoHealBasePct),
                owner,
                config.priestEchoSpellPowerToHealingPct);
            bool castOk = TryCastBoneboundPriestEchoSpell(priestEcho, hurtTarget, config.priestEchoHealSpellId, healAmount);
            healCooldown = castOk ? std::max<uint32>(500u, config.priestEchoHealCooldownMs) : 1000u;
            supportCast = castOk;
        }

        uint32& renewCooldown = gBoneboundPriestRenewCooldownByCaster[echoGuid];
        if (!supportCast && hurtTarget && renewCooldown == 0 && config.priestEchoRenewSpellId != 0 && !hurtTarget->HasAura(config.priestEchoRenewSpellId, priestEcho->GetGUID()))
        {
            uint32 renewAmount = AddBoneboundPriestSpellPowerBonus(
                ResolvePercentOfMaxHealth(hurtTarget, config.priestEchoRenewBasePct),
                owner,
                config.priestEchoSpellPowerToHealingPct);
            bool castOk = TryCastBoneboundPriestEchoSpell(priestEcho, hurtTarget, config.priestEchoRenewSpellId, renewAmount);
            renewCooldown = castOk ? std::max<uint32>(1000u, config.priestEchoRenewCooldownMs) : 1000u;
            supportCast = castOk;
        }

        uint32& shieldCooldown = gBoneboundPriestShieldCooldownByCaster[echoGuid];
        if (!supportCast && shieldCooldown == 0 && config.priestEchoShieldSpellId != 0)
        {
            Unit* shieldTarget = SelectBoneboundPriestShieldTarget(priestEcho, supportTargets, config);
            if (shieldTarget)
            {
                uint32 shieldAmount = AddBoneboundPriestSpellPowerBonus(
                    ResolvePercentOfMaxHealth(shieldTarget, config.priestEchoShieldBasePct),
                    owner,
                    config.priestEchoSpellPowerToShieldPct);
                bool castOk = TryCastBoneboundPriestEchoSpell(priestEcho, shieldTarget, config.priestEchoShieldSpellId, shieldAmount);
                shieldCooldown = castOk ? std::max<uint32>(1000u, config.priestEchoShieldCooldownMs) : 1000u;
                supportCast = castOk;
            }
        }

        uint32& dpsCooldown = gBoneboundPriestDpsCooldownByCaster[echoGuid];
        Unit* enemy = SelectBoneboundPriestEnemyTarget(priestEcho, owner, alphaPet, state.ownerGuid, config);
        if (enemy && IsBoneboundEchoHuntMode(state.ownerGuid))
            CommandBoneboundPriestEchoSeek(priestEcho, enemy);
        if (!supportCast && dpsCooldown == 0 && !priestEcho->IsNonMeleeSpellCast(false) && config.priestEchoDpsSpellId != 0)
        {
            if (enemy)
            {
                uint32 alphaRoll = ResolveAlphaMeleeDamageRoll(alphaPet, owner, config);
                uint32 baseDamage = std::max<uint32>(1u, (alphaRoll * std::max<uint32>(1u, config.priestEchoDpsDamagePct)) / 100u);
                uint32 damage = AddBoneboundPriestSpellPowerBonus(baseDamage, owner, config.priestEchoSpellPowerToDamagePct);
                bool castOk = TryStartBoneboundPriestDpsCast(priestEcho, enemy, owner, config, damage);
                dpsCooldown = castOk ? std::max<uint32>(500u, config.priestEchoDpsCooldownMs) : 1000u;
            }
        }

        MoveBoneboundPriestEchoToSafePosition(priestEcho, owner, enemy, state, config);
    }

    void ApplyBoneboundAlphaEchoRuntime(Player* owner, Pet* alphaPet, TempSummon* echo, BoneboundAlphaEchoState const& state, WmSpells::BoneboundBehaviorConfig const& config, bool refillHealth)
    {
        if (!owner || !alphaPet || !echo)
            return;

        bool priestEcho = IsBoneboundPriestEcho(state);
        std::string const& name = priestEcho ? config.priestEchoName : config.alphaEchoName;
        uint32 displayId = priestEcho && config.priestEchoDisplayId != 0 ? config.priestEchoDisplayId : config.displayId;
        uint32 virtualItem1 = priestEcho ? state.virtualItem1 : config.virtualItem1;
        uint32 virtualItem2 = priestEcho ? state.virtualItem2 : config.virtualItem2;
        uint32 virtualItem3 = priestEcho ? state.virtualItem3 : config.virtualItem3;
        float scale = alphaPet->GetObjectScale();
        if (priestEcho)
            scale = std::clamp(scale * std::max(0.1f, config.priestEchoScaleMultiplier), 0.1f, 5.0f);

        echo->SetCreatorGUID(owner->GetGUID());
        echo->SetOwnerGUID(owner->GetGUID());
        echo->SetFaction(owner->GetFaction());
        echo->SetLevel(alphaPet->GetLevel());
        echo->SetUInt32Value(UNIT_CREATED_BY_SPELL, config.shellSpellId);
        ApplyBoneboundCreatureAppearance(
            echo,
            name,
            displayId,
            virtualItem1,
            virtualItem2,
            virtualItem3,
            scale);
        // Creature stat recalculation restores template fields; copy Alpha values after it.
        ApplyOwnerTransferBonuses(echo, owner, config, false);
        CopyAlphaFinalStatsToEcho(alphaPet, echo, refillHealth);
        MatchBoneboundEchoMovementSpeed(alphaPet, echo);
        echo->SetReactState(priestEcho ? REACT_PASSIVE : REACT_DEFENSIVE);
    }

    void CommandBoneboundAlphaEchoAttack(Creature* echo, Unit* victim)
    {
        if (!echo || !victim || !victim->IsAlive() || !echo->CanCreatureAttack(victim, true))
            return;

        echo->AddThreat(victim, 25.0f);
        echo->SetInCombatWith(victim);
        victim->SetInCombatWith(echo);

        if (echo->AI())
            echo->AI()->AttackStart(victim);

        if (echo->GetVictim() != victim)
            echo->Attack(victim, true);

        if (!echo->IsWithinMeleeRange(victim))
            echo->GetMotionMaster()->MoveChase(victim);
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

        ApplyBoneboundAlphaEchoRuntime(owner, alphaPet, echo, state, config, true);
        if (!IsBoneboundPriestEcho(state) && victim && victim->IsAlive())
            CommandBoneboundAlphaEchoAttack(echo, victim);
        else
            echo->GetMotionMaster()->MoveFollow(owner, state.followDistance, state.followAngle);

        state.echoGuid = echo->GetGUID();
        state.creatureEntry = echoEntry;
        return echo;
    }

    bool TrySpawnBoneboundAlphaEcho(
        Player* owner,
        Pet* alphaPet,
        Unit* victim,
        WmSpells::BoneboundBehaviorConfig const& config,
        BoneboundEchoRole requestedRole = BoneboundEchoRole::Warrior)
    {
        if (!owner || !alphaPet || !victim || !victim->IsAlive() || !config.alphaEchoEnabled)
            return false;

        bool priestEcho = requestedRole == BoneboundEchoRole::Priest;
        if (priestEcho && (!config.priestEchoEnabled || config.priestEchoCreatureEntry == 0))
            return false;

        uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
        uint32 activeRoleCount = priestEcho
            ? CountActiveBoneboundPriestEchoes(ownerGuid)
            : CountActiveBoneboundWarriorEchoes(ownerGuid);
        uint32 activeRoleCap = priestEcho
            ? std::max<uint32>(1u, config.priestEchoMaxActive)
            : std::max<uint32>(1u, config.alphaEchoMaxActive);
        if (activeRoleCount >= activeRoleCap)
            return false;

        BoneboundAlphaEchoState state = BuildBoneboundAlphaEchoState(owner, config, requestedRole);

        TempSummon* echo = SpawnBoneboundAlphaEchoFromState(owner, alphaPet, victim, state, config);
        if (!echo)
            return false;

        gBoneboundAlphaEchoes[static_cast<uint32>(echo->GetGUID().GetCounter())] = state;
        RefreshBoneboundEchoFormationSlots(owner, config);
        RefreshBoneboundEchoCountAura(owner, config);
        return true;
    }

    bool SpawnStoredBoneboundAlphaEcho(
        Player* owner,
        Pet* alphaPet,
        WmSpells::BoneboundBehaviorConfig const& config,
        BoneboundEchoRole requestedRole)
    {
        if (!owner || !alphaPet || !config.alphaEchoEnabled)
            return false;

        bool priestEcho = requestedRole == BoneboundEchoRole::Priest;
        if (priestEcho && (!config.priestEchoEnabled || config.priestEchoCreatureEntry == 0))
            return false;

        BoneboundAlphaEchoState state = BuildBoneboundAlphaEchoState(owner, config, requestedRole);
        TempSummon* echo = SpawnBoneboundAlphaEchoFromState(owner, alphaPet, nullptr, state, config);
        if (!echo)
            return false;

        gBoneboundAlphaEchoes[static_cast<uint32>(echo->GetGUID().GetCounter())] = state;
        RefreshBoneboundEchoFormationSlots(owner, config);
        return true;
    }

    void MaintainBoneboundAlphaAbilities(Player* owner, Pet* alphaPet, WmSpells::BoneboundBehaviorConfig const& config, uint32 /*diff*/)
    {
        if (!owner || !alphaPet)
            return;

        uint32 petGuid = static_cast<uint32>(alphaPet->GetGUID().GetCounter());
        if (!config.bleedEnabled)
        {
            gBoneboundBleedCooldownByCaster.erase(petGuid);
            return;
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
            gBoneboundBleedCooldownByCaster.erase(it->first);
            gBoneboundCleaveCooldownByCaster.erase(it->first);
            gBoneboundPriestHealCooldownByCaster.erase(it->first);
            gBoneboundPriestRenewCooldownByCaster.erase(it->first);
            gBoneboundPriestShieldCooldownByCaster.erase(it->first);
            gBoneboundPriestDpsCooldownByCaster.erase(it->first);
            gBoneboundPriestDpsCastByCaster.erase(it->first);
            gBoneboundPriestDispelCooldownByCaster.erase(it->first);
            gBoneboundPriestMassDispelCooldownByCaster.erase(it->first);
            it = gBoneboundAlphaEchoes.erase(it);
        }

        gBoneboundEchoHuntModeByPlayer.erase(ownerGuid);
        gBoneboundEchoHuntRadiusByPlayer.erase(ownerGuid);
        gBoneboundWarriorEchoesSincePriestByPlayer.erase(ownerGuid);
        ClearBoneboundEchoCountAura(owner);

        gBoneboundBleeds.erase(
            std::remove_if(
                gBoneboundBleeds.begin(),
                gBoneboundBleeds.end(),
                [ownerGuid](BoneboundBleedState const& bleed) { return bleed.ownerGuid == ownerGuid; }),
            gBoneboundBleeds.end());
    }

    void UpdateBoneboundBleeds(uint32 diff)
    {
        for (auto it = gBoneboundBleeds.begin(); it != gBoneboundBleeds.end();)
        {
            Player* owner = ObjectAccessor::FindPlayerByLowGUID(it->ownerGuid);
            if (!owner)
            {
                it = gBoneboundBleeds.erase(it);
                continue;
            }

            Unit* caster = ObjectAccessor::GetUnit(*owner, it->casterGuid);
            Unit* target = ObjectAccessor::GetUnit(*owner, it->targetGuid);
            if (!caster || !target || !target->IsAlive() || !HasBoneboundBleedVisibleAura(caster, target))
            {
                it = gBoneboundBleeds.erase(it);
                continue;
            }

            if (it->tickTimerMs > diff)
            {
                it->tickTimerMs -= diff;
            }
            else
            {
                SeedBoneboundOwnerKillCredit(owner, target, it->tickDamage);
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
                it = gBoneboundBleeds.erase(it);
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
                gBoneboundBleedCooldownByCaster.erase(it->first);
                gBoneboundCleaveCooldownByCaster.erase(it->first);
                gBoneboundPriestHealCooldownByCaster.erase(it->first);
                gBoneboundPriestRenewCooldownByCaster.erase(it->first);
                gBoneboundPriestShieldCooldownByCaster.erase(it->first);
                gBoneboundPriestDpsCooldownByCaster.erase(it->first);
                gBoneboundPriestDpsCastByCaster.erase(it->first);
                gBoneboundPriestDispelCooldownByCaster.erase(it->first);
                gBoneboundPriestMassDispelCooldownByCaster.erase(it->first);
                it = gBoneboundAlphaEchoes.erase(it);
                continue;
            }

            if (it->second.remainingMs <= diff)
            {
                if (Creature* echo = ObjectAccessor::GetCreature(*owner, it->second.echoGuid))
                    echo->DespawnOrUnsummon();
                gBoneboundBleedCooldownByCaster.erase(it->first);
                gBoneboundCleaveCooldownByCaster.erase(it->first);
                gBoneboundPriestHealCooldownByCaster.erase(it->first);
                gBoneboundPriestRenewCooldownByCaster.erase(it->first);
                gBoneboundPriestShieldCooldownByCaster.erase(it->first);
                gBoneboundPriestDpsCooldownByCaster.erase(it->first);
                gBoneboundPriestDpsCastByCaster.erase(it->first);
                gBoneboundPriestDispelCooldownByCaster.erase(it->first);
                gBoneboundPriestMassDispelCooldownByCaster.erase(it->first);
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
                    gBoneboundBleedCooldownByCaster.erase(it->first);
                    gBoneboundCleaveCooldownByCaster.erase(it->first);
                    gBoneboundPriestHealCooldownByCaster.erase(it->first);
                    gBoneboundPriestRenewCooldownByCaster.erase(it->first);
                    gBoneboundPriestShieldCooldownByCaster.erase(it->first);
                    gBoneboundPriestDpsCooldownByCaster.erase(it->first);
                    gBoneboundPriestDpsCastByCaster.erase(it->first);
                    gBoneboundPriestDispelCooldownByCaster.erase(it->first);
                    gBoneboundPriestMassDispelCooldownByCaster.erase(it->first);
                    it = gBoneboundAlphaEchoes.erase(it);
                    continue;
                }

                std::optional<WmSpells::BoneboundBehaviorConfig> runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
                if (!runtimeConfig.has_value() || !runtimeConfig->alphaEchoEnabled)
                {
                    gBoneboundBleedCooldownByCaster.erase(it->first);
                    gBoneboundCleaveCooldownByCaster.erase(it->first);
                    gBoneboundPriestHealCooldownByCaster.erase(it->first);
                    gBoneboundPriestRenewCooldownByCaster.erase(it->first);
                    gBoneboundPriestShieldCooldownByCaster.erase(it->first);
                    gBoneboundPriestDpsCooldownByCaster.erase(it->first);
                    gBoneboundPriestDpsCastByCaster.erase(it->first);
                    gBoneboundPriestDispelCooldownByCaster.erase(it->first);
                    gBoneboundPriestMassDispelCooldownByCaster.erase(it->first);
                    it = gBoneboundAlphaEchoes.erase(it);
                    continue;
                }

                Unit* victim = alphaPet->GetVictim();
                BoneboundAlphaEchoState state = it->second;
                TempSummon* restored = SpawnBoneboundAlphaEchoFromState(owner, alphaPet, victim, state, *runtimeConfig);
                if (!restored)
                {
                    gBoneboundBleedCooldownByCaster.erase(it->first);
                    gBoneboundCleaveCooldownByCaster.erase(it->first);
                    gBoneboundPriestHealCooldownByCaster.erase(it->first);
                    gBoneboundPriestRenewCooldownByCaster.erase(it->first);
                    gBoneboundPriestShieldCooldownByCaster.erase(it->first);
                    gBoneboundPriestDpsCooldownByCaster.erase(it->first);
                    gBoneboundPriestDpsCastByCaster.erase(it->first);
                    gBoneboundPriestDispelCooldownByCaster.erase(it->first);
                    gBoneboundPriestMassDispelCooldownByCaster.erase(it->first);
                    it = gBoneboundAlphaEchoes.erase(it);
                    continue;
                }

                gBoneboundBleedCooldownByCaster.erase(it->first);
                gBoneboundCleaveCooldownByCaster.erase(it->first);
                gBoneboundPriestHealCooldownByCaster.erase(it->first);
                gBoneboundPriestRenewCooldownByCaster.erase(it->first);
                gBoneboundPriestShieldCooldownByCaster.erase(it->first);
                gBoneboundPriestDpsCooldownByCaster.erase(it->first);
                gBoneboundPriestDpsCastByCaster.erase(it->first);
                gBoneboundPriestDispelCooldownByCaster.erase(it->first);
                gBoneboundPriestMassDispelCooldownByCaster.erase(it->first);
                it = gBoneboundAlphaEchoes.erase(it);
                gBoneboundAlphaEchoes[static_cast<uint32>(restored->GetGUID().GetCounter())] = state;
                RefreshBoneboundEchoFormationSlots(owner, *runtimeConfig);
                continue;
            }

            Pet* alphaPet = owner->GetPet();
            if (alphaPet && IsBoneboundPet(alphaPet))
            {
                std::optional<WmSpells::BoneboundBehaviorConfig> runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
                if (runtimeConfig.has_value() && runtimeConfig->alphaEchoEnabled)
                {
                    ApplyBoneboundAlphaEchoRuntime(owner, alphaPet, echo->ToTempSummon(), it->second, *runtimeConfig, false);
                    if (IsBoneboundPriestEcho(it->second))
                        UpdateBoneboundPriestEcho(echo, owner, alphaPet, it->second, *runtimeConfig, diff);
                }

                if (IsBoneboundPriestEcho(it->second))
                {
                    ++it;
                    continue;
                }

                Unit* victim = nullptr;
                if (IsBoneboundEchoHuntMode(it->second.ownerGuid))
                {
                    float huntRadius = ResolveBoneboundEchoHuntRadius(it->second.ownerGuid, runtimeConfig);
                    victim = SelectNearestBoneboundSeekTarget(owner, echo, huntRadius);
                }
                if (!victim)
                    victim = alphaPet->GetVictim();

                if (victim && victim->IsAlive())
                    CommandBoneboundAlphaEchoAttack(echo, victim);
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

    BoneboundEchoStasisCounts LoadStoredBoneboundEchoStasis(uint32 ownerGuid)
    {
        QueryResult result = WorldDatabase.Query(
            "SELECT DestroyerCount, RestorerCount FROM wm_bonebound_echo_stasis WHERE PlayerGUID = {} LIMIT 1",
            ownerGuid);
        if (!result)
            return {};

        Field* fields = result->Fetch();
        return {
            fields[0].Get<uint32>(),
            fields[1].Get<uint32>(),
        };
    }

    bool HasStoredBoneboundEchoStasis(uint32 ownerGuid)
    {
        return LoadStoredBoneboundEchoStasis(ownerGuid).Total() > 0;
    }

    void StoreBoneboundEchoStasis(uint32 ownerGuid, BoneboundEchoStasisCounts const& counts)
    {
        WorldDatabase.Execute(
            "INSERT INTO wm_bonebound_echo_stasis "
            "(PlayerGUID, DestroyerCount, RestorerCount, StoredAt, UpdatedAt) VALUES "
            "({}, {}, {}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
            "ON DUPLICATE KEY UPDATE "
            "DestroyerCount = VALUES(DestroyerCount), RestorerCount = VALUES(RestorerCount), UpdatedAt = CURRENT_TIMESTAMP",
            ownerGuid,
            counts.destroyers,
            counts.restorers);
    }

    void ClearBoneboundEchoStasis(uint32 ownerGuid)
    {
        WorldDatabase.Execute(
            "DELETE FROM wm_bonebound_echo_stasis WHERE PlayerGUID = {}",
            ownerGuid);
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

    bool IsNightWatchersLensWandShot(SpellInfo const* spellInfo)
    {
        return spellInfo
            && spellInfo->EquippedItemClass == ITEM_CLASS_WEAPON
            && (spellInfo->EquippedItemSubClassMask & (1 << ITEM_SUBCLASS_WEAPON_WAND)) != 0
            && spellInfo->HasAttribute(SPELL_ATTR2_AUTO_REPEAT);
    }

    bool TryProcNightWatchersLensMark(Unit* attacker, Unit* victim, uint32 damage)
    {
        if (!attacker || !victim || damage == 0 || attacker == victim)
            return false;

        Player* player = attacker->ToPlayer();
        if (!HasNightWatchersLensReady(player))
            return false;

        if (!roll_chance_f(NIGHT_WATCHERS_LENS_PROC_CHANCE_PCT))
            return false;

        return RefreshNightWatchersLensMark(player, victim);
    }

    int32 HalveNightWatchersLensDefenseValue(int32 value)
    {
        return std::max<int32>(0, value / 2);
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
        gConfig.boneboundCreatureEntry = sConfigMgr->GetOption<uint32>("WmSpells.BoneboundServant.CreatureEntry", 920100u);
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
        return IsBoneboundBehaviorKind(behaviorKind)
            || IsIntellectBlockBehaviorKind(behaviorKind)
            || IsBoneboundEchoModeBehaviorKind(behaviorKind)
            || IsBoneboundEchoStasisBehaviorKind(behaviorKind);
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

    SpellCastResult CheckShellCast(Player* player, uint32 shellSpellId)
    {
        if (!player)
            return SPELL_FAILED_CASTER_DEAD;

        if (!IsPlayerAllowed(player) || !gConfig.boneboundServantEnabled)
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        if (IsBoneboundEchoStasisBehaviorKind(behaviorRecord->behaviorKind))
        {
            std::optional<BoneboundEchoStasisConfig> stasisConfig = BuildBoneboundEchoStasisConfig(*behaviorRecord);
            if (!stasisConfig.has_value())
                return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

            if (stasisConfig->soulShardItemId != 0 && stasisConfig->soulShardCount > 0
                && !player->HasItemCount(stasisConfig->soulShardItemId, stasisConfig->soulShardCount, false))
                return SPELL_FAILED_REAGENTS;

            uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
            if (CountActiveBoneboundAlphaEchoes(ownerGuid) > 0)
                return SPELL_CAST_OK;

            if (!HasStoredBoneboundEchoStasis(ownerGuid))
                return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

            Pet* alphaPet = player->GetPet();
            if (!alphaPet || !IsBoneboundPet(alphaPet))
                return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

            std::optional<BoneboundBehaviorConfig> runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
            return runtimeConfig.has_value() && runtimeConfig->alphaEchoEnabled
                ? SPELL_CAST_OK
                : SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;
        }

        if (IsIntellectBlockBehaviorKind(behaviorRecord->behaviorKind))
            return SPELL_CAST_OK;

        std::optional<BoneboundBehaviorConfig> runtimeConfig = BuildBoneboundBehaviorConfig(*behaviorRecord, true);
        if (!runtimeConfig.has_value())
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        if (!runtimeConfig->requireCorpse)
            return SPELL_CAST_OK;

        return GetCorpseTarget(player) ? SPELL_CAST_OK : SPELL_FAILED_BAD_TARGETS;
    }

    SpellCastResult CheckBoneboundCorpseTarget(Player* player, uint32 shellSpellId)
    {
        return CheckShellCast(player, shellSpellId);
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

    BehaviorExecutionResult ExecuteBoneboundEchoStasis(Player* player, uint32 shellSpellId)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return {false, "shell_behavior_missing"};
        std::optional<BoneboundEchoStasisConfig> stasisConfig = BuildBoneboundEchoStasisConfig(*behaviorRecord);
        if (!stasisConfig.has_value())
            return {false, "echo_stasis_disabled"};

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        BoneboundEchoStasisCounts activeCounts = CountActiveBoneboundEchoesByRole(ownerGuid);
        if (activeCounts.Total() > 0)
        {
            BoneboundEchoStasisCounts storedBefore = LoadStoredBoneboundEchoStasis(ownerGuid);
            BoneboundEchoStasisCounts storedAfter = AddBoneboundEchoStasisCounts(storedBefore, activeCounts);
            StoreBoneboundEchoStasis(ownerGuid, storedAfter);
            RemoveBoneboundAlphaEchoes(player);
            return {
                true,
                "bonebound_echoes_stored:destroyers="
                    + std::to_string(activeCounts.destroyers)
                    + ":restorers="
                    + std::to_string(activeCounts.restorers)
                    + ":pool_destroyers="
                    + std::to_string(storedAfter.destroyers)
                    + ":pool_restorers="
                    + std::to_string(storedAfter.restorers),
            };
        }

        BoneboundEchoStasisCounts storedCounts = LoadStoredBoneboundEchoStasis(ownerGuid);
        if (storedCounts.Total() == 0)
            return {false, "echo_stasis_empty"};

        Pet* alphaPet = player->GetPet();
        if (!alphaPet || !IsBoneboundPet(alphaPet))
            return {false, "bonebound_alpha_required"};

        std::optional<BoneboundBehaviorConfig> runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
        if (!runtimeConfig.has_value() || !runtimeConfig->alphaEchoEnabled)
            return {false, "alpha_echo_disabled"};

        BoneboundEchoStasisCounts restoredCounts;
        uint32 destroyerLimit = std::min<uint32>(storedCounts.destroyers, std::max<uint32>(1u, runtimeConfig->alphaEchoMaxActive));
        uint32 restorerLimit = runtimeConfig->priestEchoEnabled && runtimeConfig->priestEchoCreatureEntry != 0
            ? std::min<uint32>(storedCounts.restorers, std::max<uint32>(1u, runtimeConfig->priestEchoMaxActive))
            : 0u;

        for (uint32 index = 0; index < destroyerLimit; ++index)
        {
            if (SpawnStoredBoneboundAlphaEcho(player, alphaPet, *runtimeConfig, BoneboundEchoRole::Warrior))
                ++restoredCounts.destroyers;
        }

        for (uint32 index = 0; index < restorerLimit; ++index)
        {
            if (SpawnStoredBoneboundAlphaEcho(player, alphaPet, *runtimeConfig, BoneboundEchoRole::Priest))
                ++restoredCounts.restorers;
        }

        if (restoredCounts.Total() == 0)
            return {false, "echo_stasis_restore_failed"};

        BoneboundEchoStasisCounts remainingCounts = SubtractBoneboundEchoStasisCounts(storedCounts, restoredCounts);
        if (remainingCounts.Total() > 0)
            StoreBoneboundEchoStasis(ownerGuid, remainingCounts);
        else
            ClearBoneboundEchoStasis(ownerGuid);
        RefreshBoneboundEchoCountAura(player, *runtimeConfig);
        return {
            true,
            "bonebound_echoes_restored:destroyers="
                + std::to_string(restoredCounts.destroyers)
                + ":restorers="
                + std::to_string(restoredCounts.restorers)
                + ":pool_destroyers="
                + std::to_string(remainingCounts.destroyers)
                + ":pool_restorers="
                + std::to_string(remainingCounts.restorers),
        };
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

        if (IsBoneboundEchoStasisBehaviorKind(behaviorRecord->behaviorKind))
            return ExecuteBoneboundEchoStasis(player, shellSpellId);

        std::optional<BoneboundBehaviorConfig> runtimeConfig = BuildBoneboundBehaviorConfig(*behaviorRecord, persistPetFallback);
        if (!runtimeConfig.has_value())
            return {false, "shell_behavior_disabled"};

        if (IsBoneboundBehaviorKind(behaviorRecord->behaviorKind))
            return ExecuteBoneboundServant(player, shellSpellId, runtimeConfig->persistPet);

        return {false, "unsupported_shell_spell"};
    }

    BehaviorExecutionResult ExecuteBoneboundEchoSeekRange(Player* player, float huntRadius)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};
        if (!std::isfinite(huntRadius) || huntRadius <= 0.0f)
            return {false, "invalid_echo_hunt_radius"};

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        float clampedRadius = ClampBoneboundEchoHuntRadius(huntRadius);
        gBoneboundEchoHuntRadiusByPlayer[ownerGuid] = clampedRadius;
        return {true, clampedRadius >= 99.95f ? "bonebound_echo_range_set:100" : "bonebound_echo_range_set"};
    }

    BehaviorExecutionResult ExecuteBoneboundEchoTeleport(Player* player)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        Pet* alphaPet = player->GetPet();
        std::optional<BoneboundBehaviorConfig> runtimeConfig;
        if (alphaPet && IsBoneboundPet(alphaPet))
            runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
        if (runtimeConfig.has_value())
            RefreshBoneboundEchoFormationSlots(player, *runtimeConfig);

        uint32 teleported = 0;
        for (auto const& [echoGuid, state] : gBoneboundAlphaEchoes)
        {
            if (state.ownerGuid != ownerGuid)
                continue;

            Creature* echo = ObjectAccessor::GetCreature(*player, state.echoGuid);
            if (!echo || !echo->IsAlive() || echo->GetMapId() != player->GetMapId())
                continue;

            float x = player->GetPositionX();
            float y = player->GetPositionY();
            float z = player->GetPositionZ();
            player->GetClosePoint(
                x,
                y,
                z,
                echo->GetCombatReach(),
                std::max(1.2f, state.followDistance),
                state.followAngle);

            echo->NearTeleportTo(x, y, z, player->GetOrientation());
            echo->CombatStop(true);
            gBoneboundPriestDpsCastByCaster.erase(echoGuid);

            if (IsBoneboundPriestEcho(state) && runtimeConfig.has_value())
                MoveBoneboundPriestEchoToSafePosition(echo, player, nullptr, state, *runtimeConfig);
            else
                echo->GetMotionMaster()->MoveFollow(player, state.followDistance, state.followAngle);

            ++teleported;
        }

        return {true, "bonebound_echo_teleported:" + std::to_string(teleported)};
    }

    BehaviorExecutionResult ExecuteBoneboundEchoMode(Player* player, std::string const& mode, std::optional<float> huntRadiusOverride)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        std::string normalized = mode;
        std::transform(
            normalized.begin(),
            normalized.end(),
            normalized.begin(),
            [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });

        if (normalized == "teleport" || normalized == "tp" || normalized == "recall")
            return ExecuteBoneboundEchoTeleport(player);

        bool huntMode = false;
        if (normalized == "hunt" || normalized == "seek" || normalized == "attack" || normalized == "aggressive")
        {
            huntMode = true;
        }
        else if (normalized == "follow" || normalized == "close" || normalized == "guard" || normalized == "passive")
        {
            huntMode = false;
        }
        else
        {
            return {false, "invalid_echo_mode"};
        }

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        if (huntRadiusOverride.has_value())
        {
            BehaviorExecutionResult rangeResult = ExecuteBoneboundEchoSeekRange(player, *huntRadiusOverride);
            if (!rangeResult.ok)
                return rangeResult;
        }
        gBoneboundEchoHuntModeByPlayer[ownerGuid] = huntMode;

        Pet* alphaPet = player->GetPet();
        std::optional<BoneboundBehaviorConfig> runtimeConfig;
        if (alphaPet && IsBoneboundPet(alphaPet))
            runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);
        if (runtimeConfig.has_value())
            RefreshBoneboundEchoFormationSlots(player, *runtimeConfig);

        for (auto const& [_, state] : gBoneboundAlphaEchoes)
        {
            if (state.ownerGuid != ownerGuid)
                continue;

            Creature* echo = ObjectAccessor::GetCreature(*player, state.echoGuid);
            if (!echo || !echo->IsAlive())
                continue;

            if (IsBoneboundPriestEcho(state))
            {
                Unit* enemy = nullptr;
                if (huntMode)
                {
                    float huntRadius = ResolveBoneboundEchoHuntRadius(ownerGuid, runtimeConfig);
                    enemy = SelectNearestBoneboundSeekTarget(player, echo, huntRadius);
                    if (enemy)
                        CommandBoneboundPriestEchoSeek(echo, enemy);
                }
                else if (alphaPet)
                {
                    enemy = alphaPet->GetVictim();
                }

                if (runtimeConfig.has_value())
                    MoveBoneboundPriestEchoToSafePosition(echo, player, enemy, state, *runtimeConfig);
                else
                    echo->GetMotionMaster()->MoveFollow(player, state.followDistance, state.followAngle);
                continue;
            }

            if (huntMode)
            {
                float huntRadius = ResolveBoneboundEchoHuntRadius(ownerGuid, runtimeConfig);
                if (Unit* target = SelectNearestBoneboundSeekTarget(player, echo, huntRadius))
                    CommandBoneboundAlphaEchoAttack(echo, target);
                continue;
            }

            if (alphaPet && alphaPet->GetVictim())
                CommandBoneboundAlphaEchoAttack(echo, alphaPet->GetVictim());
            else
            {
                echo->CombatStop(true);
                echo->GetMotionMaster()->MoveFollow(player, state.followDistance, state.followAngle);
            }
        }

        return {true, huntMode ? "bonebound_echo_mode_hunt" : "bonebound_echo_mode_follow"};
    }

    void UpdateTrackedCompanions(uint32 diff)
    {
        UpdateBoneboundBleedCooldowns(diff);
        UpdateBoneboundCleaveCooldowns(diff);
        UpdateBoneboundPriestEchoCooldowns(diff);
        UpdateBoneboundBleeds(diff);
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
        RefreshBoneboundEchoCountAura(owner, *runtimeConfig);

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
            if (!runtimeConfig.has_value())
                return;

            uint32 ownerGuid = static_cast<uint32>(owner->GetGUID().GetCounter());
            SeedBoneboundOwnerKillCredit(owner, victim, damage);
            uint32 petGuid = static_cast<uint32>(alphaPet->GetGUID().GetCounter());
            uint32& bleedCooldown = gBoneboundBleedCooldownByCaster[petGuid];
            if (runtimeConfig->bleedEnabled && bleedCooldown == 0)
            {
                StartBoneboundBleed(owner, alphaPet, victim, *runtimeConfig, 100u);
                bleedCooldown = std::max<uint32>(1000u, runtimeConfig->bleedCooldownMs);
            }
            TryBoneboundCleave(owner, alphaPet, victim, *runtimeConfig, damage, runtimeConfig->alphaCleaveDamagePct);

            if (!runtimeConfig->alphaEchoEnabled)
                return;

            bool lensMarked = IsNightWatchersLensMarked(victim);
            float procChance = std::clamp(runtimeConfig->alphaEchoProcChancePct, 0.0f, 100.0f);
            if (lensMarked)
                procChance = std::clamp(procChance * NIGHT_WATCHERS_LENS_MARK_PROC_MULTIPLIER, 0.0f, 100.0f);
            bool warriorEchoSpawned = false;
            if (procChance > 0.0f && roll_chance_f(procChance))
                warriorEchoSpawned = TrySpawnBoneboundAlphaEcho(owner, alphaPet, victim, *runtimeConfig);

            float priestProcChance = runtimeConfig->priestEchoEnabled
                ? std::clamp(runtimeConfig->priestEchoProcChancePct, 0.0f, 100.0f)
                : 0.0f;
            if (lensMarked)
                priestProcChance = std::clamp(priestProcChance * NIGHT_WATCHERS_LENS_MARK_PROC_MULTIPLIER, 0.0f, 100.0f);
            uint32 priestPityThreshold = std::max<uint32>(1u, runtimeConfig->priestEchoPityAfterWarriorSpawns);
            uint32 warriorSpawnsSincePriest = 0;
            auto pityIt = gBoneboundWarriorEchoesSincePriestByPlayer.find(ownerGuid);
            if (pityIt != gBoneboundWarriorEchoesSincePriestByPlayer.end())
                warriorSpawnsSincePriest = pityIt->second;

            bool priestPityReady = runtimeConfig->priestEchoEnabled
                && runtimeConfig->priestEchoCreatureEntry != 0
                && runtimeConfig->priestEchoPityAfterWarriorSpawns > 0
                && (warriorSpawnsSincePriest >= priestPityThreshold
                    || (warriorEchoSpawned && warriorSpawnsSincePriest + 1 >= priestPityThreshold));
            bool priestEchoSpawned = false;
            if ((priestProcChance > 0.0f && roll_chance_f(priestProcChance)) || priestPityReady)
                priestEchoSpawned = TrySpawnBoneboundAlphaEcho(owner, alphaPet, victim, *runtimeConfig, BoneboundEchoRole::Priest);

            if (priestEchoSpawned)
            {
                gBoneboundWarriorEchoesSincePriestByPlayer.erase(ownerGuid);
            }
            else if (warriorEchoSpawned && runtimeConfig->priestEchoEnabled && runtimeConfig->priestEchoCreatureEntry != 0 && runtimeConfig->priestEchoPityAfterWarriorSpawns > 0)
            {
                gBoneboundWarriorEchoesSincePriestByPlayer[ownerGuid] = std::min<uint32>(priestPityThreshold, warriorSpawnsSincePriest + 1);
            }
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

        uint32 echoGuid = static_cast<uint32>(attacker->GetGUID().GetCounter());
        uint32& bleedCooldown = gBoneboundBleedCooldownByCaster[echoGuid];
        bool priestEcho = IsBoneboundPriestEcho(echoIt->second);
        if (priestEcho)
        {
            damage = 0;
            if (Creature* priestCreature = attacker->ToCreature())
                MoveBoneboundPriestEchoToSafePosition(priestCreature, owner, victim, echoIt->second, *runtimeConfig);
            return;
        }

        if (!priestEcho && runtimeConfig->bleedEnabled && bleedCooldown == 0)
        {
            StartBoneboundBleed(owner, attacker, victim, *runtimeConfig, echoIt->second.damagePct);
            bleedCooldown = std::max<uint32>(1000u, runtimeConfig->bleedCooldownMs);
        }

        uint32 alphaRoll = ResolveAlphaMeleeDamageRoll(alphaPet, owner, *runtimeConfig);
        uint32 scaledRoll = std::max<uint32>(1u, (alphaRoll * std::max<uint32>(1u, echoIt->second.damagePct)) / 100u);
        SeedBoneboundOwnerKillCredit(owner, victim, scaledRoll);
        damage = std::max<uint32>(damage, scaledRoll);
        if (!priestEcho)
            TryBoneboundCleave(owner, attacker, victim, *runtimeConfig, scaledRoll, runtimeConfig->echoCleaveDamagePct);
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

    void HandleNightWatchersLensWeaponDamage(Unit* attacker, Unit* victim, uint32& damage)
    {
        TryProcNightWatchersLensMark(attacker, victim, damage);
    }

    void HandleNightWatchersLensSpellDamage(Unit* attacker, Unit* victim, int32& damage, SpellInfo const* spellInfo)
    {
        if (damage <= 0 || !IsNightWatchersLensWandShot(spellInfo))
            return;

        TryProcNightWatchersLensMark(attacker, victim, static_cast<uint32>(damage));
    }

    void HandleNightWatchersLensDefenseExposure(
        Unit const* /*attacker*/,
        Unit const* victim,
        WeaponAttackType /*attType*/,
        int32& /*attackerMaxSkillValueForLevel*/,
        int32& victimMaxSkillValueForLevel,
        int32& /*attackerWeaponSkill*/,
        int32& victimDefenseSkill,
        int32& crit_chance,
        int32& miss_chance,
        int32& dodge_chance,
        int32& parry_chance,
        int32& block_chance)
    {
        if (!IsNightWatchersLensMarked(victim))
            return;

        victimMaxSkillValueForLevel = HalveNightWatchersLensDefenseValue(victimMaxSkillValueForLevel);
        victimDefenseSkill = HalveNightWatchersLensDefenseValue(victimDefenseSkill);
        miss_chance = HalveNightWatchersLensDefenseValue(miss_chance);
        dodge_chance = HalveNightWatchersLensDefenseValue(dodge_chance);
        parry_chance = HalveNightWatchersLensDefenseValue(parry_chance);
        block_chance = HalveNightWatchersLensDefenseValue(block_chance);
        crit_chance = std::clamp<int32>(crit_chance * 2, 0, 10000);
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
        if (IsBoneboundEchoModeBehaviorKind(behaviorKind))
        {
            std::string mode = ExtractJsonString(payloadJson, "mode").value_or("");
            std::optional<float> huntRadius = ExtractJsonFloat(payloadJson, "hunt_radius");
            BehaviorExecutionResult exec = ExecuteBoneboundEchoMode(player, mode, huntRadius);
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
