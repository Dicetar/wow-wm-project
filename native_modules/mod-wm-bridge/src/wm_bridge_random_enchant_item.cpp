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
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_CANCEL = 9999;

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
        if (action < RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_SLOT_BASE)
        {
            return false;
        }

        uint32 encoded = action - RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_SLOT_BASE;
        equipmentSlot = encoded / 10;
        enchantSlotIndex = encoded % 10;
        return equipmentSlot < EQUIPMENT_SLOT_END && enchantSlotIndex < 3;
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

        if (IsFocusedEnchantingVellum(item->GetEntry()) && action >= RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_ITEM_BASE && action < RANDOM_ENCHANT_GOSSIP_ACTION_FOCUSED_SLOT_BASE)
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

        uint32 selectedEnchantSlotIndex = 0;
        Item* targetItem = nullptr;
        bool focusedVellum = IsFocusedEnchantingVellum(item->GetEntry());
        if (focusedVellum)
        {
            uint32 equipmentSlot = 0;
            if (!DecodeFocusedSlotAction(action, equipmentSlot, selectedEnchantSlotIndex))
            {
                SendPlayerMessage(player, "Choose one enchant slot for this vellum.");
                CloseGossipMenuFor(player);
                return;
            }
            targetItem = ResolveSelectedItemFromEquipmentSlot(player, equipmentSlot);
        }
        else
        {
            targetItem = ResolveSelectedItem(player, action, RANDOM_ENCHANT_GOSSIP_ACTION_UNSTABLE_ITEM_BASE);
        }

        if (!targetItem || !WmBridge::RandomEnchant::IsEligibleItem(targetItem))
        {
            SendPlayerMessage(player, "That item is no longer eligible for random enchantment.");
            CloseGossipMenuFor(player);
            return;
        }

        WmBridge::RandomEnchant::ApplyOptions options = WmBridge::RandomEnchant::DefaultApplyOptionsFromConfig();
        uint32 focusedTier = 0;
        if (focusedVellum)
        {
            focusedTier = RollFocusedEnchantingVellumTier();
            options.maxEnchants = 1;
            options.guaranteeFirst = true;
            options.preserveExistingChancePct = 0.0f;
            options.minimumTier = 3;
            options.forcedTier = focusedTier;
            options.selectedEnchantSlotIndex = static_cast<int32>(selectedEnchantSlotIndex);
        }
        else
        {
            options.maxEnchants = 3;
            options.guaranteeFirst = true;
            options.preserveExistingChancePct = 15.0f;
            options.bonusTier = 5;
            options.bonusTierChancePct = 10.0f;
        }

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
        if (focusedVellum)
        {
            message << "Enchanting vellum rerolled one slot on " << targetItem->GetTemplate()->Name1
                    << " with tier " << focusedTier << ".";
        }
        else
        {
            message << "Unstable random enchant applied to " << targetItem->GetTemplate()->Name1 << ": "
                    << result.appliedCount << " new, " << result.preservedCount << " preserved.";
        }
        SendPlayerMessage(player, message.str());
        CloseGossipMenuFor(player);
    }
};

void AddSC_mod_wm_bridge_random_enchant_item()
{
    new wm_random_enchant_consumable();
}
