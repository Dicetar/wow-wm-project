#include "wm_bridge_random_enchant.h"

#include "DatabaseEnv.h"
#include "GossipDef.h"
#include "Item.h"
#include "ItemScript.h"
#include "Player.h"
#include "Random.h"
#include "ScriptedGossip.h"
#include "WorldSession.h"
#include "wm_bridge_common.h"

#include <algorithm>
#include <sstream>
#include <string>
#include <vector>

namespace
{
    constexpr uint32 WM_UNSTABLE_ENCHANTING_VELLUM_ITEM_ENTRY = 910007;
    constexpr uint32 WM_ENCHANTING_VELLUM_ITEM_ENTRY = 910008;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_UNSTABLE_ITEM_BASE = 1000;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_ITEM_BASE = 2000;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_SLOT_BASE = 3000;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_MODE_BASE = 4000;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CATEGORY_BASE = 10000;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_PAGE_BASE = 1000000;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CHOICE_BASE = 10000000;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_CANCEL = 9999;
    constexpr uint32 RANDOM_ENCHANT_MAX_DETERMINISTIC_CHOICES = 999;
    constexpr uint32 RANDOM_ENCHANT_DETERMINISTIC_PAGE_SIZE = 20;

    struct EquipmentSlotLabel
    {
        uint8 slot;
        char const* label;
    };

    EquipmentSlotLabel const EQUIPMENT_SLOT_LABELS[] = {
        {EQUIPMENT_SLOT_HEAD, "Head"},
        {EQUIPMENT_SLOT_NECK, "Neck"},
        {EQUIPMENT_SLOT_SHOULDERS, "Shoulders"},
        {EQUIPMENT_SLOT_BODY, "Shirt"},
        {EQUIPMENT_SLOT_CHEST, "Chest"},
        {EQUIPMENT_SLOT_WAIST, "Waist"},
        {EQUIPMENT_SLOT_LEGS, "Legs"},
        {EQUIPMENT_SLOT_FEET, "Feet"},
        {EQUIPMENT_SLOT_WRISTS, "Wrists"},
        {EQUIPMENT_SLOT_HANDS, "Hands"},
        {EQUIPMENT_SLOT_FINGER1, "Finger 1"},
        {EQUIPMENT_SLOT_FINGER2, "Finger 2"},
        {EQUIPMENT_SLOT_TRINKET1, "Trinket 1"},
        {EQUIPMENT_SLOT_TRINKET2, "Trinket 2"},
        {EQUIPMENT_SLOT_BACK, "Back"},
        {EQUIPMENT_SLOT_MAINHAND, "Main Hand"},
        {EQUIPMENT_SLOT_OFFHAND, "Off Hand"},
        {EQUIPMENT_SLOT_RANGED, "Ranged"},
        {EQUIPMENT_SLOT_TABARD, "Tabard"},
    };

    struct EnchantSlotLabel
    {
        uint8 slotIndex;
        char const* label;
    };

    EnchantSlotLabel const ENCHANT_SLOT_LABELS[] = {
        {0, "Permanent enchant slot"},
        {1, "Temporary enchant slot"},
        {2, "Bonus enchant slot"},
    };

    bool IsRandomEnchantVellum(uint32 itemEntry)
    {
        return itemEntry == WM_UNSTABLE_ENCHANTING_VELLUM_ITEM_ENTRY || itemEntry == WM_ENCHANTING_VELLUM_ITEM_ENTRY;
    }

    bool IsFocusedEnchantingVellum(uint32 itemEntry)
    {
        return itemEntry == WM_ENCHANTING_VELLUM_ITEM_ENTRY;
    }

    uint32 RollFocusedEnchantingVellumTier()
    {
        uint32 roll = urand(1, 100);
        if (roll <= 40)
            return 3;
        if (roll <= 70)
            return 4;
        return 5;
    }

    uint32 DeterministicTierCost(uint32 tier)
    {
        switch (tier)
        {
            case 3:
                return 5;
            case 4:
                return 12;
            case 5:
                return 20;
            default:
                return 0;
        }
    }

    std::string ClipGossipText(std::string value)
    {
        constexpr std::size_t maxLength = 118;
        if (value.size() <= maxLength)
        {
            return value;
        }

        return value.substr(0, maxLength - 3) + "...";
    }

    void SendPlayerMessage(Player* player, std::string const& message)
    {
        if (player && player->GetSession())
        {
            player->GetSession()->SendAreaTriggerMessage(message);
        }
    }

    std::vector<EquipmentSlotLabel> EligibleEquippedSlots(Player* player)
    {
        std::vector<EquipmentSlotLabel> slots;
        if (!player)
        {
            return slots;
        }

        for (EquipmentSlotLabel const& slotLabel : EQUIPMENT_SLOT_LABELS)
        {
            if (Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slotLabel.slot))
            {
                if (WmBridge::RandomEnchant::IsEligibleItem(item))
                {
                    slots.push_back(slotLabel);
                }
            }
        }
        return slots;
    }

    Item* ResolveSelectedItemFromEquipmentSlot(Player* player, uint32 equipmentSlot)
    {
        if (!player || equipmentSlot >= EQUIPMENT_SLOT_END)
        {
            return nullptr;
        }

        return player->GetItemByPos(INVENTORY_SLOT_BAG_0, static_cast<uint8>(equipmentSlot));
    }

    Item* ResolveSelectedItem(Player* player, uint32 action, uint32 actionBase)
    {
        if (!player || action < actionBase)
        {
            return nullptr;
        }

        return ResolveSelectedItemFromEquipmentSlot(player, action - actionBase);
    }

    uint32 FocusedSlotAction(uint8 equipmentSlot, uint8 enchantSlotIndex)
    {
        return RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_SLOT_BASE + static_cast<uint32>(equipmentSlot) * 10 + static_cast<uint32>(enchantSlotIndex);
    }

    bool DecodeFocusedSlotAction(uint32 action, uint32& equipmentSlot, uint32& enchantSlotIndex)
    {
        if (action < RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_SLOT_BASE || action >= RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_MODE_BASE)
        {
            return false;
        }

        uint32 encoded = action - RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_SLOT_BASE;
        equipmentSlot = encoded / 10;
        enchantSlotIndex = encoded % 10;
        return equipmentSlot < EQUIPMENT_SLOT_END && enchantSlotIndex < 3;
    }

    uint32 FocusedModeAction(uint8 equipmentSlot, uint8 enchantSlotIndex, uint32 tier)
    {
        return RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_MODE_BASE
            + static_cast<uint32>(equipmentSlot) * 100
            + static_cast<uint32>(enchantSlotIndex) * 10
            + tier;
    }

    bool DecodeFocusedModeAction(uint32 action, uint32& equipmentSlot, uint32& enchantSlotIndex, uint32& tier)
    {
        if (action < RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_MODE_BASE || action >= RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CATEGORY_BASE)
        {
            return false;
        }

        uint32 encoded = action - RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_MODE_BASE;
        equipmentSlot = encoded / 100;
        encoded %= 100;
        enchantSlotIndex = encoded / 10;
        tier = encoded % 10;
        return equipmentSlot < EQUIPMENT_SLOT_END && enchantSlotIndex < 3 && (tier == 0 || DeterministicTierCost(tier) > 0);
    }

    uint32 CategoryCode(WmBridge::RandomEnchant::EnchantCategory category)
    {
        return static_cast<uint32>(category);
    }

    uint32 FocusedCategoryAction(uint8 equipmentSlot, uint8 enchantSlotIndex, uint32 tier, WmBridge::RandomEnchant::EnchantCategory category)
    {
        return RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CATEGORY_BASE
            + static_cast<uint32>(equipmentSlot) * 1000
            + static_cast<uint32>(enchantSlotIndex) * 100
            + tier * 10
            + CategoryCode(category);
    }

    bool DecodeFocusedCategoryAction(uint32 action, uint32& equipmentSlot, uint32& enchantSlotIndex, uint32& tier, WmBridge::RandomEnchant::EnchantCategory& category)
    {
        if (action < RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CATEGORY_BASE || action >= RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_PAGE_BASE)
        {
            return false;
        }

        uint32 encoded = action - RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CATEGORY_BASE;
        equipmentSlot = encoded / 1000;
        encoded %= 1000;
        enchantSlotIndex = encoded / 100;
        encoded %= 100;
        tier = encoded / 10;
        uint32 categoryCode = encoded % 10;
        return equipmentSlot < EQUIPMENT_SLOT_END
            && enchantSlotIndex < 3
            && DeterministicTierCost(tier) > 0
            && WmBridge::RandomEnchant::DecodeEnchantCategory(categoryCode, category);
    }

    uint32 FocusedPageAction(uint8 equipmentSlot, uint8 enchantSlotIndex, uint32 tier, WmBridge::RandomEnchant::EnchantCategory category, uint32 page)
    {
        return RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_PAGE_BASE
            + static_cast<uint32>(equipmentSlot) * 100000
            + static_cast<uint32>(enchantSlotIndex) * 10000
            + tier * 1000
            + CategoryCode(category) * 100
            + page;
    }

    bool DecodeFocusedPageAction(
        uint32 action,
        uint32& equipmentSlot,
        uint32& enchantSlotIndex,
        uint32& tier,
        WmBridge::RandomEnchant::EnchantCategory& category,
        uint32& page)
    {
        if (action < RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_PAGE_BASE || action >= RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CHOICE_BASE)
        {
            return false;
        }

        uint32 encoded = action - RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_PAGE_BASE;
        equipmentSlot = encoded / 100000;
        encoded %= 100000;
        enchantSlotIndex = encoded / 10000;
        encoded %= 10000;
        tier = encoded / 1000;
        encoded %= 1000;
        uint32 categoryCode = encoded / 100;
        page = encoded % 100;
        return equipmentSlot < EQUIPMENT_SLOT_END
            && enchantSlotIndex < 3
            && DeterministicTierCost(tier) > 0
            && WmBridge::RandomEnchant::DecodeEnchantCategory(categoryCode, category);
    }

    uint32 FocusedChoiceAction(uint8 equipmentSlot, uint8 enchantSlotIndex, uint32 tier, WmBridge::RandomEnchant::EnchantCategory category, uint32 choiceIndex)
    {
        return RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CHOICE_BASE
            + static_cast<uint32>(equipmentSlot) * 1000000
            + static_cast<uint32>(enchantSlotIndex) * 100000
            + tier * 10000
            + CategoryCode(category) * 1000
            + choiceIndex;
    }

    bool DecodeFocusedChoiceAction(
        uint32 action,
        uint32& equipmentSlot,
        uint32& enchantSlotIndex,
        uint32& tier,
        WmBridge::RandomEnchant::EnchantCategory& category,
        uint32& choiceIndex)
    {
        if (action < RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CHOICE_BASE)
        {
            return false;
        }

        uint32 encoded = action - RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_CHOICE_BASE;
        equipmentSlot = encoded / 1000000;
        encoded %= 1000000;
        enchantSlotIndex = encoded / 100000;
        encoded %= 100000;
        tier = encoded / 10000;
        encoded %= 10000;
        uint32 categoryCode = encoded / 1000;
        choiceIndex = encoded % 1000;
        return equipmentSlot < EQUIPMENT_SLOT_END
            && enchantSlotIndex < 3
            && DeterministicTierCost(tier) > 0
            && choiceIndex < RANDOM_ENCHANT_MAX_DETERMINISTIC_CHOICES
            && WmBridge::RandomEnchant::DecodeEnchantCategory(categoryCode, category);
    }

    void AddCancelOption(Player* player)
    {
        AddGossipItemFor(
            player,
            GOSSIP_ICON_CHAT,
            "Cancel",
            GOSSIP_SENDER_MAIN,
            RANDOM_ENCHANT_GOSSIP_ACTION_CANCEL);
    }

    void ShowEquippedItemMenu(Player* player, Item* vellum, std::vector<EquipmentSlotLabel> const& slots)
    {
        ClearGossipMenuFor(player);

        uint32 actionBase = IsFocusedEnchantingVellum(vellum->GetEntry())
            ? RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_ITEM_BASE
            : RANDOM_ENCHANT_GOSSIP_ACTION_UNSTABLE_ITEM_BASE;

        for (EquipmentSlotLabel const& slotLabel : slots)
        {
            Item* equippedItem = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slotLabel.slot);
            if (!equippedItem || !equippedItem->GetTemplate())
            {
                continue;
            }

            std::ostringstream optionText;
            optionText << slotLabel.label << ": " << equippedItem->GetTemplate()->Name1;
            AddGossipItemFor(
                player,
                GOSSIP_ICON_INTERACT_1,
                optionText.str(),
                GOSSIP_SENDER_MAIN,
                actionBase + slotLabel.slot);
        }

        AddCancelOption(player);
        SendGossipMenuFor(player, DEFAULT_GOSSIP_MESSAGE, vellum->GetGUID());
    }

    void ShowEnchantSlotMenu(Player* player, Item* vellum, uint8 equipmentSlot)
    {
        ClearGossipMenuFor(player);

        Item* targetItem = ResolveSelectedItemFromEquipmentSlot(player, equipmentSlot);
        if (!targetItem || !targetItem->GetTemplate() || !WmBridge::RandomEnchant::IsEligibleItem(targetItem))
        {
            SendPlayerMessage(player, "That item is no longer eligible for random enchantment.");
            CloseGossipMenuFor(player);
            return;
        }

        for (EnchantSlotLabel const& slotLabel : ENCHANT_SLOT_LABELS)
        {
            std::ostringstream optionText;
            optionText << targetItem->GetTemplate()->Name1 << ": " << slotLabel.label;
            AddGossipItemFor(
                player,
                GOSSIP_ICON_INTERACT_1,
                optionText.str(),
                GOSSIP_SENDER_MAIN,
                FocusedSlotAction(equipmentSlot, slotLabel.slotIndex));
        }

        AddCancelOption(player);
        SendGossipMenuFor(player, DEFAULT_GOSSIP_MESSAGE, vellum->GetGUID());
    }

    void ShowFocusedEnchantModeMenu(Player* player, Item* vellum, uint8 equipmentSlot, uint8 enchantSlotIndex)
    {
        ClearGossipMenuFor(player);

        Item* targetItem = ResolveSelectedItemFromEquipmentSlot(player, equipmentSlot);
        if (!targetItem || !targetItem->GetTemplate() || !WmBridge::RandomEnchant::IsEligibleItem(targetItem))
        {
            SendPlayerMessage(player, "That item is no longer eligible for random enchantment.");
            CloseGossipMenuFor(player);
            return;
        }

        std::ostringstream randomText;
        randomText << "Random reroll: " << targetItem->GetTemplate()->Name1 << " (1 vellum, tier 3/4/5 roll)";
        AddGossipItemFor(
            player,
            GOSSIP_ICON_INTERACT_1,
            ClipGossipText(randomText.str()),
            GOSSIP_SENDER_MAIN,
            FocusedModeAction(equipmentSlot, enchantSlotIndex, 0));

        for (uint32 tier : {3u, 4u, 5u})
        {
            std::ostringstream optionText;
            optionText << "Choose tier " << tier << " enchant (" << DeterministicTierCost(tier) << " vellums)";
            AddGossipItemFor(
                player,
                GOSSIP_ICON_VENDOR,
                optionText.str(),
                GOSSIP_SENDER_MAIN,
                FocusedModeAction(equipmentSlot, enchantSlotIndex, tier));
        }

        AddCancelOption(player);
        SendGossipMenuFor(player, DEFAULT_GOSSIP_MESSAGE, vellum->GetGUID());
    }

    void ShowDeterministicEnchantCategoryMenu(Player* player, Item* vellum, uint8 equipmentSlot, uint8 enchantSlotIndex, uint32 tier)
    {
        ClearGossipMenuFor(player);

        Item* targetItem = ResolveSelectedItemFromEquipmentSlot(player, equipmentSlot);
        if (!targetItem || !targetItem->GetTemplate() || !WmBridge::RandomEnchant::IsEligibleItem(targetItem))
        {
            SendPlayerMessage(player, "That item is no longer eligible for random enchantment.");
            CloseGossipMenuFor(player);
            return;
        }

        bool hasAnyCategory = false;
        for (WmBridge::RandomEnchant::EnchantCategory category : WmBridge::RandomEnchant::EnchantCategoryOrder())
        {
            std::vector<WmBridge::RandomEnchant::EnchantChoice> choices = WmBridge::RandomEnchant::ListEnchantChoicesForItem(targetItem, tier, category);
            if (choices.empty())
            {
                continue;
            }

            hasAnyCategory = true;
            std::ostringstream optionText;
            optionText << "Tier " << tier << " " << WmBridge::RandomEnchant::EnchantCategoryLabel(category)
                       << " (" << choices.size() << " choices, " << DeterministicTierCost(tier) << " vellums)";
            AddGossipItemFor(
                player,
                GOSSIP_ICON_VENDOR,
                ClipGossipText(optionText.str()),
                GOSSIP_SENDER_MAIN,
                FocusedCategoryAction(equipmentSlot, enchantSlotIndex, tier, category));
        }

        if (!hasAnyCategory)
        {
            SendPlayerMessage(player, "No deterministic enchant choices exist for that item and tier.");
            CloseGossipMenuFor(player);
            return;
        }

        AddCancelOption(player);
        SendGossipMenuFor(player, DEFAULT_GOSSIP_MESSAGE, vellum->GetGUID());
    }

    void ShowDeterministicEnchantChoiceMenu(
        Player* player,
        Item* vellum,
        uint8 equipmentSlot,
        uint8 enchantSlotIndex,
        uint32 tier,
        WmBridge::RandomEnchant::EnchantCategory category,
        uint32 page)
    {
        ClearGossipMenuFor(player);

        Item* targetItem = ResolveSelectedItemFromEquipmentSlot(player, equipmentSlot);
        if (!targetItem || !targetItem->GetTemplate() || !WmBridge::RandomEnchant::IsEligibleItem(targetItem))
        {
            SendPlayerMessage(player, "That item is no longer eligible for random enchantment.");
            CloseGossipMenuFor(player);
            return;
        }

        std::vector<WmBridge::RandomEnchant::EnchantChoice> choices = WmBridge::RandomEnchant::ListEnchantChoicesForItem(targetItem, tier, category);
        if (choices.empty())
        {
            SendPlayerMessage(player, "No deterministic enchant choices exist for that category.");
            CloseGossipMenuFor(player);
            return;
        }

        uint32 choiceCount = std::min<uint32>(static_cast<uint32>(choices.size()), RANDOM_ENCHANT_MAX_DETERMINISTIC_CHOICES);
        uint32 pageCount = (choiceCount + RANDOM_ENCHANT_DETERMINISTIC_PAGE_SIZE - 1) / RANDOM_ENCHANT_DETERMINISTIC_PAGE_SIZE;
        if (pageCount == 0)
        {
            SendPlayerMessage(player, "No deterministic enchant choices exist for that category.");
            CloseGossipMenuFor(player);
            return;
        }

        page = std::min<uint32>(page, pageCount - 1);
        uint32 startIndex = page * RANDOM_ENCHANT_DETERMINISTIC_PAGE_SIZE;
        uint32 endIndex = std::min<uint32>(choiceCount, startIndex + RANDOM_ENCHANT_DETERMINISTIC_PAGE_SIZE);

        for (uint32 choiceIndex = startIndex; choiceIndex < endIndex; ++choiceIndex)
        {
            std::ostringstream optionText;
            optionText << "Apply " << choices[choiceIndex].label << " (" << DeterministicTierCost(tier) << " vellums)";
            AddGossipItemFor(
                player,
                GOSSIP_ICON_VENDOR,
                ClipGossipText(optionText.str()),
                GOSSIP_SENDER_MAIN,
                FocusedChoiceAction(equipmentSlot, enchantSlotIndex, tier, category, choiceIndex));
        }

        if (page > 0)
        {
            std::ostringstream optionText;
            optionText << "Previous page (" << page << "/" << pageCount << ")";
            AddGossipItemFor(
                player,
                GOSSIP_ICON_CHAT,
                optionText.str(),
                GOSSIP_SENDER_MAIN,
                FocusedPageAction(equipmentSlot, enchantSlotIndex, tier, category, page - 1));
        }

        if (endIndex < choiceCount)
        {
            std::ostringstream optionText;
            optionText << "Next page (" << (page + 2) << "/" << pageCount << ")";
            AddGossipItemFor(
                player,
                GOSSIP_ICON_CHAT,
                optionText.str(),
                GOSSIP_SENDER_MAIN,
                FocusedPageAction(equipmentSlot, enchantSlotIndex, tier, category, page + 1));
        }

        if (choices.size() > RANDOM_ENCHANT_MAX_DETERMINISTIC_CHOICES)
        {
            SendPlayerMessage(player, "Only the first 999 matching enchants are available in this category.");
        }

        AddCancelOption(player);
        SendGossipMenuFor(player, DEFAULT_GOSSIP_MESSAGE, vellum->GetGUID());
    }
}

class wm_random_enchant_consumable : public ItemScript
{
public:
    wm_random_enchant_consumable() : ItemScript("wm_random_enchant_consumable") { }

    bool OnUse(Player* player, Item* item, SpellCastTargets const& /*targets*/) override
    {
        if (!player || !item || !IsRandomEnchantVellum(item->GetEntry()))
        {
            return true;
        }

        if (!WmBridge::IsPlayerAllowed(player))
        {
            SendPlayerMessage(player, "WM enchant vellum is inactive for this character.");
            return true;
        }

        std::vector<EquipmentSlotLabel> slots = EligibleEquippedSlots(player);
        ClearGossipMenuFor(player);
        if (slots.empty())
        {
            SendPlayerMessage(player, "Equip a weapon or armor item before using the enchant vellum.");
            CloseGossipMenuFor(player);
            return true;
        }

        ShowEquippedItemMenu(player, item, slots);
        return true;
    }

    void OnGossipSelect(Player* player, Item* item, uint32 sender, uint32 action) override
    {
        if (!player || !item || !IsRandomEnchantVellum(item->GetEntry()))
        {
            return;
        }

        ClearGossipMenuFor(player);
        if (sender != GOSSIP_SENDER_MAIN || action == RANDOM_ENCHANT_GOSSIP_ACTION_CANCEL)
        {
            CloseGossipMenuFor(player);
            return;
        }

        if (!WmBridge::IsPlayerAllowed(player))
        {
            SendPlayerMessage(player, "WM enchant vellum is inactive for this character.");
            CloseGossipMenuFor(player);
            return;
        }

        bool focusedVellum = IsFocusedEnchantingVellum(item->GetEntry());
        if (focusedVellum && action >= RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_ITEM_BASE && action < RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_SLOT_BASE)
        {
            uint32 equipmentSlot = action - RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_ITEM_BASE;
            if (equipmentSlot >= EQUIPMENT_SLOT_END)
            {
                SendPlayerMessage(player, "That equipment slot is not valid for this vellum.");
                CloseGossipMenuFor(player);
                return;
            }

            ShowEnchantSlotMenu(player, item, static_cast<uint8>(equipmentSlot));
            return;
        }

        if (focusedVellum)
        {
            uint32 equipmentSlot = 0;
            uint32 selectedEnchantSlotIndex = 0;
            if (DecodeFocusedSlotAction(action, equipmentSlot, selectedEnchantSlotIndex))
            {
                ShowFocusedEnchantModeMenu(player, item, static_cast<uint8>(equipmentSlot), static_cast<uint8>(selectedEnchantSlotIndex));
                return;
            }

            uint32 deterministicTier = 0;
            if (DecodeFocusedModeAction(action, equipmentSlot, selectedEnchantSlotIndex, deterministicTier))
            {
                if (deterministicTier != 0)
                {
                    ShowDeterministicEnchantCategoryMenu(
                        player,
                        item,
                        static_cast<uint8>(equipmentSlot),
                        static_cast<uint8>(selectedEnchantSlotIndex),
                        deterministicTier);
                    return;
                }

                Item* targetItem = ResolveSelectedItemFromEquipmentSlot(player, equipmentSlot);
                if (!targetItem || !WmBridge::RandomEnchant::IsEligibleItem(targetItem))
                {
                    SendPlayerMessage(player, "That item is no longer eligible for random enchantment.");
                    CloseGossipMenuFor(player);
                    return;
                }

                uint32 focusedTier = RollFocusedEnchantingVellumTier();
                WmBridge::RandomEnchant::ApplyOptions options = WmBridge::RandomEnchant::DefaultApplyOptionsFromConfig();
                options.maxEnchants = 1;
                options.guaranteeFirst = true;
                options.preserveExistingChancePct = 0.0f;
                options.minimumTier = 3;
                options.forcedTier = focusedTier;
                options.selectedEnchantSlotIndex = static_cast<int32>(selectedEnchantSlotIndex);

                WmBridge::RandomEnchant::ApplyResult result = WmBridge::RandomEnchant::ApplyToItem(player, targetItem, options);
                if (!result.ok || result.appliedCount == 0)
                {
                    SendPlayerMessage(player, "No compatible random enchant took hold. The vellum was not consumed.");
                    CloseGossipMenuFor(player);
                    return;
                }

                uint32 destroyCount = 1;
                player->DestroyItemCount(item, destroyCount, true);

                CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
                player->SaveInventoryAndGoldToDB(trans);
                CharacterDatabase.CommitTransaction(trans);

                std::ostringstream message;
                message << "Enchanting vellum rerolled one slot on " << targetItem->GetTemplate()->Name1
                        << " with tier " << focusedTier << ".";
                SendPlayerMessage(player, message.str());
                CloseGossipMenuFor(player);
                return;
            }

            WmBridge::RandomEnchant::EnchantCategory category = WmBridge::RandomEnchant::EnchantCategory::Other;
            if (DecodeFocusedCategoryAction(action, equipmentSlot, selectedEnchantSlotIndex, deterministicTier, category))
            {
                ShowDeterministicEnchantChoiceMenu(
                    player,
                    item,
                    static_cast<uint8>(equipmentSlot),
                    static_cast<uint8>(selectedEnchantSlotIndex),
                    deterministicTier,
                    category,
                    0);
                return;
            }

            uint32 page = 0;
            if (DecodeFocusedPageAction(action, equipmentSlot, selectedEnchantSlotIndex, deterministicTier, category, page))
            {
                ShowDeterministicEnchantChoiceMenu(
                    player,
                    item,
                    static_cast<uint8>(equipmentSlot),
                    static_cast<uint8>(selectedEnchantSlotIndex),
                    deterministicTier,
                    category,
                    page);
                return;
            }

            uint32 choiceIndex = 0;
            if (DecodeFocusedChoiceAction(action, equipmentSlot, selectedEnchantSlotIndex, deterministicTier, category, choiceIndex))
            {
                Item* targetItem = ResolveSelectedItemFromEquipmentSlot(player, equipmentSlot);
                if (!targetItem || !targetItem->GetTemplate() || !WmBridge::RandomEnchant::IsEligibleItem(targetItem))
                {
                    SendPlayerMessage(player, "That item is no longer eligible for random enchantment.");
                    CloseGossipMenuFor(player);
                    return;
                }

                uint32 destroyCount = DeterministicTierCost(deterministicTier);
                if (destroyCount == 0 || player->GetItemCount(WM_ENCHANTING_VELLUM_ITEM_ENTRY, false) < destroyCount)
                {
                    std::ostringstream message;
                    message << "You need " << destroyCount << " Enchanting Vellums for that deterministic tier.";
                    SendPlayerMessage(player, message.str());
                    CloseGossipMenuFor(player);
                    return;
                }

                std::vector<WmBridge::RandomEnchant::EnchantChoice> choices = WmBridge::RandomEnchant::ListEnchantChoicesForItem(targetItem, deterministicTier, category);
                if (choiceIndex >= choices.size())
                {
                    SendPlayerMessage(player, "That deterministic enchant choice is no longer available.");
                    CloseGossipMenuFor(player);
                    return;
                }

                WmBridge::RandomEnchant::EnchantChoice const& choice = choices[choiceIndex];
                WmBridge::RandomEnchant::ApplyResult result = WmBridge::RandomEnchant::ApplyExactToItem(
                    player,
                    targetItem,
                    choice.enchantId,
                    static_cast<int32>(selectedEnchantSlotIndex));
                if (!result.ok || result.appliedCount == 0)
                {
                    SendPlayerMessage(player, "The deterministic enchant could not be applied. The vellums were not consumed.");
                    CloseGossipMenuFor(player);
                    return;
                }

                player->DestroyItemCount(WM_ENCHANTING_VELLUM_ITEM_ENTRY, destroyCount, true, true);

                CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
                player->SaveInventoryAndGoldToDB(trans);
                CharacterDatabase.CommitTransaction(trans);

                std::ostringstream message;
                message << "Applied tier " << deterministicTier << " " << WmBridge::RandomEnchant::EnchantCategoryLabel(category)
                        << " enchant to " << targetItem->GetTemplate()->Name1 << ": " << choice.label
                        << " (" << destroyCount << " vellums).";
                SendPlayerMessage(player, message.str());
                CloseGossipMenuFor(player);
                return;
            }

            SendPlayerMessage(player, "Choose one enchant slot and mode for this vellum.");
            CloseGossipMenuFor(player);
            return;
        }

        Item* targetItem = ResolveSelectedItem(player, action, RANDOM_ENCHANT_GOSSIP_ACTION_UNSTABLE_ITEM_BASE);
        if (!targetItem || !WmBridge::RandomEnchant::IsEligibleItem(targetItem))
        {
            SendPlayerMessage(player, "That item is no longer eligible for random enchantment.");
            CloseGossipMenuFor(player);
            return;
        }

        WmBridge::RandomEnchant::ApplyOptions options = WmBridge::RandomEnchant::DefaultApplyOptionsFromConfig();
        options.maxEnchants = 3;
        options.guaranteeFirst = true;
        options.preserveExistingChancePct = 15.0f;
        options.bonusTier = 5;
        options.bonusTierChancePct = 10.0f;

        WmBridge::RandomEnchant::ApplyResult result = WmBridge::RandomEnchant::ApplyToItem(player, targetItem, options);
        if (!result.ok || (result.appliedCount == 0 && result.preservedCount == 0))
        {
            SendPlayerMessage(player, "No compatible random enchant took hold. The vellum was not consumed.");
            CloseGossipMenuFor(player);
            return;
        }

        uint32 destroyCount = 1;
        player->DestroyItemCount(item, destroyCount, true);

        CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
        player->SaveInventoryAndGoldToDB(trans);
        CharacterDatabase.CommitTransaction(trans);

        std::ostringstream message;
        message << "Unstable random enchant applied to " << targetItem->GetTemplate()->Name1 << ": "
                << result.appliedCount << " new, " << result.preservedCount << " preserved.";
        SendPlayerMessage(player, message.str());
        CloseGossipMenuFor(player);
    }
};

void AddSC_mod_wm_bridge_random_enchant_item()
{
    new wm_random_enchant_consumable();
}
