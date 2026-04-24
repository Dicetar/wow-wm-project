#pragma once

#include "Common.h"

#include <string>

class Item;
class Player;

namespace WmBridge
{
namespace RandomEnchant
{
    struct ApplyOptions
    {
        uint32 maxEnchants = 3;
        bool guaranteeFirst = true;
        float preserveExistingChancePct = 15.0f;
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
    uint32 SelectRandomEnchantForItem(Item* item);
    ApplyResult ApplyToItem(Player* player, Item* item, ApplyOptions const& options);
}
}
