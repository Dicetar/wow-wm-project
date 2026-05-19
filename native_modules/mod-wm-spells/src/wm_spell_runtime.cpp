#include "wm_spell_runtime.h"

#include "wm_spell_internal.h"

#include "CellImpl.h"
#include "Chat.h"
#include "Config.h"
#include "Creature.h"
#include "CreatureAI.h"
#include "DatabaseEnv.h"
#include "DBCStores.h"
#include "GameTime.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Group.h"
#include "GroupReference.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Map.h"
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
#include <utility>
#include <vector>

namespace WmSpells
{
    bool IsNightWatchersLensMarkedBy(Unit const* unit, Player const* player);
}

namespace
{
    using namespace std::chrono_literals;
    using namespace WmSpells::detail;

    constexpr uint32 COMBAT_PROFICIENCY_SHELL_ID = 944000;
    constexpr uint32 BROUG_DEFLECT_SHELL_ID = 946603;
    constexpr uint32 BROUG_VULNERABLE_SHELL_ID = 946200;
    constexpr uint32 BROUG_DEFLECTED_SHELL_ID = 946201;
    constexpr uint32 BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID = 946605;
    constexpr uint32 BROUG_SKIRMISHER_MARK_SHELL_ID = 946098;
    constexpr uint32 BROUG_RETIRED_SKIRMISHER_TOGGLE_SHELL_ID = 946604;
    constexpr uint32 BROUG_UNIVERSAL_PARRY_SHELL_ID = 946800;
    constexpr uint32 BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID = 946801;
    constexpr uint32 BROUG_AUTO_RETALIATION_SHELL_ID = 946802;
    constexpr uint32 BROUG_CLOUD_STEP_SHELL_ID = 946202;
    constexpr uint32 BROUG_MARKED_MERIDIAN_SHELL_ID = 946203;
    constexpr uint32 BROUG_SUPPRESSED_SHELL_ID = 946204;
    constexpr uint32 BROUG_KILLING_INTENT_SHELL_ID = 946620;
    constexpr uint32 BROUG_QI_REVERSAL_SHELL_ID = 946621;
    constexpr uint32 BROUG_PURGED_STATE_SHELL_ID = 946622;
    constexpr uint32 BROUG_SILENT_MERIDIAN_SHELL_ID = 946803;
    constexpr uint32 BROUG_KILLING_INTENT_DOMAIN_SHELL_ID = 946804;
    constexpr uint32 BROUG_PREDATORS_STRIKE_SHELL_ID = 946805;
    constexpr uint32 BROUG_VITALITY_DRAIN_SHELL_ID = 946806;
    constexpr uint32 BROUG_PARRY_QUEST_ID = 910180;
    constexpr uint32 BROUG_DEFLECT_QUEST_ID = 910181;
    constexpr uint32 BROUG_LIGHTNESS_STEPS_QUEST_ID = 910182;
    constexpr uint32 BROUG_LIGHTNESS_NO_FOOTFALL_QUEST_ID = 910183;
    constexpr uint32 BROUG_EMPTY_COURT_WEIGHT_QUEST_ID = 910184;
    constexpr uint32 BROUG_EMPTY_COURT_STILLING_QUEST_ID = 910185;
    constexpr uint32 BROUG_EMPTY_COURT_NINETY_EIGHT_QUEST_ID = 910186;
    constexpr uint32 BROUG_EMPTY_COURT_ROOM_QUEST_ID = 910187;
    constexpr uint32 BROUG_EMPTY_COURT_DOMAIN_UNSEALED_QUEST_ID = 910188;
    constexpr uint32 BROUG_PARRY_CREDIT_CREATURE_ENTRY = 920104;
    constexpr uint32 BROUG_DEFLECT_CREDIT_CREATURE_ENTRY = 920105;
    constexpr uint32 BROUG_LIGHTNESS_CREDIT_CREATURE_ENTRY = 920106;
    constexpr uint32 SHIELD_SPELL_ID = 107;
    constexpr uint32 SHIELD_BLOCK_SPELL_ID = 9116;
    constexpr uint32 LEATHER_ARMOR_SPELL_ID = 9077;
    constexpr uint32 MAIL_ARMOR_SPELL_ID = 8737;
    constexpr uint32 PLATE_ARMOR_SPELL_ID = 750;
    constexpr uint32 DUAL_WIELD_SPELL_ID = 674;
    constexpr uint32 TWO_HANDED_SWORDS_SPELL_ID = 202;
    constexpr uint32 TWO_HANDED_AXES_SPELL_ID = 197;
    constexpr uint32 POLEARMS_SPELL_ID = 200;
    constexpr uint32 NIGHT_WATCHERS_LENS_ITEM_ENTRY = 910006;
    constexpr uint32 SHADOWMOON_WATCHERS_LENS_ITEM_ENTRY = 910013;
    // Detect Invisibility is a client-known, visible marker aura that fits the lens fantasy.
    // The WM-owned proc mechanic below is gated on this aura plus the equipped item.
    constexpr uint32 NIGHT_WATCHERS_LENS_VISIBLE_AURA_SPELL_ID = 132;
    // Faerie Fire is a visible target debuff with matching "exposed defenses" semantics.
    constexpr uint32 NIGHT_WATCHERS_LENS_MARK_DEBUFF_SPELL_ID = 770;
    constexpr uint32 NIGHT_WATCHERS_LENS_MARK_DURATION_MS = 10000;
    constexpr float NIGHT_WATCHERS_LENS_PROC_CHANCE_PCT = 10.0f;
    constexpr float NIGHT_WATCHERS_LENS_MARK_PROC_MULTIPLIER = 2.0f;
    constexpr uint32 NIGHT_WATCHERS_LENS_SPELL_FOCUS_DAMAGE_BONUS_PCT = 15;
    constexpr char BROUG_UNIVERSAL_PARRY_COUNTER_KEY[] = "universal_parry";
    constexpr char BROUG_SKIRMISHER_SHOT_COUNTER_KEY[] = "skirmisher_shot_hit";
    constexpr char BROUG_DEFLECT_COUNTER_KEY[] = "deflect_success";
    constexpr char BROUG_AUTO_RETALIATION_COUNTER_KEY[] = "auto_retaliation";
    constexpr char BROUG_CLOUD_STEP_STRIKE_COUNTER_KEY[] = "cloud_step_strike";
    constexpr char BROUG_SILENT_MERIDIAN_COUNTER_KEY[] = "silent_meridian_kill";
    constexpr char BROUG_DOMAIN_PULSE_COUNTER_KEY[] = "domain_pulse";
    constexpr char BROUG_SUPPRESSED_DEATH_EXTEND_COUNTER_KEY[] = "suppressed_death_extend";
    constexpr char BROUG_QI_REVERSAL_CLEANSE_COUNTER_KEY[] = "qi_reversal_cleanse";
    constexpr char BROUG_PREDATOR_HEAL_COUNTER_KEY[] = "predator_heal";
    constexpr char BROUG_VITALITY_KILL_COUNTER_KEY[] = "vitality_kill";
    // Rend is a client-known bleed debuff. WM owns the damage; this aura is the visible status/timer.
    constexpr uint32 BONEBOUND_BLEED_VISIBLE_AURA_SPELL_ID = 772;
    // Thorns is a client-known positive buff marker; WM strips its effects and only uses the stack count.
    constexpr uint32 BONEBOUND_ECHO_COUNT_DEFAULT_AURA_SPELL_ID = 467;
    constexpr uint32 BONEBOUND_SLASH_SPELL_ID = 945000;
    constexpr uint32 BONEBOUND_ECHO_SEEK_TARGET_STICKY_MS = 30000;
    constexpr uint32 BONEBOUND_RESTORER_MIND_BLAST_X3_SPELL_ID = 946099;
    constexpr float BONEBOUND_PRIEST_ECHO_MAX_EFFECTIVE_CAST_RANGE = 100.0f;
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

    struct LanathelStanceRuntimeState
    {
        uint32 shellSpellId = 0;
        uint32 displayId = 0;
        float displayScale = 1.0f;
        float landSpeedRate = 1.0f;
        float flightSpeedRate = 1.0f;
        bool flightAllowed = false;
    };

    std::unordered_map<uint32, LanathelStanceRuntimeState> gLanathelStanceByPlayer;
    std::optional<bool> gLanathelStanceStateTableAvailable;
    std::optional<bool> gBrougGuardCounterTableAvailable;
    std::optional<bool> gBrougLightnessCounterTableAvailable;
    std::optional<bool> gBrougEmptyCourtCounterTableAvailable;

    struct BrougGuardRuntimeState
    {
        bool hasUniversalParry = false;
        bool hasSkirmisherMark = false;
        bool hasDeflect = false;
        bool hasDeflectCounterStance = false;
        bool hasAutoRetaliation = false;
        WmSpells::BrougUniversalParryConfig universalParry;
        WmSpells::BrougSkirmisherMarkConfig skirmisherMark;
        WmSpells::BrougDeflectConfig deflect;
        WmSpells::BrougAutoRetaliationConfig autoRetaliation;
        uint32 skirmisherAttackTimerMs = 0;
        uint64 deflectWindowUntilMs = 0;
        uint64 deflectRootUntilMs = 0;
        uint64 deflectParryFeedbackAtMs = 0;
        uint64 deflectCooldownUntilMs = 0;
        bool deflectParryFeedbackPlayed = false;
        ObjectGuid deflectPrimaryAttackerGuid = ObjectGuid::Empty;
        uint64 deflectPendingResolveAtMs = 0;
        uint32 deflectPendingDamage = 0;
        std::unordered_map<ObjectGuid, uint32> deflectCaughtStacksByAttacker;
        uint64 autoRetaliationCooldownUntilMs = 0;
    };

    struct BrougPendingForcedParry
    {
        ObjectGuid attackerGuid;
        uint32 playerGuid = 0;
        uint64 expiresAtMs = 0;
        bool countEvent = false;
    };

    std::unordered_map<uint32, BrougGuardRuntimeState> gBrougGuardByPlayer;
    std::unordered_set<uint32> gBrougCounterStanceToggleOffByPlayer;
    std::unordered_set<ObjectGuid> gBrougDeflectedStunUnits;
    std::unordered_map<ObjectGuid, BrougPendingForcedParry> gBrougPendingForcedParryByVictim;

    struct BrougLightnessRuntimeState
    {
        bool hasCloudStep = false;
        bool hasSilentMeridian = false;
        WmSpells::BrougCloudStepConfig cloudStep;
        WmSpells::BrougSilentMeridianConfig silentMeridian;
        uint64 cloudStepCooldownUntilMs = 0;
        ObjectGuid cloudStepKillTargetGuid = ObjectGuid::Empty;
        uint64 cloudStepKillWindowUntilMs = 0;
        ObjectGuid markedMeridianTargetGuid = ObjectGuid::Empty;
        uint64 markedMeridianUntilMs = 0;
    };

    std::unordered_map<uint32, BrougLightnessRuntimeState> gBrougLightnessByPlayer;
    std::unordered_map<ObjectGuid, uint64> gBrougLightnessPreserveVulnerableByVictim;

    struct BrougEmptyCourtRuntimeState
    {
        bool hasDomain = false;
        bool hasQiReversal = false;
        bool hasPredatorsStrike = false;
        bool hasVitalityDrain = false;
        WmSpells::BrougKillingIntentDomainConfig domain;
        WmSpells::BrougQiReversalConfig qiReversal;
        WmSpells::BrougPredatorsStrikeConfig predatorsStrike;
        WmSpells::BrougVitalityDrainConfig vitalityDrain;
        uint32 domainPulseTimerMs = 0;
        uint32 purgedCharges = 0;
        uint64 purgedStateUntilMs = 0;
        std::unordered_set<uint32> purgedProtectedDispelTypes;
    };

    std::unordered_map<uint32, BrougEmptyCourtRuntimeState> gBrougEmptyCourtByPlayer;

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

    struct BoneboundEchoSeekTargetState
    {
        ObjectGuid targetGuid;
        uint32 remainingStickyMs = 0;
    };

    struct CombatProficiencyRuntimeGrant
    {
        uint32 skillId = 0;
        uint32 spellId = 0;
        bool scalesWithLevel = false;
        uint8 minPlayerLevel = 1;
    };

    constexpr CombatProficiencyRuntimeGrant COMBAT_PROFICIENCY_RUNTIME_GRANTS[] = {
        {SKILL_SHIELD, SHIELD_SPELL_ID, false, 1},
        {SKILL_SHIELD, SHIELD_BLOCK_SPELL_ID, false, 1},
        {SKILL_LEATHER, LEATHER_ARMOR_SPELL_ID, false, 1},
        {SKILL_MAIL, MAIL_ARMOR_SPELL_ID, false, 1},
        {SKILL_DUAL_WIELD, DUAL_WIELD_SPELL_ID, false, 1},
        {SKILL_2H_SWORDS, TWO_HANDED_SWORDS_SPELL_ID, true, 1},
        {SKILL_2H_AXES, TWO_HANDED_AXES_SPELL_ID, true, 1},
        {SKILL_POLEARMS, POLEARMS_SPELL_ID, true, 1},
        {SKILL_PLATE_MAIL, PLATE_ARMOR_SPELL_ID, false, 40},
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
    std::unordered_map<uint32, BoneboundEchoSeekTargetState> gBoneboundEchoSeekTargetByCaster;
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
        config.priestEchoDpsSpellId = BONEBOUND_RESTORER_MIND_BLAST_X3_SPELL_ID;
        config.priestEchoDpsDamageSpellId = BONEBOUND_RESTORER_MIND_BLAST_X3_SPELL_ID;
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

    bool IsBrougGuardBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "broug_universal_parry_v1"
            || behaviorKind == "broug_skirmisher_shot_v1"
            || behaviorKind == "broug_deflect_v1"
            || behaviorKind == "broug_deflect_counter_stance_v1"
            || behaviorKind == "broug_auto_retaliation_v1";
    }

    bool IsBrougLightnessBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "broug_cloud_step_v1"
            || behaviorKind == "broug_marked_meridian_v1"
            || behaviorKind == "broug_killing_intent_v1"
            || behaviorKind == "broug_silent_meridian_v1";
    }

    bool IsBrougEmptyCourtBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "broug_killing_intent_domain_v1"
            || behaviorKind == "broug_suppressed_v1"
            || behaviorKind == "broug_qi_reversal_v1"
            || behaviorKind == "broug_purged_state_v1"
            || behaviorKind == "broug_predators_strike_v1"
            || behaviorKind == "broug_vitality_drain_v1";
    }

    bool IsBoneboundEchoModeBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "bonebound_echo_mode_v1";
    }

    bool IsBoneboundEchoStasisBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "bonebound_echo_stasis_v1";
    }

    bool IsLanathelStanceBehaviorKind(std::string const& behaviorKind)
    {
        return behaviorKind == "lanathel_blood_queen_stance_v1";
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
        if (std::optional<float> value = ExtractJsonFloat(configJson, "alpha_echo_movement_speed_multiplier"))
            config.alphaEchoMovementSpeedMultiplier = *value;
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
        if (std::optional<float> value = ExtractJsonFloat(configJson, "priest_echo_movement_speed_multiplier"))
            config.priestEchoMovementSpeedMultiplier = *value;
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

    std::optional<WmSpells::BrougUniversalParryConfig> BuildBrougUniversalParryConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_universal_parry_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougUniversalParryConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "base_chance_pct"))
            config.baseChancePct = std::clamp(*value, 0.0f, 100.0f);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "strength_to_chance_pct"))
            config.strengthToChancePct = std::max(0.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "agility_to_chance_pct"))
            config.agilityToChancePct = std::max(0.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "expertise_to_chance_pct"))
            config.expertiseToChancePct = std::max(0.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "weapon_mastery_to_chance_pct"))
            config.weaponMasteryToChancePct = std::max(0.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "attack_power_to_chance_pct"))
            config.attackPowerToChancePct = std::max(0.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "max_chance_pct"))
            config.maxChancePct = std::clamp(*value, 0.0f, 100.0f);
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_UNIVERSAL_PARRY_COUNTER_KEY : *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "count_spell_damage"))
            config.countSpellDamage = *value;
        if (std::optional<bool> value = ExtractJsonBool(configJson, "count_periodic_damage"))
            config.countPeriodicDamage = *value;

        return config;
    }

    std::optional<WmSpells::BrougSkirmisherMarkConfig> BuildBrougSkirmisherMarkConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_skirmisher_shot_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougSkirmisherMarkConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "min_range_yards"))
            config.minRangeYards = std::max(0.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "max_range_yards"))
            config.maxRangeYards = std::clamp(*value, 5.0f, 100.0f);
        if (config.minRangeYards > config.maxRangeYards)
            config.minRangeYards = 0.0f;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "damage_pct"))
            config.damagePct = std::clamp<uint32>(*value, 1u, 500u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "min_attack_interval_ms"))
            config.minAttackIntervalMs = std::clamp<uint32>(*value, 250u, 10000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "max_attack_interval_ms"))
            config.maxAttackIntervalMs = std::clamp<uint32>(*value, 250u, 30000u);
        if (config.minAttackIntervalMs > config.maxAttackIntervalMs)
            config.maxAttackIntervalMs = config.minAttackIntervalMs;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "visual_spell_id"))
            config.visualSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "impact_sound_id"))
            config.impactSoundId = *value;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_SKIRMISHER_SHOT_COUNTER_KEY : *value;

        return config;
    }

    std::optional<WmSpells::BrougDeflectConfig> BuildBrougDeflectConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_deflect_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougDeflectConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "parry_pre_ms"))
            config.parryPreMs = std::clamp<uint32>(*value, 0u, 1000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "parry_animation_ms"))
            config.parryAnimationMs = std::clamp<uint32>(*value, 50u, 2000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "parry_post_ms"))
            config.parryPostMs = std::clamp<uint32>(*value, 0u, 1000u);
        config.windowMs = std::clamp<uint32>(
            config.parryPreMs + config.parryAnimationMs + config.parryPostMs,
            50u,
            3000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "window_ms"))
            config.windowMs = std::clamp<uint32>(*value, 50u, 3000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "cooldown_ms"))
            config.cooldownMs = std::clamp<uint32>(*value, 0u, 60000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "energy_cost"))
            config.energyCost = std::clamp<uint32>(*value, 0u, 100u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "stun_ms"))
            config.stunMs = std::clamp<uint32>(*value, 0u, 10000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "deflected_stun_ms_per_stack"))
            config.stunMs = std::clamp<uint32>(*value, 0u, 10000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "vulnerable_spell_id"))
            config.vulnerableSpellId = *value == 0 ? BROUG_VULNERABLE_SHELL_ID : *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "deflected_spell_id"))
            config.deflectedSpellId = *value == 0 ? BROUG_DEFLECTED_SHELL_ID : *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "vulnerable_duration_ms"))
            config.vulnerableDurationMs = std::clamp<uint32>(*value, 1000u, 300000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "max_vulnerable_stacks"))
            config.maxVulnerableStacks = std::clamp<uint32>(*value, 1u, 255u);
        if (std::optional<bool> value = ExtractJsonBool(configJson, "counterattack_enabled_default"))
            config.counterattackEnabledDefault = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "base_damage"))
            config.baseDamage = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "weapon_damage_pct"))
            config.weaponDamagePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "attack_power_pct"))
            config.attackPowerPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "visual_spell_id"))
            config.visualSpellId = *value;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_DEFLECT_COUNTER_KEY : *value;

        return config;
    }

    std::optional<WmSpells::BrougAutoRetaliationConfig> BuildBrougAutoRetaliationConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_auto_retaliation_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougAutoRetaliationConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "cooldown_ms"))
            config.cooldownMs = std::clamp<uint32>(*value, 0u, 60000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "base_damage"))
            config.baseDamage = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "weapon_damage_pct"))
            config.weaponDamagePct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "attack_power_pct"))
            config.attackPowerPct = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "visual_spell_id"))
            config.visualSpellId = *value;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_AUTO_RETALIATION_COUNTER_KEY : *value;

        return config;
    }

    std::optional<WmSpells::BrougCloudStepConfig> BuildBrougCloudStepConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_cloud_step_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougCloudStepConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "min_range_yards"))
            config.minRangeYards = std::clamp(*value, 0.0f, 100.0f);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "max_range_yards"))
            config.maxRangeYards = std::clamp(*value, 1.0f, 100.0f);
        if (config.minRangeYards > config.maxRangeYards)
            config.minRangeYards = 0.0f;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "landing_distance_yards"))
            config.landingDistanceYards = std::clamp(*value, 0.5f, 5.0f);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "cooldown_ms"))
            config.cooldownMs = std::clamp<uint32>(*value, 0u, 120000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "energy_cost"))
            config.energyCost = std::clamp<uint32>(*value, 0u, 100u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "killing_intent_spell_id"))
            config.killingIntentSpellId = *value == 0 ? BROUG_KILLING_INTENT_SHELL_ID : *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "killing_intent_duration_ms"))
            config.killingIntentDurationMs = std::clamp<uint32>(*value, 250u, 60000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "marked_meridian_spell_id"))
            config.markedMeridianSpellId = *value == 0 ? BROUG_MARKED_MERIDIAN_SHELL_ID : *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "marked_meridian_duration_ms"))
            config.markedMeridianDurationMs = std::clamp<uint32>(*value, 250u, 60000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "damage_bonus_pct"))
            config.damageBonusPct = std::clamp<uint32>(*value, 0u, 500u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "departure_visual_spell_id"))
            config.departureVisualSpellId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "arrival_visual_spell_id"))
            config.arrivalVisualSpellId = *value;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_CLOUD_STEP_STRIKE_COUNTER_KEY : *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "credit_creature_entry"))
            config.creditCreatureEntry = *value == 0 ? BROUG_LIGHTNESS_CREDIT_CREATURE_ENTRY : *value;

        return config;
    }

    std::optional<WmSpells::BrougSilentMeridianConfig> BuildBrougSilentMeridianConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_silent_meridian_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougSilentMeridianConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "kill_window_ms"))
            config.killWindowMs = std::clamp<uint32>(*value, 250u, 60000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "energy_restore"))
            config.energyRestore = std::clamp<uint32>(*value, 0u, 100u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "cooldown_reduction_ms"))
            config.cooldownReductionMs = std::clamp<uint32>(*value, 0u, 120000u);
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_SILENT_MERIDIAN_COUNTER_KEY : *value;

        return config;
    }

    std::optional<WmSpells::BrougKillingIntentDomainConfig> BuildBrougKillingIntentDomainConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_killing_intent_domain_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougKillingIntentDomainConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "killing_intent_spell_id"))
            config.killingIntentSpellId = *value == 0 ? BROUG_KILLING_INTENT_SHELL_ID : *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "suppressed_spell_id"))
            config.suppressedSpellId = *value == 0 ? BROUG_SUPPRESSED_SHELL_ID : *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "base_killing_intent_duration_ms"))
            config.baseKillingIntentDurationMs = std::clamp<uint32>(*value, 1000u, 600000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "pulse_interval_ms"))
            config.pulseIntervalMs = std::clamp<uint32>(*value, 250u, 60000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "suppressed_duration_ms"))
            config.suppressedDurationMs = std::clamp<uint32>(*value, 1000u, 600000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "death_extension_ms"))
            config.deathExtensionMs = std::clamp<uint32>(*value, 0u, 600000u);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "radius_yards"))
            config.radiusYards = std::clamp(*value, 1.0f, 100.0f);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "suppressed_damage_pressure_pct"))
            config.suppressedDamagePressurePct = std::clamp<uint32>(*value, 0u, 90u);
        if (std::optional<std::string> value = ExtractJsonString(configJson, "pulse_counter_key"))
            config.pulseCounterKey = value->empty() ? BROUG_DOMAIN_PULSE_COUNTER_KEY : *value;
        if (std::optional<std::string> value = ExtractJsonString(configJson, "death_extend_counter_key"))
            config.deathExtendCounterKey = value->empty() ? BROUG_SUPPRESSED_DEATH_EXTEND_COUNTER_KEY : *value;

        return config;
    }

    std::optional<WmSpells::BrougQiReversalConfig> BuildBrougQiReversalConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_qi_reversal_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougQiReversalConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "purged_state_spell_id"))
            config.purgedStateSpellId = *value == 0 ? BROUG_PURGED_STATE_SHELL_ID : *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "max_magic"))
            config.maxMagic = std::clamp<uint32>(*value, 0u, 10u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "max_poison"))
            config.maxPoison = std::clamp<uint32>(*value, 0u, 10u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "max_disease"))
            config.maxDisease = std::clamp<uint32>(*value, 0u, 10u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "purged_duration_ms"))
            config.purgedDurationMs = std::clamp<uint32>(*value, 1000u, 600000u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "purged_charges"))
            config.purgedCharges = std::clamp<uint32>(*value, 0u, 255u);
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_QI_REVERSAL_CLEANSE_COUNTER_KEY : *value;

        return config;
    }

    std::optional<WmSpells::BrougPredatorsStrikeConfig> BuildBrougPredatorsStrikeConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_predators_strike_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougPredatorsStrikeConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "heal_pct_of_damage"))
            config.healPctOfDamage = std::clamp<uint32>(*value, 0u, 500u);
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_PREDATOR_HEAL_COUNTER_KEY : *value;

        return config;
    }

    std::optional<WmSpells::BrougVitalityDrainConfig> BuildBrougVitalityDrainConfig(WmSpells::BehaviorRecord const& record)
    {
        if (record.behaviorKind != "broug_vitality_drain_v1" || record.status == "disabled")
            return std::nullopt;

        WmSpells::BrougVitalityDrainConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "kill_heal_pct_max_health"))
            config.killHealPctMaxHealth = std::clamp<uint32>(*value, 0u, 100u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "silent_window_kill_heal_pct_max_health"))
            config.silentWindowKillHealPctMaxHealth = std::clamp<uint32>(*value, 0u, 100u);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "silent_window_energy_bonus"))
            config.silentWindowEnergyBonus = std::clamp<uint32>(*value, 0u, 100u);
        if (std::optional<std::string> value = ExtractJsonString(configJson, "counter_key"))
            config.counterKey = value->empty() ? BROUG_VITALITY_KILL_COUNTER_KEY : *value;

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

    std::optional<WmSpells::LanathelStanceConfig> BuildLanathelStanceConfig(WmSpells::BehaviorRecord const& record)
    {
        if (!IsLanathelStanceBehaviorKind(record.behaviorKind) || record.status == "disabled")
            return std::nullopt;

        WmSpells::LanathelStanceConfig config;
        config.shellSpellId = record.shellSpellId;

        std::string const& configJson = record.configJson;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "display_id"))
            config.displayId = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "display_scale"))
            config.displayScale = std::clamp(*value, 0.05f, 3.0f);
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "riding_skill_id"))
            config.ridingSkillId = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "apprentice_riding_skill"))
            config.apprenticeRidingSkill = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "journeyman_riding_skill"))
            config.journeymanRidingSkill = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "expert_riding_skill"))
            config.expertRidingSkill = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "artisan_riding_skill"))
            config.artisanRidingSkill = *value;
        if (std::optional<uint32> value = ExtractJsonUInt(configJson, "master_riding_skill"))
            config.masterRidingSkill = *value;
        if (std::optional<float> value = ExtractJsonFloat(configJson, "base_land_speed_rate"))
            config.baseLandSpeedRate = std::max(1.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "apprentice_land_speed_rate"))
            config.apprenticeLandSpeedRate = std::max(1.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "journeyman_land_speed_rate"))
            config.journeymanLandSpeedRate = std::max(1.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "expert_flight_speed_rate"))
            config.expertFlightSpeedRate = std::max(1.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "artisan_flight_speed_rate"))
            config.artisanFlightSpeedRate = std::max(1.0f, *value);
        if (std::optional<float> value = ExtractJsonFloat(configJson, "master_flight_speed_rate"))
            config.masterFlightSpeedRate = std::max(1.0f, *value);
        if (std::optional<bool> value = ExtractJsonBool(configJson, "flight_requires_flyable_area"))
            config.flightRequiresFlyableArea = *value;

        return config;
    }

    bool LanathelStanceStateTableExists()
    {
        if (gLanathelStanceStateTableAvailable.value_or(false))
            return *gLanathelStanceStateTableAvailable;

        QueryResult result = WorldDatabase.Query(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wm_lanathel_stance_state' LIMIT 1");
        if (result)
            gLanathelStanceStateTableAvailable = true;
        return result ? true : false;
    }

    std::optional<uint32> LoadStoredLanathelStanceShell(uint32 playerGuid)
    {
        if (playerGuid == 0 || !LanathelStanceStateTableExists())
            return std::nullopt;

        QueryResult result = WorldDatabase.Query(
            "SELECT ShellSpellID FROM wm_lanathel_stance_state "
            "WHERE PlayerGUID = {} AND Active = 1 LIMIT 1",
            playerGuid);
        if (!result)
            return std::nullopt;

        Field* fields = result->Fetch();
        return fields[0].Get<uint32>();
    }

    void StoreLanathelStanceState(uint32 playerGuid, uint32 shellSpellId)
    {
        if (playerGuid == 0 || shellSpellId == 0 || !LanathelStanceStateTableExists())
            return;

        WorldDatabase.Execute(
            "INSERT INTO wm_lanathel_stance_state "
            "(PlayerGUID, ShellSpellID, Active, StoredAt, UpdatedAt) VALUES "
            "({}, {}, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
            "ON DUPLICATE KEY UPDATE "
            "ShellSpellID = VALUES(ShellSpellID), Active = 1, UpdatedAt = CURRENT_TIMESTAMP",
            playerGuid,
            shellSpellId);
    }

    void ClearLanathelStanceState(uint32 playerGuid)
    {
        if (playerGuid == 0 || !LanathelStanceStateTableExists())
            return;

        WorldDatabase.Execute(
            "UPDATE wm_lanathel_stance_state SET Active = 0, UpdatedAt = CURRENT_TIMESTAMP WHERE PlayerGUID = {}",
            playerGuid);
    }

    uint32 ResolveLanathelRidingSkill(Player* player, WmSpells::LanathelStanceConfig const& config)
    {
        if (!player || config.ridingSkillId == 0)
            return 0;

        return player->GetBaseSkillValue(config.ridingSkillId);
    }

    float ResolveLanathelLandSpeedRate(Player* player, WmSpells::LanathelStanceConfig const& config)
    {
        uint32 ridingSkill = ResolveLanathelRidingSkill(player, config);
        if (ridingSkill >= config.journeymanRidingSkill)
            return config.journeymanLandSpeedRate;
        if (ridingSkill >= config.apprenticeRidingSkill)
            return config.apprenticeLandSpeedRate;
        return config.baseLandSpeedRate;
    }

    float ResolveLanathelFlightSpeedRate(Player* player, WmSpells::LanathelStanceConfig const& config)
    {
        uint32 ridingSkill = ResolveLanathelRidingSkill(player, config);
        if (ridingSkill >= config.masterRidingSkill)
            return config.masterFlightSpeedRate;
        if (ridingSkill >= config.artisanRidingSkill)
            return config.artisanFlightSpeedRate;
        return config.expertFlightSpeedRate;
    }

    bool IsLanathelFlightEnvironment(Player* player, WmSpells::LanathelStanceConfig const& config)
    {
        if (!player || ResolveLanathelRidingSkill(player, config) < config.expertRidingSkill)
            return false;

        if (!config.flightRequiresFlyableArea)
            return true;

        if (!player->IsOutdoors())
            return false;

        AreaTableEntry const* areaEntry = sAreaTableStore.LookupEntry(player->GetAreaId());
        if (!areaEntry)
            areaEntry = sAreaTableStore.LookupEntry(player->GetZoneId());
        if (!areaEntry || !areaEntry->IsFlyable() || (areaEntry->flags & AREA_FLAG_NO_FLY_ZONE) != 0)
            return false;

        SpellInfo const* spellInfo = sSpellMgr->GetSpellInfo(config.shellSpellId);
        return spellInfo && player->canFlyInZone(player->GetMapId(), player->GetZoneId(), spellInfo);
    }

    void RestoreLanathelTransient(Player* player, bool clearFlight)
    {
        if (!player)
            return;

        if (clearFlight)
        {
            if (player->IsFlying())
                player->GetMotionMaster()->MoveFall();
            if (player->CanFly())
                player->SetCanFly(false);
        }

        player->RestoreDisplayId();
        player->SetObjectScale(1.0f);
        player->UpdateSpeed(MOVE_RUN, true);
        player->UpdateSpeed(MOVE_SWIM, true);
        player->UpdateSpeed(MOVE_FLIGHT, true);
    }

    void ApplyLanathelStance(Player* player, WmSpells::LanathelStanceConfig const& config)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        bool wasFlightAllowed = false;
        if (auto it = gLanathelStanceByPlayer.find(playerGuid); it != gLanathelStanceByPlayer.end())
            wasFlightAllowed = it->second.flightAllowed;

        player->Dismount();
        player->RemoveAurasByType(SPELL_AURA_MOUNTED);
        if (config.displayId != 0)
            player->SetDisplayId(config.displayId, config.displayScale);

        float landSpeedRate = ResolveLanathelLandSpeedRate(player, config);
        bool flightAllowed = IsLanathelFlightEnvironment(player, config);
        float flightSpeedRate = ResolveLanathelFlightSpeedRate(player, config);

        if (flightAllowed)
        {
            if (!player->CanFly())
                player->SetCanFly(true);
            player->SetSpeed(MOVE_FLIGHT, flightSpeedRate, true);
        }
        else
        {
            if (wasFlightAllowed && player->IsFlying())
                player->GetMotionMaster()->MoveFall();
            if (player->CanFly())
                player->SetCanFly(false);
            player->UpdateSpeed(MOVE_FLIGHT, true);
        }

        player->SetSpeed(MOVE_RUN, landSpeedRate, true);
        player->SetSpeed(MOVE_SWIM, landSpeedRate, true);

        LanathelStanceRuntimeState state;
        state.shellSpellId = config.shellSpellId;
        state.displayId = config.displayId;
        state.displayScale = config.displayScale;
        state.landSpeedRate = landSpeedRate;
        state.flightSpeedRate = flightSpeedRate;
        state.flightAllowed = flightAllowed;
        gLanathelStanceByPlayer[playerGuid] = state;
    }

    std::optional<WmSpells::LanathelStanceConfig> LoadActiveLanathelStanceConfig(Player* player)
    {
        if (!player)
            return std::nullopt;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        uint32 shellSpellId = 0;
        if (auto it = gLanathelStanceByPlayer.find(playerGuid); it != gLanathelStanceByPlayer.end())
            shellSpellId = it->second.shellSpellId;
        if (shellSpellId == 0)
        {
            std::optional<uint32> storedShellSpellId = LoadStoredLanathelStanceShell(playerGuid);
            if (storedShellSpellId.has_value())
                shellSpellId = *storedShellSpellId;
        }
        if (shellSpellId == 0)
            return std::nullopt;

        std::optional<WmSpells::BehaviorRecord> behaviorRecord = WmSpells::LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return std::nullopt;
        return BuildLanathelStanceConfig(*behaviorRecord);
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

    Unit* SelectNightWatchersLensMarkedBoneboundSeekTarget(Player* owner, Creature* seeker, float radius)
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
                || !seeker->IsWithinLOSInMap(candidate)
                || !WmSpells::IsNightWatchersLensMarkedBy(candidate, owner))
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

    bool IsValidBoneboundSeekTarget(Player* owner, Creature* seeker, Unit* target)
    {
        return owner
            && seeker
            && target
            && target != owner
            && target != seeker
            && target->IsAlive()
            && owner->GetMapId() == seeker->GetMapId()
            && target->GetMapId() == owner->GetMapId()
            && !owner->IsFriendlyTo(target)
            && seeker->CanCreatureAttack(target, true);
    }

    Unit* SelectBoneboundEchoSeekTarget(Player* owner, Creature* seeker, float radius, uint32 diff)
    {
        if (!owner || !seeker || radius <= 0.0f)
            return nullptr;

        uint32 echoGuid = static_cast<uint32>(seeker->GetGUID().GetCounter());
        auto stickyIt = gBoneboundEchoSeekTargetByCaster.find(echoGuid);
        if (stickyIt != gBoneboundEchoSeekTargetByCaster.end())
        {
            if (stickyIt->second.remainingStickyMs > diff)
                stickyIt->second.remainingStickyMs -= diff;
            else
                stickyIt->second.remainingStickyMs = 0;

            Unit* stickyTarget = ObjectAccessor::GetUnit(*owner, stickyIt->second.targetGuid);
            if (!IsValidBoneboundSeekTarget(owner, seeker, stickyTarget))
            {
                stickyIt = gBoneboundEchoSeekTargetByCaster.erase(stickyIt);
            }
            else if (stickyIt->second.remainingStickyMs > 0)
            {
                if (!WmSpells::IsNightWatchersLensMarkedBy(stickyTarget, owner))
                {
                    if (Unit* markedTarget = SelectNightWatchersLensMarkedBoneboundSeekTarget(owner, seeker, radius))
                    {
                        if (markedTarget != stickyTarget)
                        {
                            stickyIt->second.targetGuid = markedTarget->GetGUID();
                            stickyIt->second.remainingStickyMs = BONEBOUND_ECHO_SEEK_TARGET_STICKY_MS;
                            return markedTarget;
                        }
                    }
                }
                return stickyTarget;
            }
        }

        Unit* selectedTarget = SelectNightWatchersLensMarkedBoneboundSeekTarget(owner, seeker, radius);
        if (!selectedTarget)
            selectedTarget = SelectNearestBoneboundSeekTarget(owner, seeker, radius);
        if (selectedTarget)
        {
            BoneboundEchoSeekTargetState& stickyState = gBoneboundEchoSeekTargetByCaster[echoGuid];
            if (stickyState.targetGuid != selectedTarget->GetGUID())
            {
                stickyState.targetGuid = selectedTarget->GetGUID();
                stickyState.remainingStickyMs = BONEBOUND_ECHO_SEEK_TARGET_STICKY_MS;
            }
            return selectedTarget;
        }

        if (stickyIt != gBoneboundEchoSeekTargetByCaster.end())
        {
            Unit* stickyTarget = ObjectAccessor::GetUnit(*owner, stickyIt->second.targetGuid);
            if (IsValidBoneboundSeekTarget(owner, seeker, stickyTarget))
                return stickyTarget;
            gBoneboundEchoSeekTargetByCaster.erase(stickyIt);
        }

        return nullptr;
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

    void MatchBoneboundEchoMovementSpeed(Pet* alphaPet, TempSummon* echo, float speedMultiplier = 1.0f)
    {
        if (!alphaPet || !echo)
            return;

        float multiplier = std::isfinite(speedMultiplier) && speedMultiplier > 0.0f
            ? std::clamp(speedMultiplier, 0.1f, 5.0f)
            : 1.0f;
        auto scaledSpeed = [alphaPet, multiplier](UnitMoveType moveType)
        {
            return alphaPet->GetSpeedRate(moveType) * multiplier;
        };

        echo->SetWalk(false);
        echo->SetSpeed(MOVE_WALK, scaledSpeed(MOVE_WALK), true);
        echo->SetSpeed(MOVE_RUN, scaledSpeed(MOVE_RUN), true);
        echo->SetSpeed(MOVE_RUN_BACK, scaledSpeed(MOVE_RUN_BACK), true);
        echo->SetSpeed(MOVE_SWIM, scaledSpeed(MOVE_SWIM), true);
        echo->SetSpeed(MOVE_SWIM_BACK, scaledSpeed(MOVE_SWIM_BACK), true);
        echo->SetSpeed(MOVE_FLIGHT, scaledSpeed(MOVE_FLIGHT), true);
        echo->SetSpeed(MOVE_FLIGHT_BACK, scaledSpeed(MOVE_FLIGHT_BACK), true);
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
            return std::min(configuredRange, BONEBOUND_PRIEST_ECHO_MAX_EFFECTIVE_CAST_RANGE);

        float spellRange = spellInfo->GetMaxRange(false, priestEcho);
        if (!std::isfinite(spellRange) || spellRange <= 0.0f)
            return std::min(configuredRange, BONEBOUND_PRIEST_ECHO_MAX_EFFECTIVE_CAST_RANGE);

        return std::min(configuredRange, std::min(BONEBOUND_PRIEST_ECHO_MAX_EFFECTIVE_CAST_RANGE, std::max(5.0f, spellRange)));
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

        float followDistance = std::max(1.2f, state.followDistance);
        float minEnemyDistance = std::max(3.0f, config.priestEchoSafeMinEnemyDistance);
        if (enemy && IsBoneboundEchoHuntMode(state.ownerGuid))
        {
            float castRange = ResolveBoneboundPriestVisibleDpsCastRange(priestEcho, config);
            float readyRange = std::max(5.0f, castRange - 1.0f);
            if (!priestEcho->IsWithinDistInMap(enemy, readyRange) || !priestEcho->IsWithinLOSInMap(enemy))
            {
                float chaseStopDistance = std::clamp(castRange * 0.65f, minEnemyDistance, std::max(minEnemyDistance, castRange - 2.0f));
                priestEcho->SetTarget(enemy->GetGUID());
                priestEcho->GetMotionMaster()->MoveChase(enemy, chaseStopDistance);
                return;
            }

            priestEcho->GetMotionMaster()->MoveIdle();
            priestEcho->SetTarget(enemy->GetGUID());
            priestEcho->SetFacingToObject(enemy);
            return;
        }

        priestEcho->AttackStop();
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

    Unit* SelectBoneboundPriestEnemyTarget(Creature* priestEcho, Player* owner, Pet* alphaPet, uint32 ownerGuid, WmSpells::BoneboundBehaviorConfig const& config, uint32 diff)
    {
        if (!priestEcho || !owner)
            return nullptr;

        if (IsBoneboundEchoHuntMode(ownerGuid))
        {
            std::optional<WmSpells::BoneboundBehaviorConfig> runtimeConfig = config;
            Unit* sought = SelectBoneboundEchoSeekTarget(owner, priestEcho, ResolveBoneboundEchoHuntRadius(ownerGuid, runtimeConfig), diff);
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

        priestEcho->Attack(victim, false);
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
        Unit* enemy = SelectBoneboundPriestEnemyTarget(priestEcho, owner, alphaPet, state.ownerGuid, config, diff);
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
        MatchBoneboundEchoMovementSpeed(alphaPet, echo, priestEcho ? config.priestEchoMovementSpeedMultiplier : config.alphaEchoMovementSpeedMultiplier);
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
            gBoneboundEchoSeekTargetByCaster.erase(it->first);
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
                gBoneboundEchoSeekTargetByCaster.erase(it->first);
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
                gBoneboundEchoSeekTargetByCaster.erase(it->first);
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
                    gBoneboundEchoSeekTargetByCaster.erase(it->first);
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
                    gBoneboundEchoSeekTargetByCaster.erase(it->first);
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
                    gBoneboundEchoSeekTargetByCaster.erase(it->first);
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
                gBoneboundEchoSeekTargetByCaster.erase(it->first);
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
                    victim = SelectBoneboundEchoSeekTarget(owner, echo, huntRadius, diff);
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

    std::optional<BrougGuardRuntimeState> LoadActiveBrougGuardState(Player* player, BrougGuardRuntimeState const* previousState)
    {
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return std::nullopt;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());

        QueryResult result = WorldDatabase.Query(
            "SELECT b.ShellSpellID, b.BehaviorKind, b.ConfigJSON, b.Status "
            "FROM wm_spell_grant g "
            "JOIN wm_spell_behavior b ON b.ShellSpellID = g.ShellSpellID "
            "WHERE g.PlayerGUID = {} "
            "  AND g.RevokedAt IS NULL "
            "  AND b.BehaviorKind IN ('broug_universal_parry_v1', 'broug_skirmisher_shot_v1', 'broug_deflect_v1', 'broug_deflect_counter_stance_v1', 'broug_auto_retaliation_v1') "
            "  AND b.Status = 'active' "
            "ORDER BY g.GrantID DESC",
            playerGuid);

        if (!result)
            return std::nullopt;

        BrougGuardRuntimeState state;
        if (previousState)
        {
            state.skirmisherAttackTimerMs = previousState->skirmisherAttackTimerMs;
            state.deflectWindowUntilMs = previousState->deflectWindowUntilMs;
            state.deflectRootUntilMs = previousState->deflectRootUntilMs;
            state.deflectParryFeedbackAtMs = previousState->deflectParryFeedbackAtMs;
            state.deflectCooldownUntilMs = previousState->deflectCooldownUntilMs;
            state.deflectParryFeedbackPlayed = previousState->deflectParryFeedbackPlayed;
            state.deflectPrimaryAttackerGuid = previousState->deflectPrimaryAttackerGuid;
            state.deflectPendingResolveAtMs = previousState->deflectPendingResolveAtMs;
            state.deflectPendingDamage = previousState->deflectPendingDamage;
            state.deflectCaughtStacksByAttacker = previousState->deflectCaughtStacksByAttacker;
            state.autoRetaliationCooldownUntilMs = previousState->autoRetaliationCooldownUntilMs;
        }
        do
        {
            Field* fields = result->Fetch();
            WmSpells::BehaviorRecord record;
            record.shellSpellId = fields[0].Get<uint32>();
            record.behaviorKind = fields[1].Get<std::string>();
            record.configJson = fields[2].Get<std::string>();
            record.status = fields[3].Get<std::string>();

            if (!state.hasUniversalParry)
            {
                std::optional<WmSpells::BrougUniversalParryConfig> parryConfig = BuildBrougUniversalParryConfig(record);
                if (parryConfig.has_value())
                {
                    state.universalParry = *parryConfig;
                    state.hasUniversalParry = true;
                    continue;
                }
            }

            if (!state.hasSkirmisherMark)
            {
                std::optional<WmSpells::BrougSkirmisherMarkConfig> marksmanConfig = BuildBrougSkirmisherMarkConfig(record);
                if (marksmanConfig.has_value())
                {
                    state.skirmisherMark = *marksmanConfig;
                    state.hasSkirmisherMark = true;
                    continue;
                }
            }

            if (!state.hasDeflect)
            {
                std::optional<WmSpells::BrougDeflectConfig> deflectConfig = BuildBrougDeflectConfig(record);
                if (deflectConfig.has_value())
                {
                    state.deflect = *deflectConfig;
                    state.hasDeflect = true;
                    continue;
                }
            }

            if (!state.hasDeflectCounterStance && record.behaviorKind == "broug_deflect_counter_stance_v1" && record.status == "active")
            {
                state.hasDeflectCounterStance = true;
                continue;
            }

            if (!state.hasAutoRetaliation)
            {
                std::optional<WmSpells::BrougAutoRetaliationConfig> retaliationConfig = BuildBrougAutoRetaliationConfig(record);
                if (retaliationConfig.has_value())
                {
                    state.autoRetaliation = *retaliationConfig;
                    state.hasAutoRetaliation = true;
                    continue;
                }
            }
        } while (result->NextRow());

        if (!state.hasUniversalParry
            && !state.hasSkirmisherMark
            && !state.hasDeflect
            && !state.hasDeflectCounterStance
            && !state.hasAutoRetaliation)
            return std::nullopt;

        return state;
    }

    bool BrougGuardCounterTableExists()
    {
        if (gBrougGuardCounterTableAvailable.has_value())
            return *gBrougGuardCounterTableAvailable;

        QueryResult result = WorldDatabase.Query(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wm_broug_guard_counter' LIMIT 1");
        gBrougGuardCounterTableAvailable = result ? true : false;
        return result ? true : false;
    }

    void RecordBrougGuardCounter(uint32 playerGuid, std::string const& counterKey, uint32 increment = 1)
    {
        if (playerGuid == 0 || counterKey.empty() || increment == 0 || !BrougGuardCounterTableExists())
            return;

        WorldDatabase.Execute(
            "INSERT INTO wm_broug_guard_counter "
            "(PlayerGUID, CounterKey, CounterValue, UpdatedAt) VALUES "
            "({}, {}, {}, CURRENT_TIMESTAMP) "
            "ON DUPLICATE KEY UPDATE "
            "CounterValue = CounterValue + VALUES(CounterValue), UpdatedAt = CURRENT_TIMESTAMP",
            playerGuid,
            SqlString(counterKey),
            increment);
    }

    std::optional<BrougLightnessRuntimeState> LoadActiveBrougLightnessState(Player* player, BrougLightnessRuntimeState const* previousState)
    {
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return std::nullopt;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());

        QueryResult result = WorldDatabase.Query(
            "SELECT b.ShellSpellID, b.BehaviorKind, b.ConfigJSON, b.Status "
            "FROM wm_spell_grant g "
            "JOIN wm_spell_behavior b ON b.ShellSpellID = g.ShellSpellID "
            "WHERE g.PlayerGUID = {} "
            "  AND g.RevokedAt IS NULL "
            "  AND b.BehaviorKind IN ('broug_cloud_step_v1', 'broug_silent_meridian_v1') "
            "  AND b.Status = 'active' "
            "ORDER BY g.GrantID DESC",
            playerGuid);

        if (!result)
            return std::nullopt;

        BrougLightnessRuntimeState state;
        if (previousState)
        {
            state.cloudStepCooldownUntilMs = previousState->cloudStepCooldownUntilMs;
            state.cloudStepKillTargetGuid = previousState->cloudStepKillTargetGuid;
            state.cloudStepKillWindowUntilMs = previousState->cloudStepKillWindowUntilMs;
            state.markedMeridianTargetGuid = previousState->markedMeridianTargetGuid;
            state.markedMeridianUntilMs = previousState->markedMeridianUntilMs;
        }

        do
        {
            Field* fields = result->Fetch();
            WmSpells::BehaviorRecord record;
            record.shellSpellId = fields[0].Get<uint32>();
            record.behaviorKind = fields[1].Get<std::string>();
            record.configJson = fields[2].Get<std::string>();
            record.status = fields[3].Get<std::string>();

            if (!state.hasCloudStep)
            {
                std::optional<WmSpells::BrougCloudStepConfig> cloudStepConfig = BuildBrougCloudStepConfig(record);
                if (cloudStepConfig.has_value())
                {
                    state.cloudStep = *cloudStepConfig;
                    state.hasCloudStep = true;
                    continue;
                }
            }

            if (!state.hasSilentMeridian)
            {
                std::optional<WmSpells::BrougSilentMeridianConfig> silentConfig = BuildBrougSilentMeridianConfig(record);
                if (silentConfig.has_value())
                {
                    state.silentMeridian = *silentConfig;
                    state.hasSilentMeridian = true;
                    continue;
                }
            }
        } while (result->NextRow());

        if (!state.hasCloudStep && !state.hasSilentMeridian)
            return std::nullopt;

        return state;
    }

    bool BrougLightnessCounterTableExists()
    {
        if (gBrougLightnessCounterTableAvailable.has_value())
            return *gBrougLightnessCounterTableAvailable;

        QueryResult result = WorldDatabase.Query(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wm_broug_lightness_counter' LIMIT 1");
        gBrougLightnessCounterTableAvailable = result ? true : false;
        return result ? true : false;
    }

    void RecordBrougLightnessCounter(uint32 playerGuid, std::string const& counterKey, uint32 increment = 1)
    {
        if (playerGuid == 0 || counterKey.empty() || increment == 0 || !BrougLightnessCounterTableExists())
            return;

        WorldDatabase.Execute(
            "INSERT INTO wm_broug_lightness_counter "
            "(PlayerGUID, CounterKey, CounterValue, UpdatedAt) VALUES "
            "({}, {}, {}, CURRENT_TIMESTAMP) "
            "ON DUPLICATE KEY UPDATE "
            "CounterValue = CounterValue + VALUES(CounterValue), UpdatedAt = CURRENT_TIMESTAMP",
            playerGuid,
            SqlString(counterKey),
            increment);
    }

    std::optional<BrougEmptyCourtRuntimeState> LoadActiveBrougEmptyCourtState(Player* player, BrougEmptyCourtRuntimeState const* previousState)
    {
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return std::nullopt;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());

        QueryResult result = WorldDatabase.Query(
            "SELECT b.ShellSpellID, b.BehaviorKind, b.ConfigJSON, b.Status "
            "FROM wm_spell_grant g "
            "JOIN wm_spell_behavior b ON b.ShellSpellID = g.ShellSpellID "
            "WHERE g.PlayerGUID = {} "
            "  AND g.RevokedAt IS NULL "
            "  AND b.BehaviorKind IN ("
            "'broug_killing_intent_domain_v1',"
            "'broug_qi_reversal_v1',"
            "'broug_predators_strike_v1',"
            "'broug_vitality_drain_v1') "
            "  AND b.Status = 'active' "
            "ORDER BY g.GrantID DESC",
            playerGuid);

        if (!result)
            return std::nullopt;

        BrougEmptyCourtRuntimeState state;
        if (previousState)
        {
            state.domainPulseTimerMs = previousState->domainPulseTimerMs;
            state.purgedCharges = previousState->purgedCharges;
            state.purgedStateUntilMs = previousState->purgedStateUntilMs;
            state.purgedProtectedDispelTypes = previousState->purgedProtectedDispelTypes;
        }

        do
        {
            Field* fields = result->Fetch();
            WmSpells::BehaviorRecord record;
            record.shellSpellId = fields[0].Get<uint32>();
            record.behaviorKind = fields[1].Get<std::string>();
            record.configJson = fields[2].Get<std::string>();
            record.status = fields[3].Get<std::string>();

            if (!state.hasDomain)
            {
                std::optional<WmSpells::BrougKillingIntentDomainConfig> domainConfig = BuildBrougKillingIntentDomainConfig(record);
                if (domainConfig.has_value())
                {
                    state.domain = *domainConfig;
                    state.hasDomain = true;
                    continue;
                }
            }

            if (!state.hasQiReversal)
            {
                std::optional<WmSpells::BrougQiReversalConfig> qiConfig = BuildBrougQiReversalConfig(record);
                if (qiConfig.has_value())
                {
                    state.qiReversal = *qiConfig;
                    state.hasQiReversal = true;
                    continue;
                }
            }

            if (!state.hasPredatorsStrike)
            {
                std::optional<WmSpells::BrougPredatorsStrikeConfig> predatorConfig = BuildBrougPredatorsStrikeConfig(record);
                if (predatorConfig.has_value())
                {
                    state.predatorsStrike = *predatorConfig;
                    state.hasPredatorsStrike = true;
                    continue;
                }
            }

            if (!state.hasVitalityDrain)
            {
                std::optional<WmSpells::BrougVitalityDrainConfig> vitalityConfig = BuildBrougVitalityDrainConfig(record);
                if (vitalityConfig.has_value())
                {
                    state.vitalityDrain = *vitalityConfig;
                    state.hasVitalityDrain = true;
                    continue;
                }
            }
        } while (result->NextRow());

        if (!state.hasDomain && !state.hasQiReversal && !state.hasPredatorsStrike && !state.hasVitalityDrain)
            return std::nullopt;

        return state;
    }

    bool BrougEmptyCourtCounterTableExists()
    {
        if (gBrougEmptyCourtCounterTableAvailable.has_value())
            return *gBrougEmptyCourtCounterTableAvailable;

        QueryResult result = WorldDatabase.Query(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wm_broug_empty_court_counter' LIMIT 1");
        gBrougEmptyCourtCounterTableAvailable = result ? true : false;
        return result ? true : false;
    }

    void RecordBrougEmptyCourtCounter(uint32 playerGuid, std::string const& counterKey, uint32 increment = 1)
    {
        if (playerGuid == 0 || counterKey.empty() || increment == 0 || !BrougEmptyCourtCounterTableExists())
            return;

        WorldDatabase.Execute(
            "INSERT INTO wm_broug_empty_court_counter "
            "(PlayerGUID, CounterKey, CounterValue, UpdatedAt) VALUES "
            "({}, {}, {}, CURRENT_TIMESTAMP) "
            "ON DUPLICATE KEY UPDATE "
            "CounterValue = CounterValue + VALUES(CounterValue), UpdatedAt = CURRENT_TIMESTAMP",
            playerGuid,
            SqlString(counterKey),
            increment);
    }

    float ResolveBrougAttackPower(Player* player, bool ranged)
    {
        if (!player)
            return 0.0f;

        if (ranged)
        {
            float baseAttackPower = static_cast<float>(player->GetInt32Value(UNIT_FIELD_RANGED_ATTACK_POWER));
            float attackPowerMods = static_cast<float>(player->GetInt32Value(UNIT_FIELD_RANGED_ATTACK_POWER_MODS));
            float attackPowerMultiplier = player->GetFloatValue(UNIT_FIELD_RANGED_ATTACK_POWER_MULTIPLIER);
            return std::max(0.0f, (baseAttackPower + attackPowerMods) * (1.0f + attackPowerMultiplier));
        }

        float baseAttackPower = static_cast<float>(player->GetInt32Value(UNIT_FIELD_ATTACK_POWER));
        float attackPowerMods = static_cast<float>(player->GetInt32Value(UNIT_FIELD_ATTACK_POWER_MODS));
        float attackPowerMultiplier = player->GetFloatValue(UNIT_FIELD_ATTACK_POWER_MULTIPLIER);
        return std::max(0.0f, (baseAttackPower + attackPowerMods) * (1.0f + attackPowerMultiplier));
    }

    float ResolveBrougUniversalParryExpertisePct(Player* player)
    {
        if (!player)
            return 0.0f;

        float mainHand = std::max(0.0f, player->GetExpertiseDodgeOrParryReduction(BASE_ATTACK));
        float offHand = player->HasOffhandWeaponForAttack()
            ? std::max(0.0f, player->GetExpertiseDodgeOrParryReduction(OFF_ATTACK))
            : 0.0f;
        return std::max(mainHand, offHand);
    }

    float ResolveBrougUniversalParryWeaponMasteryPct(Player* player, Unit* attacker)
    {
        if (!player)
            return 0.0f;

        float skillCap = static_cast<float>(std::max<uint16>(1, player->GetMaxSkillValueForLevel()));
        float mainHandSkill = static_cast<float>(player->GetWeaponSkillValue(BASE_ATTACK, attacker));
        float offHandSkill = player->HasOffhandWeaponForAttack()
            ? static_cast<float>(player->GetWeaponSkillValue(OFF_ATTACK, attacker))
            : 0.0f;
        float bestSkill = std::max(mainHandSkill, offHandSkill);

        // Treat capped weapon skill as 100% mastery, and allow weapon-skill rating
        // to push the mastery contribution slightly above cap without exploding.
        return std::clamp(bestSkill / skillCap, 0.0f, 1.25f) * 100.0f;
    }

    float ResolveBrougUniversalParryChance(Player* player, Unit* attacker, WmSpells::BrougUniversalParryConfig const& config)
    {
        if (!player)
            return 0.0f;

        float strength = std::max(0.0f, player->GetTotalStatValue(STAT_STRENGTH));
        float agility = std::max(0.0f, player->GetTotalStatValue(STAT_AGILITY));
        float expertisePct = ResolveBrougUniversalParryExpertisePct(player);
        float weaponMasteryPct = ResolveBrougUniversalParryWeaponMasteryPct(player, attacker);
        float attackPower = ResolveBrougAttackPower(player, false);
        float chance = config.baseChancePct
            + strength * config.strengthToChancePct
            + agility * config.agilityToChancePct
            + expertisePct * config.expertiseToChancePct
            + weaponMasteryPct * config.weaponMasteryToChancePct
            + attackPower * config.attackPowerToChancePct;
        return std::clamp(chance, 0.0f, config.maxChancePct);
    }

    bool IsBrougHostileDamage(Unit* attacker, Unit* victim)
    {
        return attacker
            && victim
            && attacker != victim
            && attacker->IsAlive()
            && victim->IsAlive()
            && attacker->IsValidAttackTarget(victim);
    }

    void CreditBrougQuestProgress(Player* player, uint32 creditCreatureEntry);
    void TryBrougAutoRetaliation(Player* player, Unit* target, BrougGuardRuntimeState& state);
    uint64 BrougNowMs();
    void ConsumeBrougVulnerableForDamage(Unit* attacker, Unit* victim, uint32& damage);
    bool TryConsumeBrougMarkedMeridian(Player* player, Unit* target, uint32& damage);
    bool HasActiveBrougEmptyCourtDomain(Player* player, uint32 playerGuid);
    bool IsBrougSilentMeridianKillWindowActive(Player* player, Creature* killed, uint64 nowMs);
    void ApplyBrougPredatorHeal(Player* player, uint32 playerGuid, uint32 damage);
    void ApplyBrougForcedStun(Player* player, Unit* target, uint32 stunMs, uint32 deflectedSpellId, uint32 deflectedStacks);

    bool IsBrougDeflectWindowActive(BrougGuardRuntimeState const& state, uint64 nowMs)
    {
        return state.hasDeflect && state.deflectWindowUntilMs != 0 && state.deflectWindowUntilMs >= nowMs;
    }

    void ClearBrougPendingDeflect(BrougGuardRuntimeState& state)
    {
        state.deflectPrimaryAttackerGuid = ObjectGuid::Empty;
        state.deflectPendingResolveAtMs = 0;
        state.deflectPendingDamage = 0;
        state.deflectCaughtStacksByAttacker.clear();
    }

    void ClearBrougDeflectWindow(Player* player, BrougGuardRuntimeState& state)
    {
        if (player && state.deflectRootUntilMs != 0)
            player->SetControlled(false, UNIT_STATE_ROOT);

        state.deflectWindowUntilMs = 0;
        state.deflectRootUntilMs = 0;
        state.deflectParryFeedbackAtMs = 0;
        state.deflectParryFeedbackPlayed = false;
        ClearBrougPendingDeflect(state);
    }

    uint32 ResolveBrougParryEmote(Player* player)
    {
        if (!player)
            return EMOTE_ONESHOT_PARRY_UNARMED;

        Item* mainHand = player->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_MAINHAND);
        if (!mainHand || !mainHand->GetTemplate())
            return EMOTE_ONESHOT_PARRY_UNARMED;

        switch (mainHand->GetTemplate()->SubClass)
        {
            case ITEM_SUBCLASS_WEAPON_SWORD2:
            case ITEM_SUBCLASS_WEAPON_AXE2:
            case ITEM_SUBCLASS_WEAPON_MACE2:
            case ITEM_SUBCLASS_WEAPON_POLEARM:
            case ITEM_SUBCLASS_WEAPON_STAFF:
            case ITEM_SUBCLASS_WEAPON_FISHING_POLE:
                return EMOTE_ONESHOT_PARRY2H;
            default:
                return EMOTE_ONESHOT_PARRY1H;
        }
    }

    void PlayBrougParryFeedback(Player* player)
    {
        if (!player || !player->IsInWorld())
            return;

        player->HandleEmoteCommand(ResolveBrougParryEmote(player));
        player->PlayDistanceSound(11904);
    }

    uint32 ResolveBrougAttackEmote(Player* player)
    {
        if (!player)
            return EMOTE_ONESHOT_ATTACK_UNARMED;

        Item* mainHand = player->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_MAINHAND);
        if (!mainHand || !mainHand->GetTemplate())
            return EMOTE_ONESHOT_ATTACK_UNARMED;

        switch (mainHand->GetTemplate()->SubClass)
        {
            case ITEM_SUBCLASS_WEAPON_SWORD2:
            case ITEM_SUBCLASS_WEAPON_AXE2:
            case ITEM_SUBCLASS_WEAPON_MACE2:
            case ITEM_SUBCLASS_WEAPON_POLEARM:
            case ITEM_SUBCLASS_WEAPON_STAFF:
            case ITEM_SUBCLASS_WEAPON_FISHING_POLE:
                return EMOTE_ONESHOT_ATTACK2H_LOOSE;
            default:
                return EMOTE_ONESHOT_ATTACK1H;
        }
    }

    void PlayBrougDeflectStrikeFeedback(Player* player, Unit* target)
    {
        if (!player || !player->IsInWorld())
            return;

        if (target)
            player->SetInFront(target);
        player->SetSheath(SHEATH_STATE_MELEE);
        player->HandleEmoteCommand(ResolveBrougAttackEmote(player));
        player->PlayDistanceSound(11904);
    }

    void DealBrougDeflectCounterDamage(Player* player, Unit* target, uint32 damage)
    {
        if (!player || !target || damage == 0 || !target->IsAlive())
            return;

        ConsumeBrougVulnerableForDamage(player, target, damage);
        if (damage == 0)
            return;

        CalcDamageInfo damageInfo;
        damageInfo.attacker = player;
        damageInfo.target = target;
        damageInfo.blocked_amount = 0;
        damageInfo.HitInfo = HITINFO_NORMALSWING;
        damageInfo.TargetState = VICTIMSTATE_HIT;
        damageInfo.attackType = BASE_ATTACK;
        damageInfo.procAttacker = PROC_FLAG_DONE_MELEE_AUTO_ATTACK | PROC_FLAG_DONE_MAINHAND_ATTACK;
        damageInfo.procVictim = PROC_FLAG_TAKEN_MELEE_AUTO_ATTACK;
        damageInfo.cleanDamage = 0;
        damageInfo.hitOutCome = MELEE_HIT_NORMAL;

        for (uint8 i = 0; i < MAX_ITEM_PROTO_DAMAGES; ++i)
        {
            damageInfo.damages[i].damageSchoolMask = i == 0 ? player->GetMeleeDamageSchoolMask(BASE_ATTACK, i) : SPELL_SCHOOL_MASK_NORMAL;
            damageInfo.damages[i].damage = i == 0 ? damage : 0;
            damageInfo.damages[i].absorb = 0;
            damageInfo.damages[i].resist = 0;
        }

        PlayBrougDeflectStrikeFeedback(player, target);
        player->SendMeleeAttackStart(target);
        player->SendAttackStateUpdate(&damageInfo);
        player->DealMeleeDamage(&damageInfo, true);
        player->SendMeleeAttackStop(target);
    }

    uint32 ResolveBrougRangedEmote(Item const* item)
    {
        if (!item || !item->GetTemplate())
            return EMOTE_ONESHOT_ATTACK_THROWN;

        switch (item->GetTemplate()->SubClass)
        {
            case ITEM_SUBCLASS_WEAPON_BOW:
            case ITEM_SUBCLASS_WEAPON_CROSSBOW:
                return EMOTE_ONESHOT_ATTACK_BOW;
            case ITEM_SUBCLASS_WEAPON_GUN:
                return EMOTE_ONESHOT_ATTACK_RIFLE;
            case ITEM_SUBCLASS_WEAPON_THROWN:
            default:
                return EMOTE_ONESHOT_ATTACK_THROWN;
        }
    }

    void PlayBrougSkirmisherFeedback(Player* player, Item const* item, uint32 impactSoundId)
    {
        if (!player || !player->IsInWorld())
            return;

        player->SetSheath(SHEATH_STATE_RANGED);
        player->HandleEmoteCommand(ResolveBrougRangedEmote(item));
        if (impactSoundId != 0)
            player->PlayDistanceSound(impactSoundId);
    }

    bool ResolveBrougUniversalParryRoll(
        Unit* attacker,
        Unit* victim,
        Player*& player,
        uint32& playerGuid,
        BrougGuardRuntimeState*& state)
    {
        player = nullptr;
        playerGuid = 0;
        state = nullptr;

        if (!IsBrougHostileDamage(attacker, victim))
            return false;

        player = victim->ToPlayer();
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return false;

        playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        if (stateIt == gBrougGuardByPlayer.end() || !stateIt->second.hasUniversalParry)
            return false;

        state = &stateIt->second;
        if (IsBrougDeflectWindowActive(*state, BrougNowMs()))
            return false;

        WmSpells::BrougUniversalParryConfig const& config = state->universalParry;
        float chancePct = ResolveBrougUniversalParryChance(player, attacker, config);
        return chancePct > 0.0f && roll_chance_f(chancePct);
    }

    void RecordBrougUniversalParrySuccess(
        Player* player,
        uint32 playerGuid,
        BrougGuardRuntimeState& state,
        Unit* attacker,
        bool countEvent)
    {
        if (countEvent)
        {
            RecordBrougGuardCounter(playerGuid, state.universalParry.counterKey, 1);
            CreditBrougQuestProgress(player, BROUG_PARRY_CREDIT_CREATURE_ENTRY);
        }
        TryBrougAutoRetaliation(player, attacker, state);
    }

    bool TryQueueBrougUniversalMeleeParry(Unit* attacker, Unit* victim, uint32 damage, bool countEvent)
    {
        if (damage == 0)
            return false;

        uint64 nowMs = BrougNowMs();
        if (victim)
        {
            auto existing = gBrougPendingForcedParryByVictim.find(victim->GetGUID());
            if (existing != gBrougPendingForcedParryByVictim.end())
            {
                if (existing->second.expiresAtMs >= nowMs && attacker && existing->second.attackerGuid == attacker->GetGUID())
                    return true;

                gBrougPendingForcedParryByVictim.erase(existing);
            }
        }

        Player* player = nullptr;
        uint32 playerGuid = 0;
        BrougGuardRuntimeState* state = nullptr;
        if (!ResolveBrougUniversalParryRoll(attacker, victim, player, playerGuid, state))
            return false;

        gBrougPendingForcedParryByVictim[victim->GetGUID()] = {attacker->GetGUID(), playerGuid, nowMs + 1000, countEvent};
        return true;
    }

    bool TryBrougUniversalParry(Unit* attacker, Unit* victim, uint32& damage, bool countEvent)
    {
        if (damage == 0)
            return false;

        Player* player = nullptr;
        uint32 playerGuid = 0;
        BrougGuardRuntimeState* state = nullptr;
        if (!ResolveBrougUniversalParryRoll(attacker, victim, player, playerGuid, state))
            return false;

        damage = 0;
        PlayBrougParryFeedback(player);
        RecordBrougUniversalParrySuccess(player, playerGuid, *state, attacker, countEvent);
        return true;
    }

    bool IsBrougRangedWeapon(Item const* item)
    {
        if (!item || !item->GetTemplate() || item->GetTemplate()->Class != ITEM_CLASS_WEAPON)
            return false;

        switch (item->GetTemplate()->SubClass)
        {
            case ITEM_SUBCLASS_WEAPON_BOW:
            case ITEM_SUBCLASS_WEAPON_GUN:
            case ITEM_SUBCLASS_WEAPON_THROWN:
            case ITEM_SUBCLASS_WEAPON_CROSSBOW:
                return true;
            default:
                return false;
        }
    }

    Unit* SelectBrougSkirmisherTarget(Player* player, WmSpells::BrougSkirmisherMarkConfig const& config, Unit* explicitTarget = nullptr)
    {
        if (!player)
            return nullptr;

        Unit* target = explicitTarget;
        if (!target)
            target = ObjectAccessor::GetUnit(*player, player->GetTarget());
        if (!target || !target->IsAlive() || !player->IsValidAttackTarget(target))
            target = player->GetVictim();
        if (!target || !target->IsAlive() || !player->IsValidAttackTarget(target))
            return nullptr;
        if (!player->IsWithinDistInMap(target, config.maxRangeYards) || !player->IsWithinLOSInMap(target))
            return nullptr;
        if (config.minRangeYards > 0.0f && player->GetDistance(target) < config.minRangeYards)
            return nullptr;

        return target;
    }

    uint32 ResolveBrougSkirmisherAttackIntervalMs(Player* player, WmSpells::BrougSkirmisherMarkConfig const& config)
    {
        if (!player)
            return config.minAttackIntervalMs;

        uint32 attackTime = player->GetAttackTime(RANGED_ATTACK);
        return std::clamp<uint32>(attackTime, config.minAttackIntervalMs, config.maxAttackIntervalMs);
    }

    bool IsBrougSkirmisherTargetReady(Player* player, Unit* target, WmSpells::BrougSkirmisherMarkConfig const& config, bool notify)
    {
        if (!player || !target || !target->IsAlive() || !player->IsValidAttackTarget(target))
            return false;

        if (!player->IsWithinLOSInMap(target))
            return false;

        if (!player->IsWithinDistInMap(target, config.maxRangeYards)
            || (config.minRangeYards > 0.0f && player->GetDistance(target) < config.minRangeYards))
        {
            if (notify)
                player->SendAttackSwingNotInRange();
            return false;
        }

        if (!player->HasInArc(WM_PI, target))
        {
            if (notify)
                player->SendAttackSwingBadFacingAttack();
            return false;
        }

        return true;
    }

    void FinalizeBrougSkirmisherDamageInfo(CalcDamageInfo& damageInfo)
    {
        if (!(damageInfo.HitInfo & HITINFO_MISS))
            damageInfo.HitInfo |= HITINFO_AFFECTS_VICTIM;

        uint32 tmpHitInfo[MAX_ITEM_PROTO_DAMAGES] = {};
        for (uint8 i = 0; i < MAX_ITEM_PROTO_DAMAGES; ++i)
        {
            Unit::DealDamageMods(damageInfo.target, damageInfo.damages[i].damage, &damageInfo.damages[i].absorb);
            if (damageInfo.damages[i].damage == 0)
                continue;

            damageInfo.procVictim |= PROC_FLAG_TAKEN_DAMAGE;
            DamageInfo wrapped(damageInfo, i);
            Unit::CalcAbsorbResist(wrapped);
            damageInfo.damages[i].absorb = wrapped.GetAbsorb();
            damageInfo.damages[i].resist = wrapped.GetResist();

            if (damageInfo.damages[i].absorb)
                tmpHitInfo[i] |= (damageInfo.damages[i].damage - damageInfo.damages[i].absorb == 0 ? HITINFO_FULL_ABSORB : HITINFO_PARTIAL_ABSORB);
            if (damageInfo.damages[i].resist)
                tmpHitInfo[i] |= (damageInfo.damages[i].damage - damageInfo.damages[i].resist == 0 ? HITINFO_FULL_RESIST : HITINFO_PARTIAL_RESIST);

            damageInfo.damages[i].damage = wrapped.GetDamage();
        }

        if ((tmpHitInfo[0] & HITINFO_FULL_ABSORB) != 0)
            damageInfo.HitInfo |= ((tmpHitInfo[1] & HITINFO_PARTIAL_ABSORB) != 0) ? HITINFO_PARTIAL_ABSORB : HITINFO_FULL_ABSORB;
        else
            damageInfo.HitInfo |= (tmpHitInfo[0] & HITINFO_PARTIAL_ABSORB);

        if ((tmpHitInfo[0] & HITINFO_FULL_RESIST) != 0)
            damageInfo.HitInfo |= ((tmpHitInfo[1] & HITINFO_PARTIAL_RESIST) != 0) ? HITINFO_PARTIAL_RESIST : HITINFO_FULL_RESIST;
        else
            damageInfo.HitInfo |= (tmpHitInfo[0] & HITINFO_PARTIAL_RESIST);
    }

    bool BuildBrougSkirmisherDamageInfo(Player* player, Unit* target, WmSpells::BrougSkirmisherMarkConfig const& config, CalcDamageInfo& damageInfo)
    {
        if (!player || !target)
            return false;

        damageInfo.attacker = player;
        damageInfo.target = target;
        damageInfo.blocked_amount = 0;
        damageInfo.HitInfo = 0;
        damageInfo.TargetState = 0;
        damageInfo.attackType = RANGED_ATTACK;
        damageInfo.procAttacker = PROC_FLAG_DONE_RANGED_AUTO_ATTACK;
        damageInfo.procVictim = PROC_FLAG_TAKEN_RANGED_AUTO_ATTACK;
        damageInfo.cleanDamage = 0;
        damageInfo.hitOutCome = MELEE_HIT_EVADE;

        for (uint8 i = 0; i < MAX_ITEM_PROTO_DAMAGES; ++i)
        {
            damageInfo.damages[i].damageSchoolMask = i == 0 ? player->GetMeleeDamageSchoolMask(RANGED_ATTACK, i) : SPELL_SCHOOL_MASK_NORMAL;
            damageInfo.damages[i].damage = 0;
            damageInfo.damages[i].absorb = 0;
            damageInfo.damages[i].resist = 0;
        }

        SpellSchoolMask schoolMask = SpellSchoolMask(damageInfo.damages[0].damageSchoolMask);
        if (target->IsImmunedToDamageOrSchool(schoolMask))
        {
            damageInfo.HitInfo |= HITINFO_NORMALSWING;
            damageInfo.TargetState = VICTIMSTATE_IS_IMMUNE;
            damageInfo.hitOutCome = MELEE_HIT_NORMAL;
            return true;
        }

        uint32 damage = player->CalculateDamage(RANGED_ATTACK, false, true, 1 << 0);
        damage = player->MeleeDamageBonusDone(target, damage, RANGED_ATTACK, nullptr, schoolMask);
        damage = target->MeleeDamageBonusTaken(player, damage, RANGED_ATTACK, nullptr, schoolMask);
        if (config.damagePct != 100)
            damage = std::max<uint32>(1u, (static_cast<uint64>(damage) * config.damagePct) / 100u);

        if (Unit::IsDamageReducedByArmor(schoolMask))
        {
            uint32 reduced = Unit::CalcArmorReducedDamage(player, target, damage, nullptr, 0, RANGED_ATTACK);
            damageInfo.cleanDamage += damage - reduced;
            damage = reduced;
        }

        damageInfo.damages[0].damage = damage;
        damageInfo.hitOutCome = player->RollMeleeOutcomeAgainst(target, RANGED_ATTACK);

        switch (damageInfo.hitOutCome)
        {
            case MELEE_HIT_EVADE:
                damageInfo.HitInfo |= HITINFO_MISS | HITINFO_SWINGNOHITSOUND;
                damageInfo.TargetState = VICTIMSTATE_EVADES;
                damageInfo.damages[0].damage = 0;
                damageInfo.cleanDamage = 0;
                return true;
            case MELEE_HIT_MISS:
                damageInfo.HitInfo |= HITINFO_MISS;
                damageInfo.TargetState = VICTIMSTATE_INTACT;
                damageInfo.damages[0].damage = 0;
                damageInfo.cleanDamage = 0;
                break;
            case MELEE_HIT_CRIT:
                damageInfo.HitInfo |= HITINFO_CRITICALHIT;
                damageInfo.TargetState = VICTIMSTATE_HIT;
                damageInfo.damages[0].damage *= 2;
                if (float mod = target->GetTotalAuraModifier(SPELL_AURA_MOD_ATTACKER_RANGED_CRIT_DAMAGE); mod != 0.0f)
                    AddPct(damageInfo.damages[0].damage, mod);
                break;
            case MELEE_HIT_PARRY:
                damageInfo.TargetState = VICTIMSTATE_PARRY;
                damageInfo.cleanDamage += damageInfo.damages[0].damage;
                damageInfo.damages[0].damage = 0;
                break;
            case MELEE_HIT_DODGE:
                damageInfo.TargetState = VICTIMSTATE_DODGE;
                damageInfo.cleanDamage += damageInfo.damages[0].damage;
                damageInfo.damages[0].damage = 0;
                break;
            case MELEE_HIT_BLOCK:
                damageInfo.TargetState = VICTIMSTATE_HIT;
                damageInfo.HitInfo |= HITINFO_BLOCK;
                damageInfo.blocked_amount = target->GetShieldBlockValue();
                damageInfo.cleanDamage += std::min(damageInfo.blocked_amount, damageInfo.damages[0].damage);
                if (damageInfo.blocked_amount >= damageInfo.damages[0].damage)
                {
                    damageInfo.blocked_amount = damageInfo.damages[0].damage;
                    damageInfo.damages[0].damage = 0;
                    damageInfo.TargetState = VICTIMSTATE_BLOCKS;
                }
                else
                {
                    damageInfo.damages[0].damage -= damageInfo.blocked_amount;
                }
                break;
            case MELEE_HIT_NORMAL:
            default:
                damageInfo.TargetState = VICTIMSTATE_HIT;
                break;
        }

        FinalizeBrougSkirmisherDamageInfo(damageInfo);
        return true;
    }

    bool FireBrougSkirmisherShot(Player* player, Unit* target, BrougGuardRuntimeState& state)
    {
        if (!player || !target || !state.hasSkirmisherMark)
            return false;

        WmSpells::BrougSkirmisherMarkConfig const& config = state.skirmisherMark;
        Item* rangedItem = player->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_RANGED);
        if (!IsBrougRangedWeapon(rangedItem) || !player->HasRangedWeaponForAttack())
            return false;
        if (!IsBrougSkirmisherTargetReady(player, target, config, true))
            return false;

        CalcDamageInfo damageInfo;
        if (!BuildBrougSkirmisherDamageInfo(player, target, config, damageInfo))
            return false;

        TryConsumeBrougMarkedMeridian(player, target, damageInfo.damages[0].damage);
        PlayBrougSkirmisherFeedback(player, rangedItem, config.impactSoundId);
        player->SendAttackStateUpdate(&damageInfo);
        player->DealMeleeDamage(&damageInfo, true);

        DamageInfo procDamageInfo(damageInfo);
        Unit::ProcSkillsAndAuras(
            damageInfo.attacker,
            damageInfo.target,
            damageInfo.procAttacker,
            damageInfo.procVictim,
            procDamageInfo.GetHitMask(),
            procDamageInfo.GetDamage(),
            damageInfo.attackType,
            nullptr,
            nullptr,
            -1,
            nullptr,
            &procDamageInfo);

        RecordBrougGuardCounter(static_cast<uint32>(player->GetGUID().GetCounter()), config.counterKey, 1);
        return true;
    }

    uint64 BrougNowMs()
    {
        return static_cast<uint64>(GameTime::GetGameTimeMS().count());
    }

    uint32 ResolveBrougStrikeBackDamage(Player* player, uint32 baseDamage, uint32 weaponDamagePct, uint32 attackPowerPct)
    {
        if (!player)
            return 0;

        float minDamage = player->GetWeaponDamageRange(BASE_ATTACK, MINDAMAGE);
        float maxDamage = player->GetWeaponDamageRange(BASE_ATTACK, MAXDAMAGE);
        float weaponRoll = std::max(0.0f, frand(std::min(minDamage, maxDamage), std::max(minDamage, maxDamage)));
        float attackPower = ResolveBrougAttackPower(player, false);
        float damage = static_cast<float>(baseDamage)
            + weaponRoll * (static_cast<float>(weaponDamagePct) / 100.0f)
            + attackPower * (static_cast<float>(attackPowerPct) / 100.0f);
        return std::max<uint32>(1u, static_cast<uint32>(std::round(damage)));
    }

    void DealBrougStrikeBackDamage(Player* player, Unit* target, uint32 damage, uint32 visualSpellId)
    {
        if (!player || !target || damage == 0 || !target->IsAlive())
            return;

        ConsumeBrougVulnerableForDamage(player, target, damage);
        if (damage == 0)
            return;

        SpellInfo const* spellInfo = visualSpellId != 0 ? sSpellMgr->GetSpellInfo(visualSpellId) : nullptr;
        if (spellInfo)
            player->SendSpellNonMeleeDamageLog(target, spellInfo, damage, SPELL_SCHOOL_MASK_NORMAL, 0, 0, true, 0, false);

        Unit::DealDamage(player, target, damage, nullptr, DIRECT_DAMAGE, SPELL_SCHOOL_MASK_NORMAL, spellInfo, true);
    }

    Aura* ApplyBrougVisibleAura(Player* player, Unit* target, uint32 spellId)
    {
        if (!player || !target || spellId == 0)
            return nullptr;

        if (Aura* aura = target->GetAura(spellId, player->GetGUID()))
            return aura;

        if (Aura* aura = player->AddAura(spellId, target))
            return aura;

        // Deflect marker auras are gameplay-owned visible state. If the target is
        // spell-immune, still create the harmless marker while native owns effects.
        SpellInfo const* spellInfo = sSpellMgr->GetSpellInfo(spellId);
        if (!spellInfo)
            return nullptr;

        Aura* aura = Aura::TryCreate(spellInfo, MAX_EFFECT_MASK, target, player);
        if (aura)
            aura->ApplyForTargets();
        return aura;
    }

    Aura* ApplyBrougTimedVisibleAura(Player* player, Unit* target, uint32 spellId, uint32 durationMs)
    {
        if (!player || !target || spellId == 0 || durationMs == 0 || !target->IsAlive())
            return nullptr;

        Aura* aura = ApplyBrougVisibleAura(player, target, spellId);
        if (!aura)
            return nullptr;

        aura->SetStackAmount(1);
        int32 duration = static_cast<int32>(std::min<uint32>(durationMs, static_cast<uint32>(std::numeric_limits<int32>::max())));
        aura->SetMaxDuration(duration);
        aura->SetDuration(duration);
        return aura;
    }

    bool IsBrougMarkedMeridianStateActive(BrougLightnessRuntimeState const& state, Unit const* victim, uint64 nowMs)
    {
        return state.hasCloudStep
            && victim
            && state.markedMeridianTargetGuid != ObjectGuid::Empty
            && state.markedMeridianTargetGuid == victim->GetGUID()
            && state.markedMeridianUntilMs >= nowMs;
    }

    void ClearBrougMarkedMeridianState(BrougLightnessRuntimeState& state)
    {
        state.markedMeridianTargetGuid = ObjectGuid::Empty;
        state.markedMeridianUntilMs = 0;
    }

    void PlayBrougCloudStepVisual(Player* player, uint32 visualSpellId)
    {
        if (!player || visualSpellId == 0 || !player->IsInWorld())
            return;

        player->CastSpell(player, visualSpellId, true);
    }

    bool HasBrougLightnessMarkReady(Unit* attacker, Unit* victim)
    {
        Player* player = attacker ? attacker->ToPlayer() : nullptr;
        if (!player || !victim || !WmSpells::IsPlayerAllowed(player))
            return false;

        uint64 nowMs = BrougNowMs();
        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        if (auto stateIt = gBrougLightnessByPlayer.find(playerGuid); stateIt != gBrougLightnessByPlayer.end())
        {
            if (IsBrougMarkedMeridianStateActive(stateIt->second, victim, nowMs))
                return true;
            if (stateIt->second.markedMeridianUntilMs != 0 && stateIt->second.markedMeridianUntilMs < nowMs)
                ClearBrougMarkedMeridianState(stateIt->second);
        }

        if (victim->HasAura(BROUG_MARKED_MERIDIAN_SHELL_ID))
            return true;

        auto preserveIt = gBrougLightnessPreserveVulnerableByVictim.find(victim->GetGUID());
        if (preserveIt == gBrougLightnessPreserveVulnerableByVictim.end())
            return false;

        if (preserveIt->second < nowMs)
        {
            gBrougLightnessPreserveVulnerableByVictim.erase(preserveIt);
            return false;
        }

        return true;
    }

    BrougEmptyCourtRuntimeState* EnsureBrougEmptyCourtState(Player* player, uint32 playerGuid)
    {
        if (!player || playerGuid == 0)
            return nullptr;

        auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid);
        BrougEmptyCourtRuntimeState const* previousState = stateIt != gBrougEmptyCourtByPlayer.end() ? &stateIt->second : nullptr;
        std::optional<BrougEmptyCourtRuntimeState> loaded = LoadActiveBrougEmptyCourtState(player, previousState);
        if (!loaded.has_value())
        {
            gBrougEmptyCourtByPlayer.erase(playerGuid);
            return nullptr;
        }

        gBrougEmptyCourtByPlayer[playerGuid] = *loaded;
        return &gBrougEmptyCourtByPlayer[playerGuid];
    }

    bool HasActiveBrougEmptyCourtDomain(Player* player, uint32 playerGuid)
    {
        if (!player || playerGuid == 0)
            return false;

        auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid);
        if (stateIt != gBrougEmptyCourtByPlayer.end() && stateIt->second.hasDomain)
            return true;

        BrougEmptyCourtRuntimeState* state = EnsureBrougEmptyCourtState(player, playerGuid);
        return state && state->hasDomain;
    }

    uint32 ResolveBrougKillingIntentDurationMs(Player* player, uint32 playerGuid, uint32 fallbackDurationMs)
    {
        auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid);
        BrougEmptyCourtRuntimeState* state = stateIt != gBrougEmptyCourtByPlayer.end()
            ? &stateIt->second
            : EnsureBrougEmptyCourtState(player, playerGuid);
        if (!state || !state->hasDomain)
            return fallbackDurationMs;

        return std::max<uint32>(fallbackDurationMs, state->domain.baseKillingIntentDurationMs);
    }

    void ApplyBrougHeal(Player* player, uint32 amount)
    {
        if (!player || amount == 0 || !player->IsAlive() || player->IsFullHealth())
            return;

        uint32 missing = player->GetMaxHealth() > player->GetHealth() ? player->GetMaxHealth() - player->GetHealth() : 0;
        if (missing == 0)
            return;

        uint32 heal = std::min<uint32>(amount, missing);
        player->ModifyHealth(static_cast<int32>(std::min<uint32>(heal, static_cast<uint32>(std::numeric_limits<int32>::max()))));
    }

    void ApplyBrougPredatorHeal(Player* player, uint32 playerGuid, uint32 damage)
    {
        if (!player || playerGuid == 0 || damage == 0)
            return;

        auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid);
        BrougEmptyCourtRuntimeState* state = stateIt != gBrougEmptyCourtByPlayer.end()
            ? &stateIt->second
            : EnsureBrougEmptyCourtState(player, playerGuid);
        if (!state || !state->hasPredatorsStrike || state->predatorsStrike.healPctOfDamage == 0)
            return;

        uint64 heal = (static_cast<uint64>(damage) * static_cast<uint64>(state->predatorsStrike.healPctOfDamage)) / 100u;
        uint32 cappedHeal = static_cast<uint32>(std::min<uint64>(heal, std::numeric_limits<uint32>::max()));
        ApplyBrougHeal(player, cappedHeal);
        RecordBrougEmptyCourtCounter(playerGuid, state->predatorsStrike.counterKey, 1);
    }

    bool TryConsumeBrougMarkedMeridian(Player* player, Unit* target, uint32& damage)
    {
        if (!player || !target || damage == 0 || !target->IsAlive() || !WmSpells::IsPlayerAllowed(player))
            return false;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougLightnessByPlayer.find(playerGuid);
        if (stateIt == gBrougLightnessByPlayer.end() || !stateIt->second.hasCloudStep)
        {
            std::optional<BrougLightnessRuntimeState> loaded = LoadActiveBrougLightnessState(player, nullptr);
            if (loaded.has_value())
            {
                gBrougLightnessByPlayer[playerGuid] = *loaded;
                stateIt = gBrougLightnessByPlayer.find(playerGuid);
            }
        }
        if (stateIt == gBrougLightnessByPlayer.end() || !stateIt->second.hasCloudStep)
            return false;

        BrougLightnessRuntimeState& state = stateIt->second;
        WmSpells::BrougCloudStepConfig const& config = state.cloudStep;
        uint64 nowMs = BrougNowMs();
        bool stateMarkActive = IsBrougMarkedMeridianStateActive(state, target, nowMs);
        if (!stateMarkActive && state.markedMeridianUntilMs != 0 && state.markedMeridianUntilMs < nowMs)
            ClearBrougMarkedMeridianState(state);

        Aura* mark = target->GetAura(config.markedMeridianSpellId, player->GetGUID());
        if (!mark && config.markedMeridianSpellId == BROUG_MARKED_MERIDIAN_SHELL_ID)
            mark = target->GetAura(BROUG_MARKED_MERIDIAN_SHELL_ID, player->GetGUID());

        if (!stateMarkActive && !mark)
            return false;
        if (state.markedMeridianTargetGuid != ObjectGuid::Empty && state.markedMeridianTargetGuid != target->GetGUID())
            return false;
        if (config.damageBonusPct > 0)
        {
            uint64 scaledDamage = static_cast<uint64>(damage)
                + (static_cast<uint64>(damage) * static_cast<uint64>(config.damageBonusPct)) / 100u;
            damage = static_cast<uint32>(std::min<uint64>(scaledDamage, std::numeric_limits<uint32>::max()));
        }

        gBrougLightnessPreserveVulnerableByVictim[target->GetGUID()] = nowMs + 1000u;
        if (mark)
            mark->Remove(AURA_REMOVE_BY_DEFAULT);
        target->RemoveAurasDueToSpell(config.markedMeridianSpellId);
        if (config.killingIntentSpellId != 0 && !HasActiveBrougEmptyCourtDomain(player, playerGuid))
            player->RemoveAurasDueToSpell(config.killingIntentSpellId);
        ClearBrougMarkedMeridianState(state);
        RecordBrougLightnessCounter(playerGuid, config.counterKey, 1);
        ApplyBrougPredatorHeal(player, playerGuid, damage);
        CreditBrougQuestProgress(player, config.creditCreatureEntry);
        ChatHandler(player->GetSession()).PSendSysMessage(
            "WM Broug: Marked Meridian consumed (+{}%).",
            config.damageBonusPct);
        return true;
    }

    bool ResolveBrougCloudStepLanding(Player* player, Unit* target, WmSpells::BrougCloudStepConfig const& config, Position& landing)
    {
        if (!player || !target || !target->IsInWorld() || target->GetMapId() != player->GetMapId())
            return false;

        Map* map = player->GetMap();
        if (!map)
            return false;

        float const targetOrientation = target->GetOrientation();
        float const angles[] = {
            targetOrientation + WM_PI,
            targetOrientation + (WM_PI * 0.5f),
            targetOrientation - (WM_PI * 0.5f),
        };

        for (float angle : angles)
        {
            float x = target->GetPositionX();
            float y = target->GetPositionY();
            float z = target->GetPositionZ();
            target->GetClosePoint(
                x,
                y,
                z,
                player->GetCombatReach(),
                std::max(0.5f, config.landingDistanceYards),
                angle);
            player->UpdateAllowedPositionZ(x, y, z);
            if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z))
                continue;
            if (!map->CanReachPositionAndGetValidCoords(player, x, y, z, true, true))
                continue;

            landing.Relocate(x, y, z, std::atan2(target->GetPositionY() - y, target->GetPositionX() - x));
            return true;
        }

        return false;
    }

    Unit* SelectBrougCloudStepTarget(Player* player, WmSpells::BrougCloudStepConfig const& config, Unit* explicitTarget = nullptr)
    {
        if (!player)
            return nullptr;

        Unit* target = explicitTarget;
        if (!target)
            target = ObjectAccessor::GetUnit(*player, player->GetTarget());
        if (!target || !target->IsAlive() || !player->IsValidAttackTarget(target))
            target = player->GetVictim();
        if (!target || !target->IsAlive() || !player->IsValidAttackTarget(target))
            return nullptr;
        if (!player->IsWithinLOSInMap(target))
            return nullptr;
        if (!player->IsWithinDistInMap(target, config.maxRangeYards))
            return nullptr;
        return target;
    }

    bool HasBrougDeflectedAura(Unit* target)
    {
        return target && target->HasAura(BROUG_DEFLECTED_SHELL_ID);
    }

    void RestartBrougStunnedCreature(Unit* target)
    {
        if (!target)
            return;

        if (!target->IsAlive() || target->HasUnitState(UNIT_STATE_STUNNED))
            return;

        if (Creature* creature = target->ToCreature())
        {
            Unit* victim = creature->GetVictim();
            if (!victim)
                victim = creature->SelectVictim();

            if (victim)
            {
                creature->SetTarget(victim->GetGUID());
                if (creature->AI())
                    creature->AI()->AttackStart(victim);
            }
        }
    }

    void EnsureBrougDeflectedStun(Player* player, Unit* target)
    {
        if (!target || !target->IsAlive() || !HasBrougDeflectedAura(target))
            return;

        if (!target->HasUnitState(UNIT_STATE_STUNNED))
            target->SetControlled(true, UNIT_STATE_STUNNED, player);

        target->CastStop();
        if (target->HasUnitState(UNIT_STATE_MOVING))
            target->StopMoving();

        gBrougDeflectedStunUnits.insert(target->GetGUID());
    }

    void ReleaseBrougForcedStun(Unit* target)
    {
        if (!target || HasBrougDeflectedAura(target))
            return;

        target->SetControlled(false, UNIT_STATE_STUNNED);
        RestartBrougStunnedCreature(target);
    }

    Aura* ApplyBrougDeflectedStacks(Player* player, Unit* target, uint32 deflectedSpellId, uint32 stacks, uint32 durationMs)
    {
        if (!player || !target || deflectedSpellId == 0 || stacks == 0 || durationMs == 0 || !target->IsAlive())
            return nullptr;

        Aura* aura = target->GetAura(deflectedSpellId, player->GetGUID());
        bool newlyApplied = false;
        if (!aura)
        {
            aura = ApplyBrougVisibleAura(player, target, deflectedSpellId);
            newlyApplied = aura != nullptr;
        }
        if (!aura)
            return nullptr;

        uint32 currentStacks = newlyApplied ? 0u : aura->GetStackAmount();
        uint8 nextStacks = static_cast<uint8>(std::min<uint32>(255u, currentStacks + stacks));
        aura->SetStackAmount(nextStacks);

        int32 duration = static_cast<int32>(std::min<uint32>(durationMs, static_cast<uint32>(std::numeric_limits<int32>::max())));
        duration = std::max<int32>(duration, aura->GetDuration());
        aura->SetMaxDuration(duration);
        aura->SetDuration(duration);
        return aura;
    }

    void ApplyBrougForcedStun(Player* player, Unit* target, uint32 stunMs, uint32 deflectedSpellId, uint32 deflectedStacks)
    {
        if (!player || !target || stunMs == 0 || !target->IsAlive())
            return;

        Aura* aura = ApplyBrougDeflectedStacks(player, target, deflectedSpellId, deflectedStacks, stunMs);
        if (!aura)
            return;

        EnsureBrougDeflectedStun(player, target);
    }

    bool ResolveBrougVulnerableCaster(Aura* aura, Player*& player, BrougGuardRuntimeState*& state)
    {
        player = nullptr;
        state = nullptr;
        if (!aura)
            return false;

        Unit* caster = aura->GetCaster();
        player = caster ? caster->ToPlayer() : nullptr;
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return false;

        auto stateIt = gBrougGuardByPlayer.find(static_cast<uint32>(player->GetGUID().GetCounter()));
        if (stateIt != gBrougGuardByPlayer.end() && stateIt->second.hasDeflect)
            state = &stateIt->second;
        return true;
    }

    void ConsumeBrougVulnerableForDamage(Unit* attacker, Unit* victim, uint32& damage)
    {
        if (!victim || damage == 0)
            return;

        if (HasBrougLightnessMarkReady(attacker, victim))
            return;

        Aura* aura = victim->GetAura(BROUG_VULNERABLE_SHELL_ID);
        if (!aura)
            return;

        Player* broug = nullptr;
        BrougGuardRuntimeState* state = nullptr;
        if (!ResolveBrougVulnerableCaster(aura, broug, state))
            return;

        uint32 stacks = std::max<uint32>(1u, aura->GetStackAmount());
        uint32 stunMsPerStack = state ? state->deflect.stunMs : 1000u;
        uint32 deflectedSpellId = state ? state->deflect.deflectedSpellId : BROUG_DEFLECTED_SHELL_ID;
        uint64 scaledDamage = static_cast<uint64>(damage) * static_cast<uint64>(1u + stacks);
        damage = static_cast<uint32>(std::min<uint64>(scaledDamage, std::numeric_limits<uint32>::max()));

        aura->Remove(AURA_REMOVE_BY_DEFAULT);
        uint64 stunDuration = static_cast<uint64>(stunMsPerStack) * static_cast<uint64>(stacks);
        ApplyBrougForcedStun(
            broug,
            victim,
            static_cast<uint32>(std::min<uint64>(stunDuration, std::numeric_limits<uint32>::max())),
            deflectedSpellId,
            stacks);
    }

    void UpdateBrougForcedStuns(Player* player)
    {
        if (!player || gBrougDeflectedStunUnits.empty())
            return;

        for (auto it = gBrougDeflectedStunUnits.begin(); it != gBrougDeflectedStunUnits.end();)
        {
            Unit* unit = ObjectAccessor::GetUnit(*player, *it);
            if (!unit)
            {
                it = gBrougDeflectedStunUnits.erase(it);
                continue;
            }

            if (HasBrougDeflectedAura(unit))
            {
                EnsureBrougDeflectedStun(player, unit);
                ++it;
                continue;
            }

            ReleaseBrougForcedStun(unit);
            it = gBrougDeflectedStunUnits.erase(it);
        }
    }

    void CreditBrougQuestProgress(Player* player, uint32 creditCreatureEntry)
    {
        if (!player || creditCreatureEntry == 0)
            return;

        player->KilledMonsterCredit(creditCreatureEntry);
    }

    void TryBrougAutoRetaliation(Player* player, Unit* target, BrougGuardRuntimeState& state)
    {
        if (!player || !target || !state.hasAutoRetaliation || !target->IsAlive())
            return;

        uint64 nowMs = BrougNowMs();
        if (state.autoRetaliationCooldownUntilMs > nowMs)
            return;

        WmSpells::BrougAutoRetaliationConfig const& config = state.autoRetaliation;
        state.autoRetaliationCooldownUntilMs = nowMs + static_cast<uint64>(config.cooldownMs);
        uint32 damage = ResolveBrougStrikeBackDamage(player, config.baseDamage, config.weaponDamagePct, config.attackPowerPct);
        DealBrougStrikeBackDamage(player, target, damage, config.visualSpellId);
        RecordBrougGuardCounter(static_cast<uint32>(player->GetGUID().GetCounter()), config.counterKey, 1);
    }

    void ApplyBrougVulnerableStack(Player* player, Unit* target, WmSpells::BrougDeflectConfig const& config)
    {
        if (!player || !target || !target->IsAlive() || config.vulnerableSpellId == 0)
            return;

        Aura* aura = target->GetAura(config.vulnerableSpellId, player->GetGUID());
        bool newlyApplied = false;
        if (!aura)
        {
            aura = ApplyBrougVisibleAura(player, target, config.vulnerableSpellId);
            newlyApplied = aura != nullptr;
        }
        if (!aura)
            return;

        uint32 currentStacks = newlyApplied ? 0u : aura->GetStackAmount();
        uint32 cappedStacks = std::min<uint32>(config.maxVulnerableStacks, currentStacks + 1u);
        aura->SetStackAmount(static_cast<uint8>(std::min<uint32>(255u, cappedStacks)));
        int32 duration = static_cast<int32>(std::min<uint32>(config.vulnerableDurationMs, static_cast<uint32>(std::numeric_limits<int32>::max())));
        aura->SetMaxDuration(duration);
        aura->SetDuration(duration);
    }

    void CaptureBrougDeflectEvent(Player* player, uint32 playerGuid, BrougGuardRuntimeState& state, Unit* attacker)
    {
        if (!player || !attacker || !attacker->IsAlive())
            return;

        WmSpells::BrougDeflectConfig const& config = state.deflect;
        ApplyBrougVulnerableStack(player, attacker, config);
        ObjectGuid attackerGuid = attacker->GetGUID();
        uint32& caughtStacks = state.deflectCaughtStacksByAttacker[attackerGuid];
        if (caughtStacks < config.maxVulnerableStacks)
            ++caughtStacks;

        if (state.deflectPrimaryAttackerGuid == ObjectGuid::Empty)
        {
            state.deflectPrimaryAttackerGuid = attackerGuid;
            state.deflectPendingResolveAtMs = state.deflectWindowUntilMs;
            state.deflectPendingDamage = ResolveBrougStrikeBackDamage(player, config.baseDamage, config.weaponDamagePct, config.attackPowerPct);
        }

        RecordBrougGuardCounter(playerGuid, config.counterKey, 1);
        CreditBrougQuestProgress(player, BROUG_DEFLECT_CREDIT_CREATURE_ENTRY);
    }

    Unit* ResolveBrougDeflectCounterTarget(Player* player, BrougGuardRuntimeState& state)
    {
        if (!player)
            return nullptr;

        if (state.deflectPrimaryAttackerGuid != ObjectGuid::Empty)
        {
            if (Unit* primary = ObjectAccessor::GetUnit(*player, state.deflectPrimaryAttackerGuid))
                if (primary->IsAlive())
                    return primary;
        }

        for (auto const& caught : state.deflectCaughtStacksByAttacker)
        {
            if (Unit* unit = ObjectAccessor::GetUnit(*player, caught.first))
                if (unit->IsAlive())
                    return unit;
        }

        return nullptr;
    }

    bool IsBrougDeflectCounterStanceActive(Player const* player)
    {
        return player && player->HasAura(BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID);
    }

    void ResolveBrougPendingDeflect(Player* player, BrougGuardRuntimeState& state)
    {
        if (!player || state.deflectPendingResolveAtMs == 0)
            return;

        uint64 nowMs = BrougNowMs();
        if (state.deflectPendingResolveAtMs > nowMs)
            return;

        uint32 reflectedDamage = state.deflectPendingDamage;
        bool counterattackEnabled = IsBrougDeflectCounterStanceActive(player);
        Unit* attacker = counterattackEnabled ? ResolveBrougDeflectCounterTarget(player, state) : nullptr;
        ClearBrougPendingDeflect(state);
        state.deflectWindowUntilMs = 0;

        if (!counterattackEnabled)
            return;

        if (!attacker || !attacker->IsAlive())
            return;

        DealBrougDeflectCounterDamage(player, attacker, reflectedDamage);
    }

    void TickBrougDeflectWindow(Player* player, BrougGuardRuntimeState& state)
    {
        uint64 nowMs = BrougNowMs();
        if (state.deflectParryFeedbackAtMs != 0
            && !state.deflectParryFeedbackPlayed
            && state.deflectParryFeedbackAtMs <= nowMs)
        {
            PlayBrougParryFeedback(player);
            state.deflectParryFeedbackPlayed = true;
        }

        ResolveBrougPendingDeflect(player, state);

        if (state.deflectRootUntilMs != 0 && state.deflectRootUntilMs <= nowMs && player)
        {
            player->SetControlled(false, UNIT_STATE_ROOT);
            state.deflectRootUntilMs = 0;
        }

        if (state.deflectPendingResolveAtMs == 0
            && state.deflectWindowUntilMs != 0
            && state.deflectWindowUntilMs < nowMs)
        {
            state.deflectWindowUntilMs = 0;
            state.deflectParryFeedbackAtMs = 0;
            state.deflectParryFeedbackPlayed = false;
        }
    }

    bool TryBrougDeflect(Unit* attacker, Unit* victim, uint32& damage)
    {
        if (damage == 0 || !IsBrougHostileDamage(attacker, victim))
            return false;

        Player* player = victim->ToPlayer();
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return false;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        if (stateIt == gBrougGuardByPlayer.end() || !stateIt->second.hasDeflect)
            return false;

        BrougGuardRuntimeState& state = stateIt->second;
        uint64 nowMs = BrougNowMs();
        if (state.deflectWindowUntilMs == 0 || state.deflectWindowUntilMs < nowMs)
            return false;

        WmSpells::BrougDeflectConfig const& config = state.deflect;
        state.deflectCooldownUntilMs = std::max(state.deflectCooldownUntilMs, nowMs + static_cast<uint64>(config.cooldownMs));
        damage = 0;
        CaptureBrougDeflectEvent(player, playerGuid, state, attacker);
        return true;
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

    uint16 ResolveCombatProficiencySkillMax(Player* player, CombatProficiencyRuntimeGrant const& grant)
    {
        if (!player)
            return 1;

        if (grant.scalesWithLevel)
            return std::max<uint16>(1, player->GetMaxSkillValueForLevel());

        return 1;
    }

    void EnsureCombatProficiencyRuntimeGrant(Player* player, CombatProficiencyRuntimeGrant const& grant)
    {
        if (!player || grant.skillId == 0 || grant.spellId == 0)
            return;

        if (player->GetLevel() < grant.minPlayerLevel)
            return;

        if (!player->HasSpell(grant.spellId))
            player->learnSpell(grant.spellId, false);

        uint16 targetMax = ResolveCombatProficiencySkillMax(player, grant);
        uint16 currentValue = player->HasSkill(grant.skillId) ? player->GetPureSkillValue(grant.skillId) : 0;
        uint16 currentMax = player->HasSkill(grant.skillId) ? player->GetPureMaxSkillValue(grant.skillId) : 0;
        if (player->HasSkill(grant.skillId) && currentValue >= 1 && currentMax >= targetMax)
            return;

        uint16 targetValue = std::max<uint16>(1, currentValue);
        targetMax = std::max<uint16>(targetMax, currentMax);
        player->SetSkill(static_cast<uint16>(grant.skillId), player->GetSkillStep(static_cast<uint16>(grant.skillId)), targetValue, targetMax);
    }

    bool IsNightWatchersLensEquipped(Player* player)
    {
        if (!player)
            return false;

        Item* headItem = player->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_HEAD);
        if (!headItem || !headItem->GetTemplate())
            return false;

        uint32 itemEntry = headItem->GetTemplate()->ItemId;
        return itemEntry == NIGHT_WATCHERS_LENS_ITEM_ENTRY || itemEntry == SHADOWMOON_WATCHERS_LENS_ITEM_ENTRY;
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
            || IsBrougGuardBehaviorKind(behaviorKind)
            || IsBrougLightnessBehaviorKind(behaviorKind)
            || IsBrougEmptyCourtBehaviorKind(behaviorKind)
            || IsBoneboundEchoModeBehaviorKind(behaviorKind)
            || IsBoneboundEchoStasisBehaviorKind(behaviorKind)
            || IsLanathelStanceBehaviorKind(behaviorKind);
    }

    bool ShouldAllowShellDefaultEffect(Player const* player, uint32 spellId, uint8 effIndex)
    {
        if (spellId != BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID || effIndex != 0 || !player)
            return false;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        return gBrougCounterStanceToggleOffByPlayer.find(playerGuid) == gBrougCounterStanceToggleOffByPlayer.end();
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

    SpellCastResult CheckShellCast(Player* player, uint32 shellSpellId, Unit* explicitTarget)
    {
        if (!player)
            return SPELL_FAILED_CASTER_DEAD;

        if (!IsPlayerAllowed(player))
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        if (IsBoneboundBehaviorKind(behaviorRecord->behaviorKind) && !gConfig.boneboundServantEnabled)
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

        if (IsLanathelStanceBehaviorKind(behaviorRecord->behaviorKind))
            return BuildLanathelStanceConfig(*behaviorRecord).has_value()
                ? SPELL_CAST_OK
                : SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

        if (IsIntellectBlockBehaviorKind(behaviorRecord->behaviorKind))
            return SPELL_CAST_OK;

        if (behaviorRecord->behaviorKind == "broug_skirmisher_shot_v1")
        {
            uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
            auto stateIt = gBrougGuardByPlayer.find(playerGuid);
            BrougGuardRuntimeState const* previousState = stateIt != gBrougGuardByPlayer.end() ? &stateIt->second : nullptr;
            std::optional<BrougGuardRuntimeState> loaded = LoadActiveBrougGuardState(player, previousState);
            if (!loaded.has_value() || !loaded->hasSkirmisherMark)
                return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

            gBrougGuardByPlayer[playerGuid] = *loaded;
            BrougGuardRuntimeState const& state = gBrougGuardByPlayer[playerGuid];
            if (state.skirmisherAttackTimerMs > 0)
                return SPELL_FAILED_NOT_READY;

            Item* rangedItem = player->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_RANGED);
            if (!IsBrougRangedWeapon(rangedItem) || !player->HasRangedWeaponForAttack())
                return SPELL_FAILED_EQUIPPED_ITEM;

            Unit* target = SelectBrougSkirmisherTarget(player, state.skirmisherMark, explicitTarget);
            return target ? SPELL_CAST_OK : SPELL_FAILED_BAD_TARGETS;
        }

        if (behaviorRecord->behaviorKind == "broug_deflect_v1")
        {
            uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
            auto stateIt = gBrougGuardByPlayer.find(playerGuid);
            BrougGuardRuntimeState const* previousState = stateIt != gBrougGuardByPlayer.end() ? &stateIt->second : nullptr;
            std::optional<BrougGuardRuntimeState> loaded = LoadActiveBrougGuardState(player, previousState);
            if (!loaded.has_value() || !loaded->hasDeflect)
                return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

            gBrougGuardByPlayer[playerGuid] = *loaded;
            BrougGuardRuntimeState const& state = gBrougGuardByPlayer[playerGuid];
            uint64 nowMs = BrougNowMs();
            if (state.deflectCooldownUntilMs > nowMs)
                return SPELL_FAILED_NOT_READY;
            if (state.deflect.energyCost > 0 && player->GetPower(POWER_ENERGY) < state.deflect.energyCost)
                return SPELL_FAILED_NO_POWER;
            return SPELL_CAST_OK;
        }

        if (behaviorRecord->behaviorKind == "broug_deflect_counter_stance_v1")
        {
            uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
            auto stateIt = gBrougGuardByPlayer.find(playerGuid);
            BrougGuardRuntimeState const* previousState = stateIt != gBrougGuardByPlayer.end() ? &stateIt->second : nullptr;
            std::optional<BrougGuardRuntimeState> loaded = LoadActiveBrougGuardState(player, previousState);
            if (!loaded.has_value() || !loaded->hasDeflect || !loaded->hasDeflectCounterStance)
                return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

            gBrougGuardByPlayer[playerGuid] = *loaded;
            if (IsBrougDeflectCounterStanceActive(player))
                gBrougCounterStanceToggleOffByPlayer.insert(playerGuid);
            else
                gBrougCounterStanceToggleOffByPlayer.erase(playerGuid);
            return SPELL_CAST_OK;
        }

        if (behaviorRecord->behaviorKind == "broug_cloud_step_v1")
        {
            uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
            auto stateIt = gBrougLightnessByPlayer.find(playerGuid);
            BrougLightnessRuntimeState const* previousState = stateIt != gBrougLightnessByPlayer.end() ? &stateIt->second : nullptr;
            std::optional<BrougLightnessRuntimeState> loaded = LoadActiveBrougLightnessState(player, previousState);
            if (!loaded.has_value() || !loaded->hasCloudStep)
                return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

            gBrougLightnessByPlayer[playerGuid] = *loaded;
            BrougLightnessRuntimeState const& state = gBrougLightnessByPlayer[playerGuid];
            uint64 nowMs = BrougNowMs();
            if (state.cloudStepCooldownUntilMs > nowMs)
                return SPELL_FAILED_NOT_READY;
            if (state.cloudStep.energyCost > 0 && player->GetPower(POWER_ENERGY) < state.cloudStep.energyCost)
                return SPELL_FAILED_NO_POWER;
            if (player->HasUnitState(UNIT_STATE_ROOT) || player->HasUnitState(UNIT_STATE_STUNNED) || player->HasUnitState(UNIT_STATE_CONTROLLED))
                return SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;

            Unit* target = SelectBrougCloudStepTarget(player, state.cloudStep, explicitTarget);
            if (!target)
                return SPELL_FAILED_BAD_TARGETS;

            Position landing;
            return ResolveBrougCloudStepLanding(player, target, state.cloudStep, landing)
                ? SPELL_CAST_OK
                : SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;
        }

        if (behaviorRecord->behaviorKind == "broug_qi_reversal_v1")
        {
            uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
            BrougEmptyCourtRuntimeState* state = EnsureBrougEmptyCourtState(player, playerGuid);
            return state && state->hasQiReversal ? SPELL_CAST_OK : SPELL_FAILED_CANT_DO_THAT_RIGHT_NOW;
        }

        if (IsBrougGuardBehaviorKind(behaviorRecord->behaviorKind))
            return SPELL_CAST_OK;

        if (IsBrougLightnessBehaviorKind(behaviorRecord->behaviorKind))
            return SPELL_CAST_OK;

        if (IsBrougEmptyCourtBehaviorKind(behaviorRecord->behaviorKind))
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

    BehaviorExecutionResult ExecuteLanathelStance(Player* player, uint32 shellSpellId)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return {false, "shell_behavior_missing"};
        std::optional<LanathelStanceConfig> stanceConfig = BuildLanathelStanceConfig(*behaviorRecord);
        if (!stanceConfig.has_value())
            return {false, "lanathel_stance_disabled"};

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        bool active = gLanathelStanceByPlayer.find(playerGuid) != gLanathelStanceByPlayer.end()
            || LoadStoredLanathelStanceShell(playerGuid).has_value();
        if (active)
        {
            ClearLanathelStanceState(playerGuid);
            RestoreLanathelTransient(player, true);
            gLanathelStanceByPlayer.erase(playerGuid);
            return {true, "lanathel_stance_disabled"};
        }

        StoreLanathelStanceState(playerGuid, shellSpellId);
        ApplyLanathelStance(player, *stanceConfig);

        LanathelStanceRuntimeState const& state = gLanathelStanceByPlayer[playerGuid];
        return {
            true,
            "lanathel_stance_enabled:flight="
                + std::string(state.flightAllowed ? "1" : "0")
                + ":land_speed="
                + std::to_string(state.landSpeedRate)
                + ":flight_speed="
                + std::to_string(state.flightSpeedRate),
        };
    }

    BehaviorExecutionResult ExecuteBrougSkirmisherMark(Player* player, uint32 shellSpellId, Unit* explicitTarget)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        BrougGuardRuntimeState const* previousState = stateIt != gBrougGuardByPlayer.end() ? &stateIt->second : nullptr;
        std::optional<BrougGuardRuntimeState> loaded = LoadActiveBrougGuardState(player, previousState);
        if (!loaded.has_value() || !loaded->hasSkirmisherMark)
            return {false, "broug_skirmisher_not_granted"};

        gBrougGuardByPlayer[playerGuid] = *loaded;
        BrougGuardRuntimeState& state = gBrougGuardByPlayer[playerGuid];
        if (state.skirmisherMark.shellSpellId != shellSpellId)
            return {false, "broug_skirmisher_shell_mismatch"};

        if (state.skirmisherAttackTimerMs > 0)
            return {false, "broug_skirmisher_not_ready"};

        Item* rangedItem = player->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_RANGED);
        if (!IsBrougRangedWeapon(rangedItem) || !player->HasRangedWeaponForAttack())
            return {false, "broug_skirmisher_ranged_weapon_required"};
        Unit* target = SelectBrougSkirmisherTarget(player, state.skirmisherMark, explicitTarget);
        if (!target)
            return {false, "broug_skirmisher_target_required"};

        if (!FireBrougSkirmisherShot(player, target, state))
            return {false, "broug_skirmisher_fire_failed"};
        state.skirmisherAttackTimerMs = ResolveBrougSkirmisherAttackIntervalMs(player, state.skirmisherMark);
        return {true, "broug_skirmisher_shot_fired"};
    }

    BehaviorExecutionResult ExecuteBrougDeflectCounterStance(Player* player, uint32 shellSpellId)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};
        if (shellSpellId != BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID)
            return {false, "broug_deflect_counter_stance_shell_mismatch"};

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        BrougGuardRuntimeState const* previousState = stateIt != gBrougGuardByPlayer.end() ? &stateIt->second : nullptr;
        std::optional<BrougGuardRuntimeState> loaded = LoadActiveBrougGuardState(player, previousState);
        if (!loaded.has_value() || !loaded->hasDeflect || !loaded->hasDeflectCounterStance)
            return {false, "broug_deflect_counter_stance_not_granted"};

        gBrougGuardByPlayer[playerGuid] = *loaded;
        bool toggledOff = gBrougCounterStanceToggleOffByPlayer.erase(playerGuid) > 0;
        if (toggledOff)
        {
            player->RemoveAurasDueToSpell(BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID);
            ChatHandler(player->GetSession()).PSendSysMessage("WM Broug: Counterstrike Stance inactive.");
            return {true, "broug_deflect_counter_stance_inactive"};
        }

        bool active = IsBrougDeflectCounterStanceActive(player);

        ChatHandler(player->GetSession()).PSendSysMessage(
            "WM Broug: Counterstrike Stance {}.",
            active ? "active" : "cast");
        return {
            true,
            active
                ? "broug_deflect_counter_stance_active"
                : "broug_deflect_counter_stance_cast",
        };
    }

    BehaviorExecutionResult ExecuteBrougDeflect(Player* player, uint32 shellSpellId)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        BrougGuardRuntimeState const* previousState = stateIt != gBrougGuardByPlayer.end() ? &stateIt->second : nullptr;
        std::optional<BrougGuardRuntimeState> loaded = LoadActiveBrougGuardState(player, previousState);
        if (!loaded.has_value() || !loaded->hasDeflect)
            return {false, "broug_deflect_not_granted"};

        gBrougGuardByPlayer[playerGuid] = *loaded;
        BrougGuardRuntimeState& state = gBrougGuardByPlayer[playerGuid];
        if (state.deflect.shellSpellId != shellSpellId)
            return {false, "broug_deflect_shell_mismatch"};

        uint64 nowMs = BrougNowMs();
        if (state.deflectCooldownUntilMs > nowMs)
            return {false, "broug_deflect_not_ready"};
        if (state.deflect.energyCost > 0 && player->GetPower(POWER_ENERGY) < state.deflect.energyCost)
            return {false, "broug_deflect_no_power"};
        ClearBrougPendingDeflect(state);
        gBrougPendingForcedParryByVictim.erase(player->GetGUID());
        state.deflectWindowUntilMs = nowMs + static_cast<uint64>(state.deflect.windowMs);
        state.deflectRootUntilMs = state.deflectWindowUntilMs;
        state.deflectParryFeedbackAtMs = nowMs + static_cast<uint64>(state.deflect.parryPreMs);
        state.deflectParryFeedbackPlayed = false;
        state.deflectCooldownUntilMs = nowMs + static_cast<uint64>(state.deflect.cooldownMs);
        if (state.deflect.energyCost > 0)
            player->ModifyPower(POWER_ENERGY, -static_cast<int32>(state.deflect.energyCost));
        player->SetControlled(true, UNIT_STATE_ROOT, player);
        if (state.deflect.parryPreMs == 0)
        {
            PlayBrougParryFeedback(player);
            state.deflectParryFeedbackPlayed = true;
        }
        return {true, "broug_deflect_window_open"};
    }

    BehaviorExecutionResult ExecuteBrougCloudStep(Player* player, uint32 shellSpellId, Unit* explicitTarget)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougLightnessByPlayer.find(playerGuid);
        BrougLightnessRuntimeState const* previousState = stateIt != gBrougLightnessByPlayer.end() ? &stateIt->second : nullptr;
        std::optional<BrougLightnessRuntimeState> loaded = LoadActiveBrougLightnessState(player, previousState);
        if (!loaded.has_value() || !loaded->hasCloudStep)
            return {false, "broug_cloud_step_not_granted"};

        gBrougLightnessByPlayer[playerGuid] = *loaded;
        BrougLightnessRuntimeState& state = gBrougLightnessByPlayer[playerGuid];
        if (state.cloudStep.shellSpellId != shellSpellId)
            return {false, "broug_cloud_step_shell_mismatch"};

        uint64 nowMs = BrougNowMs();
        if (state.cloudStepCooldownUntilMs > nowMs)
            return {false, "broug_cloud_step_not_ready"};
        if (state.cloudStep.energyCost > 0 && player->GetPower(POWER_ENERGY) < state.cloudStep.energyCost)
            return {false, "broug_cloud_step_no_power"};
        if (player->HasUnitState(UNIT_STATE_ROOT) || player->HasUnitState(UNIT_STATE_STUNNED) || player->HasUnitState(UNIT_STATE_CONTROLLED))
            return {false, "broug_cloud_step_caster_locked"};

        Unit* target = SelectBrougCloudStepTarget(player, state.cloudStep, explicitTarget);
        if (!target)
            return {false, "broug_cloud_step_target_required"};

        Position landing;
        if (!ResolveBrougCloudStepLanding(player, target, state.cloudStep, landing))
            return {false, "broug_cloud_step_no_landing"};

        if (state.cloudStep.energyCost > 0)
            player->ModifyPower(POWER_ENERGY, -static_cast<int32>(state.cloudStep.energyCost));
        state.cloudStepCooldownUntilMs = nowMs + static_cast<uint64>(state.cloudStep.cooldownMs);
        state.cloudStepKillTargetGuid = target->GetGUID();
        state.cloudStepKillWindowUntilMs = nowMs + static_cast<uint64>(
            state.hasSilentMeridian ? state.silentMeridian.killWindowMs : 5000u);
        state.markedMeridianTargetGuid = target->GetGUID();
        state.markedMeridianUntilMs = nowMs + static_cast<uint64>(state.cloudStep.markedMeridianDurationMs);
        uint32 killingIntentDurationMs = ResolveBrougKillingIntentDurationMs(
            player,
            playerGuid,
            state.cloudStep.killingIntentDurationMs);

        PlayBrougCloudStepVisual(player, state.cloudStep.departureVisualSpellId);
        player->NearTeleportTo(
            landing.GetPositionX(),
            landing.GetPositionY(),
            landing.GetPositionZ(),
            landing.GetOrientation());
        player->SetInFront(target);
        player->Attack(target, true);
        PlayBrougCloudStepVisual(player, state.cloudStep.arrivalVisualSpellId);

        ApplyBrougTimedVisibleAura(
            player,
            player,
            state.cloudStep.killingIntentSpellId,
            killingIntentDurationMs);
        ApplyBrougTimedVisibleAura(
            player,
            target,
            state.cloudStep.markedMeridianSpellId,
            state.cloudStep.markedMeridianDurationMs);

        return {true, "broug_cloud_step_cast"};
    }

    uint32 RemoveBrougQiReversalAurasByDispel(Player* player, uint32 dispelType, uint32 maxRemovals)
    {
        if (!player || dispelType == DISPEL_NONE || maxRemovals == 0)
            return 0;

        std::vector<Aura*> aurasToRemove;
        for (auto const& applied : player->GetAppliedAuras())
        {
            AuraApplication* aurApp = applied.second;
            Aura* aura = aurApp ? aurApp->GetBase() : nullptr;
            SpellInfo const* spellInfo = aura ? aura->GetSpellInfo() : nullptr;
            if (!aura || !spellInfo || spellInfo->IsPositive() || spellInfo->Dispel != dispelType)
                continue;

            aurasToRemove.push_back(aura);
            if (aurasToRemove.size() >= maxRemovals)
                break;
        }

        uint32 removed = 0;
        for (Aura* aura : aurasToRemove)
        {
            if (!aura || aura->IsRemoved())
                continue;
            aura->Remove(AURA_REMOVE_BY_DEFAULT);
            ++removed;
        }
        return removed;
    }

    void ApplyBrougPurgedState(Player* player, BrougEmptyCourtRuntimeState& state, std::unordered_set<uint32> protectedTypes)
    {
        if (!player || protectedTypes.empty() || state.qiReversal.purgedStateSpellId == 0 || state.qiReversal.purgedCharges == 0)
            return;

        uint64 nowMs = BrougNowMs();
        state.purgedCharges = state.qiReversal.purgedCharges;
        state.purgedProtectedDispelTypes = std::move(protectedTypes);
        state.purgedStateUntilMs = nowMs + static_cast<uint64>(state.qiReversal.purgedDurationMs);

        Aura* aura = ApplyBrougTimedVisibleAura(
            player,
            player,
            state.qiReversal.purgedStateSpellId,
            state.qiReversal.purgedDurationMs);
        if (aura)
            aura->SetStackAmount(static_cast<uint8>(std::min<uint32>(state.purgedCharges, 255u)));
    }

    BehaviorExecutionResult ExecuteBrougQiReversal(Player* player, uint32 shellSpellId)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        BrougEmptyCourtRuntimeState* state = EnsureBrougEmptyCourtState(player, playerGuid);
        if (!state || !state->hasQiReversal)
            return {false, "broug_qi_reversal_not_granted"};
        if (state->qiReversal.shellSpellId != shellSpellId)
            return {false, "broug_qi_reversal_shell_mismatch"};

        uint32 removedMagic = RemoveBrougQiReversalAurasByDispel(player, DISPEL_MAGIC, state->qiReversal.maxMagic);
        uint32 removedPoison = RemoveBrougQiReversalAurasByDispel(player, DISPEL_POISON, state->qiReversal.maxPoison);
        uint32 removedDisease = RemoveBrougQiReversalAurasByDispel(player, DISPEL_DISEASE, state->qiReversal.maxDisease);
        uint32 removedTotal = removedMagic + removedPoison + removedDisease;

        std::unordered_set<uint32> protectedTypes;
        if (removedMagic > 0)
            protectedTypes.insert(DISPEL_MAGIC);
        if (removedPoison > 0)
            protectedTypes.insert(DISPEL_POISON);
        if (removedDisease > 0)
            protectedTypes.insert(DISPEL_DISEASE);

        ApplyBrougPurgedState(player, *state, std::move(protectedTypes));
        if (removedTotal > 0)
            RecordBrougEmptyCourtCounter(playerGuid, state->qiReversal.counterKey, removedTotal);

        ChatHandler(player->GetSession()).PSendSysMessage(
            "WM Broug: Qi Reversal cleansed {} harmful aura{}.",
            removedTotal,
            removedTotal == 1 ? "" : "s");
        return {true, removedTotal > 0 ? "broug_qi_reversal_cleansed" : "broug_qi_reversal_no_harmful_auras"};
    }

    BehaviorExecutionResult ExecuteShellBehavior(Player* player, uint32 shellSpellId, bool persistPetFallback, Unit* explicitTarget)
    {
        std::optional<BehaviorRecord> behaviorRecord = LoadBehaviorRecord(shellSpellId);
        if (!behaviorRecord.has_value())
            return {false, "shell_behavior_missing"};

        if (IsIntellectBlockBehaviorKind(behaviorRecord->behaviorKind))
        {
            MaintainIntellectBlockPassive(player);
            return {true, "intellect_block_passive_maintained"};
        }

        if (behaviorRecord->behaviorKind == "broug_deflect_v1")
            return ExecuteBrougDeflect(player, shellSpellId);

        if (behaviorRecord->behaviorKind == "broug_deflect_counter_stance_v1")
            return ExecuteBrougDeflectCounterStance(player, shellSpellId);

        if (behaviorRecord->behaviorKind == "broug_skirmisher_shot_v1")
            return ExecuteBrougSkirmisherMark(player, shellSpellId, explicitTarget);

        if (behaviorRecord->behaviorKind == "broug_cloud_step_v1")
            return ExecuteBrougCloudStep(player, shellSpellId, explicitTarget);

        if (behaviorRecord->behaviorKind == "broug_qi_reversal_v1")
            return ExecuteBrougQiReversal(player, shellSpellId);

        if (IsBrougGuardBehaviorKind(behaviorRecord->behaviorKind))
        {
            MaintainBrougGuard(player, 0);
            return {true, "broug_guard_passive_maintained"};
        }

        if (IsBrougLightnessBehaviorKind(behaviorRecord->behaviorKind))
        {
            MaintainBrougLightness(player, 0);
            return {true, "broug_lightness_passive_maintained"};
        }

        if (IsBrougEmptyCourtBehaviorKind(behaviorRecord->behaviorKind))
        {
            MaintainBrougEmptyCourt(player, 0);
            return {true, "broug_empty_court_passive_maintained"};
        }

        if (IsBoneboundEchoStasisBehaviorKind(behaviorRecord->behaviorKind))
            return ExecuteBoneboundEchoStasis(player, shellSpellId);

        if (IsLanathelStanceBehaviorKind(behaviorRecord->behaviorKind))
            return ExecuteLanathelStance(player, shellSpellId);

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
            gBoneboundEchoSeekTargetByCaster.erase(echoGuid);

            if (IsBoneboundPriestEcho(state) && runtimeConfig.has_value())
                MoveBoneboundPriestEchoToSafePosition(echo, player, nullptr, state, *runtimeConfig);
            else
                echo->GetMotionMaster()->MoveFollow(player, state.followDistance, state.followAngle);

            ++teleported;
        }

        return {true, "bonebound_echo_teleported:" + std::to_string(teleported)};
    }

    BehaviorExecutionResult DescribeBoneboundEchoStatus(Player* player)
    {
        if (!player)
            return {false, "player_not_online"};
        if (!IsPlayerAllowed(player))
            return {false, "player_not_allowed"};

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        Pet* alphaPet = player->GetPet();
        bool alphaOnline = alphaPet && IsBoneboundPet(alphaPet);

        std::optional<BoneboundBehaviorConfig> runtimeConfig;
        if (alphaOnline)
            runtimeConfig = LoadActiveBoneboundConfig(alphaPet->GetUInt32Value(UNIT_CREATED_BY_SPELL), false);

        bool huntMode = IsBoneboundEchoHuntMode(ownerGuid);
        float huntRadius = ResolveBoneboundEchoHuntRadius(ownerGuid, runtimeConfig);
        uint32 radiusYards = static_cast<uint32>(std::round(huntRadius));

        bool dpsSpellInfoOk = false;
        if (runtimeConfig.has_value())
        {
            uint32 damageSpellId = runtimeConfig->priestEchoDpsDamageSpellId != 0
                ? runtimeConfig->priestEchoDpsDamageSpellId
                : runtimeConfig->priestEchoDpsSpellId;
            dpsSpellInfoOk = runtimeConfig->priestEchoDpsSpellId != 0
                && sSpellMgr->GetSpellInfo(runtimeConfig->priestEchoDpsSpellId)
                && sSpellMgr->GetSpellInfo(damageSpellId);
        }

        uint32 tracked = 0;
        uint32 live = 0;
        uint32 destroyers = 0;
        uint32 restorers = 0;
        uint32 restorerTargeted = 0;
        uint32 restorerReady = 0;
        uint32 restorerCasting = 0;
        uint32 restorerPending = 0;
        uint32 restorerCooldown = 0;
        uint32 restorerNoTarget = 0;
        uint32 restorerOutOfRange = 0;
        uint32 restorerNoLos = 0;
        uint32 restorerLensMarked = 0;
        std::string firstRestorer = "";

        for (auto const& [echoGuid, state] : gBoneboundAlphaEchoes)
        {
            if (state.ownerGuid != ownerGuid)
                continue;

            ++tracked;
            Creature* echo = ObjectAccessor::GetCreature(*player, state.echoGuid);
            if (!echo || !echo->IsAlive() || echo->GetMapId() != player->GetMapId())
                continue;

            ++live;
            if (!IsBoneboundPriestEcho(state))
            {
                ++destroyers;
                continue;
            }

            ++restorers;
            Unit* target = nullptr;
            if (Unit* victim = echo->GetVictim(); IsValidBoneboundSeekTarget(player, echo, victim))
                target = victim;
            if (!target)
            {
                Unit* selected = ObjectAccessor::GetUnit(*player, echo->GetTarget());
                if (IsValidBoneboundSeekTarget(player, echo, selected))
                    target = selected;
            }
            if (!target)
            {
                auto seekIt = gBoneboundEchoSeekTargetByCaster.find(echoGuid);
                if (seekIt != gBoneboundEchoSeekTargetByCaster.end())
                {
                    Unit* selected = ObjectAccessor::GetUnit(*player, seekIt->second.targetGuid);
                    if (IsValidBoneboundSeekTarget(player, echo, selected))
                        target = selected;
                }
            }
            if (!target && huntMode)
            {
                Unit* selected = SelectNightWatchersLensMarkedBoneboundSeekTarget(player, echo, huntRadius);
                if (!selected)
                    selected = SelectNearestBoneboundSeekTarget(player, echo, huntRadius);
                if (IsValidBoneboundSeekTarget(player, echo, selected))
                    target = selected;
            }
            if (!target && alphaPet)
            {
                Unit* selected = alphaPet->GetVictim();
                if (IsValidBoneboundSeekTarget(player, echo, selected))
                    target = selected;
            }

            bool hasTarget = target != nullptr;
            bool inRange = false;
            bool hasLos = false;
            bool lensMarked = hasTarget && WmSpells::IsNightWatchersLensMarkedBy(target, player);
            if (hasTarget)
            {
                ++restorerTargeted;
                if (lensMarked)
                    ++restorerLensMarked;
                if (runtimeConfig.has_value())
                    inRange = echo->IsWithinDistInMap(target, ResolveBoneboundPriestVisibleDpsCastRange(echo, *runtimeConfig));
                hasLos = echo->IsWithinLOSInMap(target);
                if (!inRange)
                    ++restorerOutOfRange;
                if (!hasLos)
                    ++restorerNoLos;
            }
            else
            {
                ++restorerNoTarget;
            }

            bool casting = echo->IsNonMeleeSpellCast(false);
            if (casting)
                ++restorerCasting;

            bool pending = gBoneboundPriestDpsCastByCaster.find(echoGuid) != gBoneboundPriestDpsCastByCaster.end();
            if (pending)
                ++restorerPending;

            uint32 cooldownMs = 0;
            if (auto cooldownIt = gBoneboundPriestDpsCooldownByCaster.find(echoGuid); cooldownIt != gBoneboundPriestDpsCooldownByCaster.end())
                cooldownMs = cooldownIt->second;
            if (cooldownMs != 0)
                ++restorerCooldown;

            if (hasTarget && inRange && hasLos && !casting && !pending && cooldownMs == 0 && dpsSpellInfoOk)
                ++restorerReady;

            if (firstRestorer.empty())
            {
                firstRestorer = " first=t";
                firstRestorer += hasTarget ? std::to_string(static_cast<uint32>(target->GetGUID().GetCounter())) : "0";
                if (hasTarget)
                    firstRestorer += ":d" + std::to_string(static_cast<uint32>(std::round(echo->GetDistance(target))));
                firstRestorer += ":los" + std::to_string(hasLos ? 1 : 0);
                firstRestorer += ":range" + std::to_string(inRange ? 1 : 0);
                firstRestorer += ":mark" + std::to_string(lensMarked ? 1 : 0);
                firstRestorer += ":cast" + std::to_string(casting ? 1 : 0);
                firstRestorer += ":cd" + std::to_string(cooldownMs);
                firstRestorer += ":pending" + std::to_string(pending ? 1 : 0);
            }
        }

        std::string message = "mode=" + std::string(huntMode ? "seek" : "follow")
            + " radius=" + std::to_string(radiusYards)
            + " alpha=" + std::string(alphaOnline ? "1" : "0")
            + " tracked=" + std::to_string(tracked)
            + " live=" + std::to_string(live)
            + " destroyers=" + std::to_string(destroyers)
            + " restorers=" + std::to_string(restorers)
            + " restorer_targeted=" + std::to_string(restorerTargeted)
            + " ready=" + std::to_string(restorerReady)
            + " casting=" + std::to_string(restorerCasting)
            + " pending=" + std::to_string(restorerPending)
            + " cooldown=" + std::to_string(restorerCooldown)
            + " no_target=" + std::to_string(restorerNoTarget)
            + " out_range=" + std::to_string(restorerOutOfRange)
            + " no_los=" + std::to_string(restorerNoLos)
            + " marked=" + std::to_string(restorerLensMarked)
            + " dps_spell=" + std::string(dpsSpellInfoOk ? "1" : "0")
            + firstRestorer;

        return {true, message};
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
        if (!huntMode)
        {
            for (auto const& [echoGuid, state] : gBoneboundAlphaEchoes)
            {
                if (state.ownerGuid == ownerGuid)
                    gBoneboundEchoSeekTargetByCaster.erase(echoGuid);
            }
        }

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
                    enemy = SelectBoneboundEchoSeekTarget(player, echo, huntRadius, 0);
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
                if (Unit* target = SelectBoneboundEchoSeekTarget(player, echo, huntRadius, 0))
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

        if (!HasActiveCombatProficiencyGrant(player))
            return;

        for (CombatProficiencyRuntimeGrant const& grant : COMBAT_PROFICIENCY_RUNTIME_GRANTS)
            EnsureCombatProficiencyRuntimeGrant(player, grant);

        // character_spell is the persistent truth; AzerothCore keeps Dual Wield
        // as a volatile runtime flag, so materialize it only for explicit WM grants.
        if (!player->HasSpell(DUAL_WIELD_SPELL_ID) || player->CanDualWield())
            return;

        player->CastSpell(player, DUAL_WIELD_SPELL_ID, true);
        if (!player->CanDualWield())
            player->SetCanDualWield(true);
    }

    void TickBrougGuard(Player* player, uint32 /*diff*/)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        UpdateBrougForcedStuns(player);
        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        if (stateIt == gBrougGuardByPlayer.end())
            return;

        if (!IsPlayerAllowed(player))
        {
            gBrougCounterStanceToggleOffByPlayer.erase(playerGuid);
            gBrougGuardByPlayer.erase(stateIt);
            return;
        }

        TickBrougDeflectWindow(player, stateIt->second);
    }

    void MaintainBrougGuard(Player* player, uint32 diff)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        UpdateBrougForcedStuns(player);
        if (!IsPlayerAllowed(player))
        {
            if (auto stateIt = gBrougGuardByPlayer.find(playerGuid); stateIt != gBrougGuardByPlayer.end())
                ClearBrougDeflectWindow(player, stateIt->second);
            gBrougCounterStanceToggleOffByPlayer.erase(playerGuid);
            gBrougGuardByPlayer.erase(playerGuid);
            return;
        }

        BrougGuardRuntimeState const* previousState = nullptr;
        if (auto stateIt = gBrougGuardByPlayer.find(playerGuid); stateIt != gBrougGuardByPlayer.end())
            previousState = &stateIt->second;

        std::optional<BrougGuardRuntimeState> loaded = LoadActiveBrougGuardState(player, previousState);
        if (!loaded.has_value())
        {
            if (auto stateIt = gBrougGuardByPlayer.find(playerGuid); stateIt != gBrougGuardByPlayer.end())
                ClearBrougDeflectWindow(player, stateIt->second);
            gBrougCounterStanceToggleOffByPlayer.erase(playerGuid);
            gBrougGuardByPlayer.erase(playerGuid);
            return;
        }

        BrougGuardRuntimeState& state = gBrougGuardByPlayer[playerGuid];
        state = *loaded;
        TickBrougDeflectWindow(player, state);
        if (state.skirmisherAttackTimerMs > diff)
            state.skirmisherAttackTimerMs -= diff;
        else
            state.skirmisherAttackTimerMs = 0;
    }

    void TickBrougLightness(Player* player, uint32 /*diff*/)
    {
        if (!player)
            return;

        uint64 nowMs = BrougNowMs();
        for (auto it = gBrougLightnessPreserveVulnerableByVictim.begin(); it != gBrougLightnessPreserveVulnerableByVictim.end();)
        {
            if (it->second < nowMs)
                it = gBrougLightnessPreserveVulnerableByVictim.erase(it);
            else
                ++it;
        }

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougLightnessByPlayer.find(playerGuid);
        if (stateIt == gBrougLightnessByPlayer.end())
            return;

        if (!IsPlayerAllowed(player))
        {
            gBrougLightnessByPlayer.erase(stateIt);
            return;
        }

        if (stateIt->second.cloudStepKillWindowUntilMs != 0 && stateIt->second.cloudStepKillWindowUntilMs < nowMs)
        {
            stateIt->second.cloudStepKillTargetGuid = ObjectGuid::Empty;
            stateIt->second.cloudStepKillWindowUntilMs = 0;
        }
        if (stateIt->second.markedMeridianUntilMs != 0 && stateIt->second.markedMeridianUntilMs < nowMs)
            ClearBrougMarkedMeridianState(stateIt->second);
    }

    void MaintainBrougLightness(Player* player, uint32 diff)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        if (!IsPlayerAllowed(player))
        {
            gBrougLightnessByPlayer.erase(playerGuid);
            return;
        }

        BrougLightnessRuntimeState const* previousState = nullptr;
        if (auto stateIt = gBrougLightnessByPlayer.find(playerGuid); stateIt != gBrougLightnessByPlayer.end())
            previousState = &stateIt->second;

        std::optional<BrougLightnessRuntimeState> loaded = LoadActiveBrougLightnessState(player, previousState);
        if (!loaded.has_value())
        {
            gBrougLightnessByPlayer.erase(playerGuid);
            return;
        }

        gBrougLightnessByPlayer[playerGuid] = *loaded;
        TickBrougLightness(player, diff);
    }

    void ClearBrougPurgedState(Player* player, BrougEmptyCourtRuntimeState& state)
    {
        state.purgedCharges = 0;
        state.purgedStateUntilMs = 0;
        state.purgedProtectedDispelTypes.clear();
        if (player && state.qiReversal.purgedStateSpellId != 0)
            player->RemoveAurasDueToSpell(state.qiReversal.purgedStateSpellId);
    }

    bool ApplyBrougDomainPulse(Player* player, BrougEmptyCourtRuntimeState& state, uint32 playerGuid)
    {
        if (!player || !state.hasDomain || state.domain.suppressedSpellId == 0 || !player->IsAlive())
            return false;

        Aura* intent = player->GetAura(state.domain.killingIntentSpellId, player->GetGUID());
        if (!intent || intent->GetDuration() == 0)
            return false;

        std::list<Unit*> nearby;
        Acore::AnyUnfriendlyUnitInObjectRangeCheck check(player, player, state.domain.radiusYards);
        Acore::UnitListSearcher<Acore::AnyUnfriendlyUnitInObjectRangeCheck> searcher(player, nearby, check);
        Cell::VisitObjects(player, searcher, state.domain.radiusYards);

        uint32 applied = 0;
        for (Unit* target : nearby)
        {
            if (!target || target == player || !target->IsAlive() || player->IsFriendlyTo(target))
                continue;
            if (!player->IsWithinLOSInMap(target))
                continue;

            if (ApplyBrougTimedVisibleAura(
                    player,
                    target,
                    state.domain.suppressedSpellId,
                    state.domain.suppressedDurationMs))
                ++applied;
        }

        if (applied > 0)
            RecordBrougEmptyCourtCounter(playerGuid, state.domain.pulseCounterKey, 1);
        return applied > 0;
    }

    void TickBrougEmptyCourt(Player* player, uint32 diff)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid);
        if (stateIt == gBrougEmptyCourtByPlayer.end())
            return;

        if (!IsPlayerAllowed(player) || !player->IsAlive())
        {
            ClearBrougPurgedState(player, stateIt->second);
            gBrougEmptyCourtByPlayer.erase(stateIt);
            return;
        }

        BrougEmptyCourtRuntimeState& state = stateIt->second;
        uint64 nowMs = BrougNowMs();
        if (state.purgedStateUntilMs != 0 && state.purgedStateUntilMs < nowMs)
            ClearBrougPurgedState(player, state);
        else if (state.purgedCharges > 0
            && state.qiReversal.purgedStateSpellId != 0
            && !player->HasAura(state.qiReversal.purgedStateSpellId))
        {
            ClearBrougPurgedState(player, state);
        }

        if (!state.hasDomain || !player->HasAura(state.domain.killingIntentSpellId))
        {
            state.domainPulseTimerMs = 0;
            return;
        }

        if (state.domainPulseTimerMs > diff)
        {
            state.domainPulseTimerMs -= diff;
            return;
        }

        ApplyBrougDomainPulse(player, state, playerGuid);
        state.domainPulseTimerMs = state.domain.pulseIntervalMs;
    }

    void MaintainBrougEmptyCourt(Player* player, uint32 diff)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        if (!IsPlayerAllowed(player))
        {
            gBrougEmptyCourtByPlayer.erase(playerGuid);
            return;
        }

        BrougEmptyCourtRuntimeState const* previousState = nullptr;
        if (auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid); stateIt != gBrougEmptyCourtByPlayer.end())
            previousState = &stateIt->second;

        std::optional<BrougEmptyCourtRuntimeState> loaded = LoadActiveBrougEmptyCourtState(player, previousState);
        if (!loaded.has_value())
        {
            gBrougEmptyCourtByPlayer.erase(playerGuid);
            return;
        }

        gBrougEmptyCourtByPlayer[playerGuid] = *loaded;
        TickBrougEmptyCourt(player, diff);
    }

    void ForgetIntellectBlockPassive(Player* player)
    {
        if (!player)
            return;

        ApplyIntellectBlockRating(player, 0);
    }

    void ForgetBrougGuard(Player* player)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        if (stateIt != gBrougGuardByPlayer.end())
            ClearBrougDeflectWindow(player, stateIt->second);
        gBrougCounterStanceToggleOffByPlayer.erase(playerGuid);
        gBrougGuardByPlayer.erase(playerGuid);
    }

    void ForgetBrougLightness(Player* player)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        gBrougLightnessByPlayer.erase(playerGuid);
    }

    void ForgetBrougEmptyCourt(Player* player)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        if (auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid); stateIt != gBrougEmptyCourtByPlayer.end())
            ClearBrougPurgedState(player, stateIt->second);
        gBrougEmptyCourtByPlayer.erase(playerGuid);
    }

    bool CanCompleteBrougGuardQuest(Player* player, uint32 questId, std::string* reason)
    {
        if (questId != BROUG_PARRY_QUEST_ID && questId != BROUG_DEFLECT_QUEST_ID)
            return true;

        if (!player)
        {
            if (reason)
                *reason = "player_not_online";
            return false;
        }

        if (!IsPlayerAllowed(player))
        {
            if (reason)
                *reason = "player_not_allowed";
            return false;
        }

        char const* counterKey = questId == BROUG_PARRY_QUEST_ID
            ? BROUG_UNIVERSAL_PARRY_COUNTER_KEY
            : BROUG_DEFLECT_COUNTER_KEY;
        if (!BrougGuardCounterTableExists())
        {
            if (reason)
                *reason = "counter_table_missing";
            return false;
        }

        QueryResult result = WorldDatabase.Query(
            "SELECT CounterValue FROM wm_broug_guard_counter "
            "WHERE PlayerGUID = {} AND CounterKey = {} LIMIT 1",
            static_cast<uint32>(player->GetGUID().GetCounter()),
            SqlString(counterKey));
        uint64 counterValue = result ? result->Fetch()[0].Get<uint64>() : 0;
        if (counterValue < 1000)
        {
            if (reason)
                *reason = std::string("counter_below_required:") + counterKey + "=" + std::to_string(counterValue);
            return false;
        }

        if (reason)
            *reason = "ok";
        return true;
    }

    void HandleBrougGuardQuestComplete(Player* player, uint32 questId)
    {
        if (!player || (questId != BROUG_PARRY_QUEST_ID && questId != BROUG_DEFLECT_QUEST_ID))
            return;

        if (!IsPlayerAllowed(player))
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());

        struct BrougQuestRewardShell
        {
            uint32 shellSpellId;
            char const* behaviorKind;
            char const* capability;
        };

        std::vector<BrougQuestRewardShell> rewards;
        if (questId == BROUG_PARRY_QUEST_ID)
        {
            rewards.push_back({BROUG_DEFLECT_SHELL_ID, "broug_deflect_v1", "deflect"});
            rewards.push_back({BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID, "broug_deflect_counter_stance_v1", "deflect_counter_stance"});
        }
        else
        {
            rewards.push_back({BROUG_AUTO_RETALIATION_SHELL_ID, "broug_auto_retaliation_v1", "auto_retaliation"});
        }

        for (BrougQuestRewardShell const& reward : rewards)
        {
            if (!player->HasSpell(reward.shellSpellId))
                player->learnSpell(reward.shellSpellId, false);

            std::string metadata = "{\"capability\":\"" + std::string(reward.capability)
                + "\",\"behavior_kind\":\"" + reward.behaviorKind
                + "\",\"source\":\"broug_guard_quest\",\"status\":\"PARTIAL\"}";
            WorldDatabase.Execute(
                "UPDATE wm_spell_grant "
                "SET GrantKind = 'broug_guard_reward', SourceQuestID = {}, Author = 'mod-wm-spells', MetadataJSON = {} "
                "WHERE PlayerGUID = {} AND ShellSpellID = {} AND RevokedAt IS NULL",
                questId,
                SqlString(metadata),
                playerGuid,
                reward.shellSpellId);
            WorldDatabase.Execute(
                "INSERT INTO wm_spell_grant "
                "(PlayerGUID, ShellSpellID, GrantKind, SourceQuestID, Author, MetadataJSON) "
                "SELECT {}, {}, 'broug_guard_reward', {}, 'mod-wm-spells', {} "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM wm_spell_grant "
                "WHERE PlayerGUID = {} AND ShellSpellID = {} AND RevokedAt IS NULL"
                ")",
                playerGuid,
                reward.shellSpellId,
                questId,
                SqlString(metadata),
                playerGuid,
                reward.shellSpellId);
        }

        player->SaveToDB(false, false);
        MaintainBrougGuard(player, 0);
    }

    bool CanCompleteBrougLightnessQuest(Player* player, uint32 questId, std::string* reason)
    {
        if (questId != BROUG_LIGHTNESS_STEPS_QUEST_ID && questId != BROUG_LIGHTNESS_NO_FOOTFALL_QUEST_ID)
            return true;

        if (!player)
        {
            if (reason)
                *reason = "player_not_online";
            return false;
        }

        if (!IsPlayerAllowed(player))
        {
            if (reason)
                *reason = "player_not_allowed";
            return false;
        }

        if (questId == BROUG_LIGHTNESS_STEPS_QUEST_ID)
        {
            if (reason)
                *reason = "ok";
            return true;
        }

        if (!BrougLightnessCounterTableExists())
        {
            if (reason)
                *reason = "lightness_counter_table_missing";
            return false;
        }

        QueryResult result = WorldDatabase.Query(
            "SELECT CounterValue FROM wm_broug_lightness_counter "
            "WHERE PlayerGUID = {} AND CounterKey = {} LIMIT 1",
            static_cast<uint32>(player->GetGUID().GetCounter()),
            SqlString(BROUG_CLOUD_STEP_STRIKE_COUNTER_KEY));
        uint64 counterValue = result ? result->Fetch()[0].Get<uint64>() : 0;
        if (counterValue < 20)
        {
            if (reason)
                *reason = std::string("counter_below_required:") + BROUG_CLOUD_STEP_STRIKE_COUNTER_KEY + "=" + std::to_string(counterValue);
            return false;
        }

        if (reason)
            *reason = "ok";
        return true;
    }

    void HandleBrougLightnessQuestComplete(Player* player, uint32 questId)
    {
        if (!player || (questId != BROUG_LIGHTNESS_STEPS_QUEST_ID && questId != BROUG_LIGHTNESS_NO_FOOTFALL_QUEST_ID))
            return;

        if (!IsPlayerAllowed(player))
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());

        struct BrougLightnessRewardShell
        {
            uint32 shellSpellId;
            char const* behaviorKind;
            char const* capability;
        };

        std::vector<BrougLightnessRewardShell> rewards;
        if (questId == BROUG_LIGHTNESS_STEPS_QUEST_ID)
            rewards.push_back({BROUG_CLOUD_STEP_SHELL_ID, "broug_cloud_step_v1", "cloud_step"});
        else
            rewards.push_back({BROUG_SILENT_MERIDIAN_SHELL_ID, "broug_silent_meridian_v1", "silent_meridian"});

        for (BrougLightnessRewardShell const& reward : rewards)
        {
            if (!player->HasSpell(reward.shellSpellId))
                player->learnSpell(reward.shellSpellId, false);

            std::string metadata = "{\"capability\":\"" + std::string(reward.capability)
                + "\",\"behavior_kind\":\"" + reward.behaviorKind
                + "\",\"source\":\"broug_lightness_assassin_v1\",\"status\":\"PARTIAL\"}";
            WorldDatabase.Execute(
                "UPDATE wm_spell_grant "
                "SET GrantKind = 'broug_lightness_reward', SourceQuestID = {}, Author = 'mod-wm-spells', MetadataJSON = {} "
                "WHERE PlayerGUID = {} AND ShellSpellID = {} AND RevokedAt IS NULL",
                questId,
                SqlString(metadata),
                playerGuid,
                reward.shellSpellId);
            WorldDatabase.Execute(
                "INSERT INTO wm_spell_grant "
                "(PlayerGUID, ShellSpellID, GrantKind, SourceQuestID, Author, MetadataJSON) "
                "SELECT {}, {}, 'broug_lightness_reward', {}, 'mod-wm-spells', {} "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM wm_spell_grant "
                "WHERE PlayerGUID = {} AND ShellSpellID = {} AND RevokedAt IS NULL"
                ")",
                playerGuid,
                reward.shellSpellId,
                questId,
                SqlString(metadata),
                playerGuid,
                reward.shellSpellId);
        }

        player->SaveToDB(false, false);
        MaintainBrougLightness(player, 0);
    }

    bool CanCompleteBrougEmptyCourtQuest(Player* player, uint32 questId, std::string* reason)
    {
        if (questId < BROUG_EMPTY_COURT_WEIGHT_QUEST_ID || questId > BROUG_EMPTY_COURT_DOMAIN_UNSEALED_QUEST_ID)
            return true;

        if (!player)
        {
            if (reason)
                *reason = "player_not_online";
            return false;
        }

        if (!IsPlayerAllowed(player))
        {
            if (reason)
                *reason = "player_not_allowed";
            return false;
        }

        if (player->GetQuestStatus(BROUG_LIGHTNESS_NO_FOOTFALL_QUEST_ID) != QUEST_STATUS_REWARDED)
        {
            if (reason)
                *reason = "lightness_foundation_quest_missing";
            return false;
        }

        if (!player->HasSpell(BROUG_CLOUD_STEP_SHELL_ID) || !player->HasSpell(BROUG_SILENT_MERIDIAN_SHELL_ID))
        {
            if (reason)
                *reason = "lightness_foundation_spells_missing";
            return false;
        }

        if (reason)
            *reason = "ok";
        return true;
    }

    void HandleBrougEmptyCourtQuestComplete(Player* player, uint32 questId)
    {
        if (!player || questId < BROUG_EMPTY_COURT_WEIGHT_QUEST_ID || questId > BROUG_EMPTY_COURT_DOMAIN_UNSEALED_QUEST_ID)
            return;

        if (!IsPlayerAllowed(player))
            return;

        struct BrougEmptyCourtRewardShell
        {
            uint32 shellSpellId;
            char const* behaviorKind;
            char const* capability;
        };

        std::vector<BrougEmptyCourtRewardShell> rewards;
        switch (questId)
        {
            case BROUG_EMPTY_COURT_STILLING_QUEST_ID:
                rewards.push_back({BROUG_QI_REVERSAL_SHELL_ID, "broug_qi_reversal_v1", "qi_reversal"});
                break;
            case BROUG_EMPTY_COURT_NINETY_EIGHT_QUEST_ID:
                rewards.push_back({BROUG_PREDATORS_STRIKE_SHELL_ID, "broug_predators_strike_v1", "predators_strike"});
                break;
            case BROUG_EMPTY_COURT_ROOM_QUEST_ID:
                rewards.push_back({BROUG_KILLING_INTENT_DOMAIN_SHELL_ID, "broug_killing_intent_domain_v1", "killing_intent_domain"});
                break;
            case BROUG_EMPTY_COURT_DOMAIN_UNSEALED_QUEST_ID:
                rewards.push_back({BROUG_VITALITY_DRAIN_SHELL_ID, "broug_vitality_drain_v1", "vitality_drain"});
                break;
            default:
                break;
        }

        if (rewards.empty())
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        for (BrougEmptyCourtRewardShell const& reward : rewards)
        {
            if (!player->HasSpell(reward.shellSpellId))
                player->learnSpell(reward.shellSpellId, false);

            std::string metadata = "{\"capability\":\"" + std::string(reward.capability)
                + "\",\"behavior_kind\":\"" + reward.behaviorKind
                + "\",\"source\":\"broug_empty_court_v2\",\"status\":\"PARTIAL\"}";
            WorldDatabase.Execute(
                "UPDATE wm_spell_grant "
                "SET GrantKind = 'broug_empty_court_reward', SourceQuestID = {}, Author = 'mod-wm-spells', MetadataJSON = {} "
                "WHERE PlayerGUID = {} AND ShellSpellID = {} AND RevokedAt IS NULL",
                questId,
                SqlString(metadata),
                playerGuid,
                reward.shellSpellId);
            WorldDatabase.Execute(
                "INSERT INTO wm_spell_grant "
                "(PlayerGUID, ShellSpellID, GrantKind, SourceQuestID, Author, MetadataJSON) "
                "SELECT {}, {}, 'broug_empty_court_reward', {}, 'mod-wm-spells', {} "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM wm_spell_grant "
                "WHERE PlayerGUID = {} AND ShellSpellID = {} AND RevokedAt IS NULL"
                ")",
                playerGuid,
                reward.shellSpellId,
                questId,
                SqlString(metadata),
                playerGuid,
                reward.shellSpellId);
        }

        player->SaveToDB(false, false);
        MaintainBrougEmptyCourt(player, 0);
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

    void MaintainLanathelStance(Player* player, uint32 /*diff*/)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        if (!IsPlayerAllowed(player))
        {
            if (gLanathelStanceByPlayer.find(playerGuid) != gLanathelStanceByPlayer.end())
                ForgetLanathelStance(player);
            return;
        }

        std::optional<LanathelStanceConfig> config = LoadActiveLanathelStanceConfig(player);
        if (!config.has_value())
        {
            if (gLanathelStanceByPlayer.find(playerGuid) != gLanathelStanceByPlayer.end())
                ForgetLanathelStance(player);
            return;
        }

        if (!player->IsAlive())
        {
            RestoreLanathelTransient(player, true);
            gLanathelStanceByPlayer.erase(playerGuid);
            return;
        }

        ApplyLanathelStance(player, *config);
    }

    void ForgetLanathelStance(Player* player)
    {
        if (!player)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        RestoreLanathelTransient(player, true);
        gLanathelStanceByPlayer.erase(playerGuid);
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

    bool IsNightWatchersLensMarkedBy(Unit const* unit, Player const* player)
    {
        if (!unit || !player)
            return false;

        auto markIt = gNightWatchersLensMarksByTarget.find(unit->GetGUID().GetRawValue());
        if (markIt == gNightWatchersLensMarksByTarget.end() || markIt->second.casterGuid != player->GetGUID())
            return false;

        Aura* aura = unit->GetAura(NIGHT_WATCHERS_LENS_MARK_DEBUFF_SPELL_ID, player->GetGUID());
        return aura && aura->GetDuration() > 0;
    }

    void ApplyNightWatchersLensSpellFocus(Player* player, Unit* victim, int32& damage, SpellInfo const* spellInfo)
    {
        if (!player || !victim || !spellInfo || damage <= 0)
            return;

        if (!HasNightWatchersLensReady(player) || !IsNightWatchersLensMarkedBy(victim, player))
            return;

        int64 focusedDamage = static_cast<int64>(damage)
            + (static_cast<int64>(damage) * NIGHT_WATCHERS_LENS_SPELL_FOCUS_DAMAGE_BONUS_PCT) / 100;
        damage = static_cast<int32>(std::min<int64>(focusedDamage, std::numeric_limits<int32>::max()));
    }

    void HandleNightWatchersLensWeaponDamage(Unit* attacker, Unit* victim, uint32& damage)
    {
        TryProcNightWatchersLensMark(attacker, victim, damage);
    }

    void HandleNightWatchersLensSpellDamage(Unit* attacker, Unit* victim, int32& damage, SpellInfo const* spellInfo)
    {
        if (damage <= 0 || !attacker)
            return;

        if (IsNightWatchersLensWandShot(spellInfo))
        {
            TryProcNightWatchersLensMark(attacker, victim, static_cast<uint32>(damage));
            return;
        }

        ApplyNightWatchersLensSpellFocus(attacker->ToPlayer(), victim, damage, spellInfo);
    }

    void HandleBrougLightnessMeleeDamage(Unit* attacker, Unit* victim, uint32& damage)
    {
        if (!attacker || !victim || damage == 0)
            return;

        Player* player = attacker->ToPlayer();
        if (!player)
            return;

        TryConsumeBrougMarkedMeridian(player, victim, damage);
    }

    void HandleBrougLightnessSpellDamage(Unit* attacker, Unit* victim, int32& damage, SpellInfo const* spellInfo)
    {
        if (!attacker || !victim || !spellInfo || damage <= 0 || spellInfo->Id != BROUG_CLOUD_STEP_SHELL_ID)
            return;

        Player* player = attacker->ToPlayer();
        if (!player)
            return;

        uint32 unsignedDamage = static_cast<uint32>(damage);
        if (TryConsumeBrougMarkedMeridian(player, victim, unsignedDamage))
            damage = static_cast<int32>(std::min<uint32>(unsignedDamage, static_cast<uint32>(std::numeric_limits<int32>::max())));
    }

    void HandleBrougLightnessCreatureKill(Player* player, Creature* killed)
    {
        if (!player || !killed || !IsPlayerAllowed(player))
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougLightnessByPlayer.find(playerGuid);
        if (stateIt == gBrougLightnessByPlayer.end() || !stateIt->second.hasSilentMeridian)
            return;

        BrougLightnessRuntimeState& state = stateIt->second;
        uint64 nowMs = BrougNowMs();
        if (state.cloudStepKillTargetGuid == ObjectGuid::Empty
            || state.cloudStepKillTargetGuid != killed->GetGUID()
            || state.cloudStepKillWindowUntilMs < nowMs)
            return;

        WmSpells::BrougSilentMeridianConfig const& config = state.silentMeridian;
        if (config.energyRestore > 0)
            player->ModifyPower(POWER_ENERGY, static_cast<int32>(config.energyRestore));
        if (config.cooldownReductionMs > 0 && state.cloudStepCooldownUntilMs > nowMs)
        {
            uint64 remainingMs = state.cloudStepCooldownUntilMs - nowMs;
            uint64 reductionMs = std::min<uint64>(remainingMs, config.cooldownReductionMs);
            state.cloudStepCooldownUntilMs -= reductionMs;

            uint32 clientDelayMs = player->GetSpellCooldownDelay(state.cloudStep.shellSpellId);
            uint32 clientReductionMs = std::min<uint32>(
                clientDelayMs,
                static_cast<uint32>(std::min<uint64>(reductionMs, static_cast<uint64>(std::numeric_limits<uint32>::max()))));
            if (clientReductionMs > 0)
                player->ModifySpellCooldown(state.cloudStep.shellSpellId, -static_cast<int32>(clientReductionMs));
        }
        RecordBrougLightnessCounter(playerGuid, config.counterKey, 1);
        state.cloudStepKillTargetGuid = ObjectGuid::Empty;
        state.cloudStepKillWindowUntilMs = 0;
    }

    bool IsBrougSilentMeridianKillWindowActive(Player* player, Creature* killed, uint64 nowMs)
    {
        if (!player || !killed)
            return false;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougLightnessByPlayer.find(playerGuid);
        if (stateIt == gBrougLightnessByPlayer.end() || !stateIt->second.hasSilentMeridian)
            return false;

        BrougLightnessRuntimeState const& state = stateIt->second;
        return state.cloudStepKillTargetGuid != ObjectGuid::Empty
            && state.cloudStepKillTargetGuid == killed->GetGUID()
            && state.cloudStepKillWindowUntilMs >= nowMs;
    }

    void ApplyBrougSuppressedIncomingPressure(Unit* attacker, Player* player, uint32 playerGuid, uint32& damage)
    {
        if (!attacker || !player || playerGuid == 0 || damage == 0)
            return;

        auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid);
        BrougEmptyCourtRuntimeState* state = stateIt != gBrougEmptyCourtByPlayer.end()
            ? &stateIt->second
            : EnsureBrougEmptyCourtState(player, playerGuid);
        if (!state || !state->hasDomain || state->domain.suppressedDamagePressurePct == 0)
            return;

        Aura* suppressed = attacker->GetAura(state->domain.suppressedSpellId, player->GetGUID());
        if (!suppressed || suppressed->GetDuration() == 0)
            return;

        uint64 reduced = static_cast<uint64>(damage)
            * static_cast<uint64>(std::min<uint32>(state->domain.suppressedDamagePressurePct, 90u))
            / 100u;
        damage -= static_cast<uint32>(std::min<uint64>(damage, reduced));
    }

    void HandleBrougEmptyCourtMeleeDamage(Unit* attacker, Unit* victim, uint32& damage)
    {
        Player* player = victim ? victim->ToPlayer() : nullptr;
        if (!player || !IsPlayerAllowed(player))
            return;

        ApplyBrougSuppressedIncomingPressure(
            attacker,
            player,
            static_cast<uint32>(player->GetGUID().GetCounter()),
            damage);
    }

    void HandleBrougEmptyCourtSpellDamage(Unit* attacker, Unit* victim, int32& damage, SpellInfo const* /*spellInfo*/)
    {
        if (damage <= 0)
            return;

        Player* player = victim ? victim->ToPlayer() : nullptr;
        if (!player || !IsPlayerAllowed(player))
            return;

        uint32 unsignedDamage = static_cast<uint32>(damage);
        ApplyBrougSuppressedIncomingPressure(
            attacker,
            player,
            static_cast<uint32>(player->GetGUID().GetCounter()),
            unsignedDamage);
        damage = static_cast<int32>(std::min<uint32>(unsignedDamage, static_cast<uint32>(std::numeric_limits<int32>::max())));
    }

    void ExtendBrougKillingIntentFromSuppressedDeath(Player* player, Creature* killed, uint32 playerGuid, BrougEmptyCourtRuntimeState& state)
    {
        if (!player || !killed || !state.hasDomain || state.domain.deathExtensionMs == 0)
            return;

        Aura* suppressed = killed->GetAura(state.domain.suppressedSpellId, player->GetGUID());
        if (!suppressed || suppressed->GetDuration() == 0)
            return;

        Aura* intent = player->GetAura(state.domain.killingIntentSpellId, player->GetGUID());
        if (!intent || intent->GetDuration() == 0)
            return;

        int64 currentDuration = std::max<int32>(0, intent->GetDuration());
        int64 extension = static_cast<int64>(state.domain.deathExtensionMs);
        int32 nextDuration = static_cast<int32>(std::min<int64>(currentDuration + extension, std::numeric_limits<int32>::max()));
        int32 nextMaxDuration = std::max<int32>(nextDuration, intent->GetMaxDuration());
        intent->SetMaxDuration(nextMaxDuration);
        intent->SetDuration(nextDuration);
        RecordBrougEmptyCourtCounter(playerGuid, state.domain.deathExtendCounterKey, 1);
    }

    void HandleBrougEmptyCourtCreatureKill(Player* player, Creature* killed)
    {
        if (!player || !killed || !IsPlayerAllowed(player))
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid);
        BrougEmptyCourtRuntimeState* state = stateIt != gBrougEmptyCourtByPlayer.end()
            ? &stateIt->second
            : EnsureBrougEmptyCourtState(player, playerGuid);
        if (!state)
            return;

        ExtendBrougKillingIntentFromSuppressedDeath(player, killed, playerGuid, *state);

        if (!state->hasVitalityDrain)
            return;

        uint64 nowMs = BrougNowMs();
        bool inSilentWindow = IsBrougSilentMeridianKillWindowActive(player, killed, nowMs);
        uint32 healPct = inSilentWindow
            ? state->vitalityDrain.silentWindowKillHealPctMaxHealth
            : state->vitalityDrain.killHealPctMaxHealth;
        if (healPct > 0)
        {
            uint64 healAmount = static_cast<uint64>(player->GetMaxHealth()) * static_cast<uint64>(healPct) / 100u;
            ApplyBrougHeal(
                player,
                static_cast<uint32>(std::min<uint64>(healAmount, std::numeric_limits<uint32>::max())));
        }
        if (inSilentWindow && state->vitalityDrain.silentWindowEnergyBonus > 0)
            player->ModifyPower(POWER_ENERGY, static_cast<int32>(state->vitalityDrain.silentWindowEnergyBonus));
        RecordBrougEmptyCourtCounter(playerGuid, state->vitalityDrain.counterKey, 1);
    }

    void HandleBrougGuardMeleeDamage(Unit* attacker, Unit* victim, uint32& damage)
    {
        if (TryBrougDeflect(attacker, victim, damage))
            return;

        ConsumeBrougVulnerableForDamage(attacker, victim, damage);
        if (damage == 0)
            return;

        TryQueueBrougUniversalMeleeParry(attacker, victim, damage, true);
    }

    void HandleBrougGuardSpellDamage(Unit* attacker, Unit* victim, int32& damage, SpellInfo const* spellInfo)
    {
        if (damage <= 0)
            return;

        // ModifySpellDamageTaken covers single-target spells and direct AoE hits.
        uint32 deflectDamage = static_cast<uint32>(damage);
        if (TryBrougDeflect(attacker, victim, deflectDamage))
        {
            damage = 0;
            return;
        }

        ConsumeBrougVulnerableForDamage(attacker, victim, deflectDamage);
        damage = static_cast<int32>(std::min<uint32>(deflectDamage, static_cast<uint32>(std::numeric_limits<int32>::max())));
        if (damage <= 0)
            return;

        Player* player = victim ? victim->ToPlayer() : nullptr;
        if (!player)
            return;

        auto stateIt = gBrougGuardByPlayer.find(static_cast<uint32>(player->GetGUID().GetCounter()));
        bool countEvent = stateIt != gBrougGuardByPlayer.end()
            && stateIt->second.hasUniversalParry
            && stateIt->second.universalParry.countSpellDamage;
        uint32 unsignedDamage = static_cast<uint32>(damage);
        if (TryBrougUniversalParry(attacker, victim, unsignedDamage, countEvent))
        {
            damage = 0;
            if (attacker && spellInfo)
                attacker->SendSpellMiss(player, spellInfo->Id, SPELL_MISS_PARRY);
        }
    }

    void HandleBrougGuardPeriodicDamage(Unit* attacker, Unit* victim, uint32& damage, SpellInfo const* /*spellInfo*/)
    {
        if (damage == 0)
            return;

        if (TryBrougDeflect(attacker, victim, damage))
            return;

        ConsumeBrougVulnerableForDamage(attacker, victim, damage);
        if (damage == 0)
            return;

        Player* player = victim ? victim->ToPlayer() : nullptr;
        if (!player)
            return;

        auto stateIt = gBrougGuardByPlayer.find(static_cast<uint32>(player->GetGUID().GetCounter()));
        bool countEvent = stateIt != gBrougGuardByPlayer.end()
            && stateIt->second.hasUniversalParry
            && stateIt->second.universalParry.countPeriodicDamage;
        TryBrougUniversalParry(attacker, victim, damage, countEvent);
    }

    void HandleBrougGuardAuraApply(Unit* unit, Aura* aura)
    {
        if (!unit || !aura)
            return;

        uint32 auraSpellId = aura->GetId();
        if (auraSpellId == BROUG_DEFLECTED_SHELL_ID)
        {
            Player* caster = nullptr;
            if (Unit* casterUnit = aura->GetCaster())
                caster = casterUnit->ToPlayer();
            EnsureBrougDeflectedStun(caster, unit);
            return;
        }

        if (auraSpellId == BROUG_VULNERABLE_SHELL_ID)
            return;

        Player* player = unit->ToPlayer();
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        if (stateIt == gBrougGuardByPlayer.end() || !IsBrougDeflectWindowActive(stateIt->second, BrougNowMs()))
            return;

        SpellInfo const* spellInfo = aura->GetSpellInfo();
        if (!spellInfo || spellInfo->IsPositive())
            return;

        Unit* caster = aura->GetCaster();
        if (!caster)
            caster = ObjectAccessor::GetUnit(*player, aura->GetCasterGUID());
        if (!IsBrougHostileDamage(caster, player))
            return;

        CaptureBrougDeflectEvent(player, playerGuid, stateIt->second, caster);
        aura->Remove(AURA_REMOVE_BY_DEFAULT);
    }

    void HandleBrougEmptyCourtAuraApply(Unit* unit, Aura* aura)
    {
        if (!unit || !aura)
            return;
        if (aura->IsRemoved())
            return;

        Player* player = unit->ToPlayer();
        if (!player || !IsPlayerAllowed(player))
            return;

        SpellInfo const* spellInfo = aura->GetSpellInfo();
        if (!spellInfo || spellInfo->IsPositive() || spellInfo->Dispel == DISPEL_NONE)
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        auto stateIt = gBrougEmptyCourtByPlayer.find(playerGuid);
        if (stateIt == gBrougEmptyCourtByPlayer.end())
            return;

        BrougEmptyCourtRuntimeState& state = stateIt->second;
        if (state.purgedCharges == 0 || state.purgedStateUntilMs < BrougNowMs())
            return;
        if (state.purgedProtectedDispelTypes.find(spellInfo->Dispel) == state.purgedProtectedDispelTypes.end())
            return;

        aura->Remove(AURA_REMOVE_BY_DEFAULT);
        --state.purgedCharges;
        Aura* purged = state.qiReversal.purgedStateSpellId != 0
            ? player->GetAura(state.qiReversal.purgedStateSpellId, player->GetGUID())
            : nullptr;
        if (state.purgedCharges == 0)
        {
            ClearBrougPurgedState(player, state);
            return;
        }
        if (purged)
            purged->SetStackAmount(static_cast<uint8>(std::min<uint32>(state.purgedCharges, 255u)));
    }

    void HandleBrougGuardAuraRemove(Unit* unit, AuraApplication* aurApp, AuraRemoveMode /*mode*/)
    {
        if (!unit || !aurApp)
            return;

        Aura* aura = aurApp->GetBase();
        if (!aura || aura->GetId() != BROUG_DEFLECTED_SHELL_ID)
            return;

        if (HasBrougDeflectedAura(unit))
            return;

        ReleaseBrougForcedStun(unit);
        gBrougDeflectedStunUnits.erase(unit->GetGUID());
    }

    void HandleBrougGuardMeleeOutcome(
        Unit const* attacker,
        Unit const* victim,
        WeaponAttackType /*attType*/,
        int32& crit_chance,
        int32& miss_chance,
        int32& dodge_chance,
        int32& parry_chance,
        int32& block_chance)
    {
        if (!attacker || !victim)
            return;

        auto it = gBrougPendingForcedParryByVictim.find(victim->GetGUID());
        if (it == gBrougPendingForcedParryByVictim.end())
            return;

        uint64 nowMs = BrougNowMs();
        if (auto stateIt = gBrougGuardByPlayer.find(it->second.playerGuid);
            stateIt != gBrougGuardByPlayer.end() && IsBrougDeflectWindowActive(stateIt->second, nowMs))
        {
            gBrougPendingForcedParryByVictim.erase(it);
            return;
        }

        if (it->second.expiresAtMs < nowMs || it->second.attackerGuid != attacker->GetGUID())
        {
            gBrougPendingForcedParryByVictim.erase(it);
            return;
        }

        if ((!victim->HasInArc(WM_PI, attacker) && !victim->HasIgnoreHitDirectionAura())
            || victim->IsNonMeleeSpellCast(false, false, true)
            || victim->HasUnitState(UNIT_STATE_CONTROLLED))
        {
            gBrougPendingForcedParryByVictim.erase(it);
            return;
        }

        Player* player = const_cast<Unit*>(victim)->ToPlayer();
        uint32 playerGuid = it->second.playerGuid;
        bool countEvent = it->second.countEvent;
        gBrougPendingForcedParryByVictim.erase(it);

        if (!player || playerGuid == 0)
            return;

        auto stateIt = gBrougGuardByPlayer.find(playerGuid);
        if (stateIt == gBrougGuardByPlayer.end() || !stateIt->second.hasUniversalParry)
            return;

        crit_chance = 0;
        miss_chance = 0;
        dodge_chance = 0;
        block_chance = 0;
        parry_chance = std::max<int32>(parry_chance, 30000);
        PlayBrougParryFeedback(player);
        RecordBrougUniversalParrySuccess(player, playerGuid, stateIt->second, const_cast<Unit*>(attacker), countEvent);
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
