#include "wm_bridge_random_enchant.h"

#include "DatabaseEnv.h"
#include "GossipDef.h"
#include "Item.h"
#include "ItemScript.h"
#include "Player.h"
#include "ScriptedGossip.h"
#include "WorldSession.h"
#include "wm_bridge_common.h"

#include <sstream>
#include <string>
#include <vector>

namespace
{
    constexpr uint32 WM_RANDOM_ENCHANT_CONSUMABLE_ITEM_ENTRY = 910007;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_SLOT_BASE = 1000;
    constexpr uint32 RANDOM_ENCHANT_GOSSIP_ACTION_CANCEL = 1999;

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

    Item* ResolveSelectedItem(Player* player, uint32 action)
    {
        if (!player || action < RANDOM_ENCHANT_GOSSIP_ACTION_SLOT_BASE)
        {
            return nullptr;
        }

        uint32 slot = action - RANDOM_ENCHANT_GOSSIP_ACTION_SLOT_BASE;
        if (slot >= EQUIPMENT_SLOT_END)
        {
            return nullptr;
        }

        return player->GetItemByPos(INVENTORY_SLOT_BAG_0, static_cast<uint8>(slot));
    }
}

class wm_random_enchant_consumable : public ItemScript
{
public:
    wm_random_enchant_consumable() : ItemScript("wm_random_enchant_consumable") { }

    bool OnUse(Player* player, Item* item, SpellCastTargets const& /*targets*/) override
    {
        if (!player || !item || item->GetEntry() != WM_RANDOM_ENCHANT_CONSUMABLE_ITEM_ENTRY)
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
                RANDOM_ENCHANT_GOSSIP_ACTION_SLOT_BASE + slotLabel.slot);
        }

        AddGossipItemFor(
            player,
            GOSSIP_ICON_CHAT,
            "Cancel",
            GOSSIP_SENDER_MAIN,
            RANDOM_ENCHANT_GOSSIP_ACTION_CANCEL);
        SendGossipMenuFor(player, DEFAULT_GOSSIP_MESSAGE, item->GetGUID());
        return true;
    }

    void OnGossipSelect(Player* player, Item* item, uint32 sender, uint32 action) override
    {
        if (!player || !item || item->GetEntry() != WM_RANDOM_ENCHANT_CONSUMABLE_ITEM_ENTRY)
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

        Item* targetItem = ResolveSelectedItem(player, action);
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
        message << "Random enchant applied to " << targetItem->GetTemplate()->Name1 << ": "
                << result.appliedCount << " new, " << result.preservedCount << " preserved.";
        SendPlayerMessage(player, message.str());
        CloseGossipMenuFor(player);
    }
};

void AddSC_mod_wm_bridge_random_enchant_item()
{
    new wm_random_enchant_consumable();
}
