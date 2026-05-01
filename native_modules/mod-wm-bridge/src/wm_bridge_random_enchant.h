#pragma once

#include "Common.h"

#include <string>
#include <vector>

class Item;
class Player;

namespace WmBridge
{
namespace RandomEnchant
{
    enum class EnchantCategory : uint8
    {
        Stats = 1,
        Damage = 2,
        CombatRatings = 3,
        Defense = 4,
        Resistances = 5,
        Utility = 6,
        Other = 7,
    };

    struct EnchantChoice
    {
        uint32 enchantId = 0;
        EnchantCategory category = EnchantCategory::Other;
        std::string label;
    };

    struct ApplyOptions
    {
        uint32 maxEnchants = 3;
        bool guaranteeFirst = true;
        float preserveExistingChancePct = 15.0f;
        uint32 minimumTier = 0;
        uint32 forcedTier = 0;
        uint32 bonusTier = 0;
        float bonusTierChancePct = 0.0f;
        int32 selectedEnchantSlotIndex = -1;
        float enchantChance1 = 70.0f;
        float enchantChance2 = 65.0f;
        float enchantChance3 = 60.0f;
    };

    struct ApplyResult
    {
        bool ok = false;
        std::string message;
        uint32 itemEntry = 0;
        uint32 itemGuidLow = 0;
        uint32 appliedCount = 0;
        uint32 replacedCount = 0;
        uint32 preservedCount = 0;
        uint32 firstEnchantId = 0;
        uint32 lastEnchantId = 0;
    };

    ApplyOptions DefaultApplyOptionsFromConfig();
    bool IsEligibleItem(Item const* item);
    char const* EnchantCategoryLabel(EnchantCategory category);
    bool DecodeEnchantCategory(uint32 categoryCode, EnchantCategory& category);
    std::vector<EnchantCategory> EnchantCategoryOrder();
    std::vector<EnchantChoice> ListEnchantChoicesForItem(Item* item, uint32 tier, EnchantCategory category);
    uint32 SelectRandomEnchantForItem(Item* item);
    uint32 SelectRandomEnchantForItem(Item* item, ApplyOptions const& options);
    ApplyResult ApplyToItem(Player* player, Item* item, ApplyOptions const& options);
    ApplyResult ApplyExactToItem(Player* player, Item* item, uint32 enchantId, int32 selectedEnchantSlotIndex);
}
}
