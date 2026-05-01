#include "wm_bridge_random_enchant.h"

#include "Configuration/Config.h"
#include "DBCStores.h"
#include "DatabaseEnv.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Player.h"
#include "Random.h"

#include <algorithm>
#include <cctype>
#include <initializer_list>
#include <sstream>

namespace
{
    constexpr uint32 RANDOM_ENCHANT_MIN_TIER = 1;
    constexpr uint32 RANDOM_ENCHANT_MAX_TIER = 5;

    uint32 ClampEnchantTier(uint32 tier)
    {
        return std::clamp<uint32>(tier, RANDOM_ENCHANT_MIN_TIER, RANDOM_ENCHANT_MAX_TIER);
    }

    char const* RandomEnchantClassKey(Item const* item)
    {
        return item && item->GetTemplate() && item->GetTemplate()->Class == ITEM_CLASS_WEAPON ? "WEAPON" : "ARMOR";
    }

    std::string EnchantDescription(SpellItemEnchantmentEntry const* enchant)
    {
        if (!enchant || !enchant->description[0])
        {
            return "";
        }

        return enchant->description[0];
    }

    std::string LowerCopy(std::string value)
    {
        std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
        return value;
    }

    bool ContainsAny(std::string const& haystack, std::initializer_list<char const*> needles)
    {
        for (char const* needle : needles)
        {
            if (haystack.find(needle) != std::string::npos)
            {
                return true;
            }
        }
        return false;
    }

    WmBridge::RandomEnchant::EnchantCategory ClassifyEnchant(SpellItemEnchantmentEntry const* enchant)
    {
        std::string text = LowerCopy(EnchantDescription(enchant));

        if (ContainsAny(text, {"strength", "agility", "stamina", "intellect", "spirit", "all stats", "mana", "health"}))
        {
            return WmBridge::RandomEnchant::EnchantCategory::Stats;
        }

        if (ContainsAny(text, {"resistance", "resist"}))
        {
            return WmBridge::RandomEnchant::EnchantCategory::Resistances;
        }

        if (ContainsAny(text, {"defense", "dodge", "parry", "block", "armor", "shield"}))
        {
            return WmBridge::RandomEnchant::EnchantCategory::Defense;
        }

        if (ContainsAny(text, {"critical", "crit", "hit", "haste", "expertise", "resilience", "penetration rating"}))
        {
            return WmBridge::RandomEnchant::EnchantCategory::CombatRatings;
        }

        if (ContainsAny(text, {"damage", "spell power", "attack power", "healing", "ranged", "fire", "frost", "nature", "shadow", "arcane", "holy", "bleed", "massacre", "icebreaker", "berserking"}))
        {
            return WmBridge::RandomEnchant::EnchantCategory::Damage;
        }

        if (ContainsAny(text, {"speed", "threat", "stealth", "mount", "fishing", "skinning", "mining", "herbalism"}))
        {
            return WmBridge::RandomEnchant::EnchantCategory::Utility;
        }

        return WmBridge::RandomEnchant::EnchantCategory::Other;
    }

    std::string EnchantChoiceLabel(uint32 enchantId, SpellItemEnchantmentEntry const* enchant)
    {
        std::ostringstream label;
        label << "#" << enchantId;
        std::string description = EnchantDescription(enchant);
        if (!description.empty())
        {
            label << ": " << description;
        }
        return label.str();
    }

    uint8 RandomEnchantTierForItem(Item const* item)
    {
        if (!item || !item->GetTemplate())
        {
            return 0;
        }

        int rarityRoll = -1;
        switch (item->GetTemplate()->Quality)
        {
            case ITEM_QUALITY_NORMAL:
                rarityRoll = static_cast<int>(urand(0, 49));
                break;
            case ITEM_QUALITY_UNCOMMON:
                rarityRoll = 45 + static_cast<int>(urand(0, 19));
                break;
            case ITEM_QUALITY_RARE:
                rarityRoll = 65 + static_cast<int>(urand(0, 14));
                break;
            case ITEM_QUALITY_EPIC:
                rarityRoll = 80 + static_cast<int>(urand(0, 13));
                break;
            case ITEM_QUALITY_LEGENDARY:
                rarityRoll = 93;
                break;
            default:
                return 0;
        }

        if (rarityRoll <= 44)
            return 1;
        if (rarityRoll <= 64)
            return 2;
        if (rarityRoll <= 79)
            return 3;
        if (rarityRoll <= 92)
            return 4;
        return 5;
    }
}

namespace WmBridge
{
namespace RandomEnchant
{
    uint32 ResolveRandomEnchantTierForItem(Item const* item, ApplyOptions const& options)
    {
        if (options.forcedTier > 0)
        {
            return ClampEnchantTier(options.forcedTier);
        }

        uint32 tier = RandomEnchantTierForItem(item);
        if (tier == 0)
        {
            return 0;
        }

        if (options.bonusTier > 0 && options.bonusTierChancePct > 0.0f && roll_chance_f(std::clamp<float>(options.bonusTierChancePct, 0.0f, 100.0f)))
        {
            tier = ClampEnchantTier(options.bonusTier);
        }

        if (options.minimumTier > 0)
        {
            tier = std::max<uint32>(tier, ClampEnchantTier(options.minimumTier));
        }

        return ClampEnchantTier(tier);
    }

    ApplyOptions DefaultApplyOptionsFromConfig()
    {
        ApplyOptions options;
        options.enchantChance1 = sConfigMgr->GetOption<float>("RandomEnchants.EnchantChance1", 70.0f);
        options.enchantChance2 = sConfigMgr->GetOption<float>("RandomEnchants.EnchantChance2", 65.0f);
        options.enchantChance3 = sConfigMgr->GetOption<float>("RandomEnchants.EnchantChance3", 60.0f);
        return options;
    }

    bool IsEligibleItem(Item const* item)
    {
        if (!item || !item->GetTemplate())
        {
            return false;
        }

        ItemTemplate const* itemTemplate = item->GetTemplate();
        if (itemTemplate->Quality < ITEM_QUALITY_NORMAL || itemTemplate->Quality > ITEM_QUALITY_LEGENDARY)
        {
            return false;
        }

        return itemTemplate->Class == ITEM_CLASS_WEAPON || itemTemplate->Class == ITEM_CLASS_ARMOR;
    }

    char const* EnchantCategoryLabel(EnchantCategory category)
    {
        switch (category)
        {
            case EnchantCategory::Stats:
                return "Stats";
            case EnchantCategory::Damage:
                return "Damage / Power";
            case EnchantCategory::CombatRatings:
                return "Combat ratings";
            case EnchantCategory::Defense:
                return "Defense";
            case EnchantCategory::Resistances:
                return "Resistances";
            case EnchantCategory::Utility:
                return "Utility";
            case EnchantCategory::Other:
            default:
                return "Other";
        }
    }

    bool DecodeEnchantCategory(uint32 categoryCode, EnchantCategory& category)
    {
        switch (categoryCode)
        {
            case 1:
                category = EnchantCategory::Stats;
                return true;
            case 2:
                category = EnchantCategory::Damage;
                return true;
            case 3:
                category = EnchantCategory::CombatRatings;
                return true;
            case 4:
                category = EnchantCategory::Defense;
                return true;
            case 5:
                category = EnchantCategory::Resistances;
                return true;
            case 6:
                category = EnchantCategory::Utility;
                return true;
            case 7:
                category = EnchantCategory::Other;
                return true;
            default:
                category = EnchantCategory::Other;
                return false;
        }
    }

    std::vector<EnchantCategory> EnchantCategoryOrder()
    {
        return {
            EnchantCategory::Stats,
            EnchantCategory::Damage,
            EnchantCategory::CombatRatings,
            EnchantCategory::Defense,
            EnchantCategory::Resistances,
            EnchantCategory::Utility,
            EnchantCategory::Other,
        };
    }

    std::vector<EnchantChoice> ListEnchantChoicesForItem(Item* item, uint32 tier, EnchantCategory category)
    {
        std::vector<EnchantChoice> choices;
        if (!IsEligibleItem(item))
        {
            return choices;
        }

        tier = ClampEnchantTier(tier);
        char const* classKey = RandomEnchantClassKey(item);
        QueryResult result = WorldDatabase.Query(
            "SELECT DISTINCT `enchantID` FROM `item_enchantment_random_tiers` "
            "WHERE `tier` = {} "
            "AND (`exclusiveSubClass` IS NULL OR `exclusiveSubClass` = {}) "
            "AND (`class` = '{}' OR `class` = 'ANY') "
            "ORDER BY `enchantID`",
            tier,
            item->GetTemplate()->SubClass,
            classKey);
        if (!result)
        {
            return choices;
        }

        do
        {
            uint32 enchantId = result->Fetch()[0].Get<uint32>();
            SpellItemEnchantmentEntry const* enchant = sSpellItemEnchantmentStore.LookupEntry(enchantId);
            if (!enchant)
            {
                continue;
            }

            EnchantCategory enchantCategory = ClassifyEnchant(enchant);
            if (enchantCategory != category)
            {
                continue;
            }

            EnchantChoice choice;
            choice.enchantId = enchantId;
            choice.category = enchantCategory;
            choice.label = EnchantChoiceLabel(enchantId, enchant);
            choices.push_back(choice);
        } while (result->NextRow());

        return choices;
    }

    uint32 SelectRandomEnchantForItem(Item* item)
    {
        return SelectRandomEnchantForItem(item, ApplyOptions());
    }

    uint32 SelectRandomEnchantForItem(Item* item, ApplyOptions const& options)
    {
        if (!IsEligibleItem(item))
        {
            return 0;
        }

        char const* classKey = RandomEnchantClassKey(item);
        uint32 tier = ResolveRandomEnchantTierForItem(item, options);
        if (tier == 0)
        {
            return 0;
        }

        QueryResult result = WorldDatabase.Query(
            "SELECT `enchantID` FROM `item_enchantment_random_tiers` "
            "WHERE `tier` = {} "
            "AND (`exclusiveSubClass` IS NULL OR `exclusiveSubClass` = {}) "
            "AND (`class` = '{}' OR `class` = 'ANY') "
            "ORDER BY RAND() LIMIT 1",
            static_cast<uint32>(tier),
            item->GetTemplate()->SubClass,
            classKey);
        if (!result)
        {
            return 0;
        }

        uint32 enchantId = result->Fetch()[0].Get<uint32>();
        return sSpellItemEnchantmentStore.LookupEntry(enchantId) ? enchantId : 0;
    }

    ApplyResult ApplyToItem(Player* player, Item* item, ApplyOptions const& rawOptions)
    {
        ApplyResult result;
        if (!player)
        {
            result.message = "player_not_online";
            return result;
        }
        if (!IsEligibleItem(item))
        {
            result.message = "item_not_random_enchant_eligible";
            return result;
        }

        result.ok = true;
        result.message = "random_enchant_not_applied";
        result.itemEntry = item->GetEntry();
        result.itemGuidLow = static_cast<uint32>(item->GetGUID().GetCounter());

        ApplyOptions options = rawOptions;
        options.maxEnchants = std::clamp<uint32>(options.maxEnchants, 1, 3);
        options.preserveExistingChancePct = std::clamp<float>(options.preserveExistingChancePct, 0.0f, 100.0f);
        options.minimumTier = options.minimumTier == 0 ? 0 : ClampEnchantTier(options.minimumTier);
        options.forcedTier = options.forcedTier == 0 ? 0 : ClampEnchantTier(options.forcedTier);
        options.bonusTier = options.bonusTier == 0 ? 0 : ClampEnchantTier(options.bonusTier);
        options.bonusTierChancePct = std::clamp<float>(options.bonusTierChancePct, 0.0f, 100.0f);
        options.enchantChance1 = std::clamp<float>(options.enchantChance1, 0.0f, 100.0f);
        options.enchantChance2 = std::clamp<float>(options.enchantChance2, 0.0f, 100.0f);
        options.enchantChance3 = std::clamp<float>(options.enchantChance3, 0.0f, 100.0f);

        EnchantmentSlot enchantSlots[3] = {PERM_ENCHANTMENT_SLOT, TEMP_ENCHANTMENT_SLOT, BONUS_ENCHANTMENT_SLOT};
        float rollChances[3] = {options.enchantChance1, options.enchantChance2, options.enchantChance3};
        if (options.selectedEnchantSlotIndex > 2)
        {
            result.ok = false;
            result.message = "invalid_enchant_slot";
            return result;
        }
        uint32 iterationCount = options.selectedEnchantSlotIndex >= 0 ? 1 : options.maxEnchants;

        for (uint32 i = 0; i < iterationCount; ++i)
        {
            uint32 slotIndex = options.selectedEnchantSlotIndex >= 0 ? static_cast<uint32>(options.selectedEnchantSlotIndex) : i;
            uint32 chanceIndex = options.selectedEnchantSlotIndex >= 0 ? 0 : i;
            if (!(i == 0 && options.guaranteeFirst) && !roll_chance_f(rollChances[chanceIndex]))
            {
                break;
            }

            EnchantmentSlot slot = enchantSlots[slotIndex];
            uint32 oldEnchantId = item->GetEnchantmentId(slot);
            if (oldEnchantId != 0 && roll_chance_f(options.preserveExistingChancePct))
            {
                ++result.preservedCount;
                continue;
            }

            uint32 enchantId = SelectRandomEnchantForItem(item, options);
            if (enchantId == 0)
            {
                continue;
            }

            if (oldEnchantId != 0)
            {
                ++result.replacedCount;
            }
            player->ApplyEnchantment(item, slot, false);
            item->SetEnchantment(slot, enchantId, 0, 0, player->GetGUID());
            player->ApplyEnchantment(item, slot, true);
            item->SetState(ITEM_CHANGED, player);

            if (result.firstEnchantId == 0)
            {
                result.firstEnchantId = enchantId;
            }
            result.lastEnchantId = enchantId;
            ++result.appliedCount;
        }

        if (result.appliedCount > 0)
        {
            result.message = "random_enchant_applied";
        }
        else if (result.preservedCount > 0)
        {
            result.message = "random_enchant_preserved_existing";
        }

        return result;
    }

    ApplyResult ApplyExactToItem(Player* player, Item* item, uint32 enchantId, int32 selectedEnchantSlotIndex)
    {
        ApplyResult result;
        if (!player)
        {
            result.message = "player_not_online";
            return result;
        }
        if (!IsEligibleItem(item))
        {
            result.message = "item_not_random_enchant_eligible";
            return result;
        }
        if (selectedEnchantSlotIndex < 0 || selectedEnchantSlotIndex > 2)
        {
            result.message = "invalid_enchant_slot";
            return result;
        }
        if (!sSpellItemEnchantmentStore.LookupEntry(enchantId))
        {
            result.message = "invalid_enchant_id";
            return result;
        }

        result.ok = true;
        result.message = "deterministic_enchant_applied";
        result.itemEntry = item->GetEntry();
        result.itemGuidLow = static_cast<uint32>(item->GetGUID().GetCounter());
        result.firstEnchantId = enchantId;
        result.lastEnchantId = enchantId;

        EnchantmentSlot enchantSlots[3] = {PERM_ENCHANTMENT_SLOT, TEMP_ENCHANTMENT_SLOT, BONUS_ENCHANTMENT_SLOT};
        EnchantmentSlot slot = enchantSlots[selectedEnchantSlotIndex];
        uint32 oldEnchantId = item->GetEnchantmentId(slot);
        if (oldEnchantId != 0)
        {
            ++result.replacedCount;
        }

        player->ApplyEnchantment(item, slot, false);
        item->SetEnchantment(slot, enchantId, 0, 0, player->GetGUID());
        player->ApplyEnchantment(item, slot, true);
        item->SetState(ITEM_CHANGED, player);
        ++result.appliedCount;

        return result;
    }
}
}
