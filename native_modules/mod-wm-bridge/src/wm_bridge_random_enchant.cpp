#include "wm_bridge_random_enchant.h"

#include "Configuration/Config.h"
#include "DBCStores.h"
#include "DatabaseEnv.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Player.h"
#include "Random.h"

#include <algorithm>

namespace
{
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

    uint32 SelectRandomEnchantForItem(Item* item)
    {
        if (!IsEligibleItem(item))
        {
            return 0;
        }

        char const* classKey = item->GetTemplate()->Class == ITEM_CLASS_WEAPON ? "WEAPON" : "ARMOR";
        uint8 tier = RandomEnchantTierForItem(item);
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
        options.enchantChance1 = std::clamp<float>(options.enchantChance1, 0.0f, 100.0f);
        options.enchantChance2 = std::clamp<float>(options.enchantChance2, 0.0f, 100.0f);
        options.enchantChance3 = std::clamp<float>(options.enchantChance3, 0.0f, 100.0f);

        EnchantmentSlot enchantSlots[3] = {PERM_ENCHANTMENT_SLOT, TEMP_ENCHANTMENT_SLOT, BONUS_ENCHANTMENT_SLOT};
        float rollChances[3] = {options.enchantChance1, options.enchantChance2, options.enchantChance3};

        for (uint32 i = 0; i < options.maxEnchants; ++i)
        {
            if (!(i == 0 && options.guaranteeFirst) && !roll_chance_f(rollChances[i]))
            {
                break;
            }

            EnchantmentSlot slot = enchantSlots[i];
            uint32 oldEnchantId = item->GetEnchantmentId(slot);
            if (oldEnchantId != 0 && roll_chance_f(options.preserveExistingChancePct))
            {
                ++result.preservedCount;
                continue;
            }

            uint32 enchantId = SelectRandomEnchantForItem(item);
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
}
}
