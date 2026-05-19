// Phase 0D: inventory-domain native WM action handlers. Bodies moved
// verbatim from wm_bridge_action_queue.cpp; shared infra lives in
// wm_bridge_action_support.h (WmBridge::detail). Registered via
// RegisterWmBridgeInventoryActions from the queue bootstrap.

#include "Configuration/Config.h"
#include "DatabaseEnv.h"
#include "Cell.h"
#include "CellImpl.h"
#include "Creature.h"
#include "DBCStores.h"
#include "GameObject.h"
#include "GridNotifiers.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QueryResult.h"
#include "Random.h"
#include "ReputationMgr.h"
#include "SpellMgr.h"
#include "TemporarySummon.h"
#include "Unit.h"
#include "WorldSession.h"
#include "wm_bridge_action_registry.h"
#include "wm_bridge_action_support.h"
#include "wm_bridge_common.h"
#include "wm_bridge_json.h"
#include "wm_bridge_random_enchant.h"
#include "wm_effect_registry.h"

#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <initializer_list>
#include <limits>
#include <list>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace
{
    using WmBridge::EscapeForJson;
    using namespace WmBridge::detail;

    // Phase 0D: forward declarations so intra-file order is irrelevant.
    bool IsRandomEnchantEligibleItem(Item const* item);
    bool TryResolveEquipmentSlot(std::string rawSlot, uint8& slot);
    std::string NormalizeToken(std::string value);
    Item* SelectRandomEligibleEquippedItem(Player* player);
    Item* ResolveRandomEnchantTargetItem(Player* player, std::string const& payloadJson, std::string& errorText);

    std::string NormalizeToken(std::string value)
    {
        std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
            if (ch == '-' || ch == ' ')
            {
                return '_';
            }
            return static_cast<char>(std::tolower(ch));
        });
        return value;
    }

    bool ExecutePlayerAddItem(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 itemId = 0;
        uint32 count = 1;
        if (!TryExtractAnyUInt32Field(payloadJson, {"item_id", "itemId", "entry"}, itemId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_item_id"), "missing_item_id");
            return true;
        }
        TryExtractAnyUInt32Field(payloadJson, {"count", "quantity"}, count);
        count = std::clamp<uint32>(count, 1, 200);
        if (!sObjectMgr->GetItemTemplate(itemId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_item", {}, {{"item_id", itemId}}), "invalid_item");
            return true;
        }

        uint32 noSpaceForCount = 0;
        ItemPosCountVec destination;
        InventoryResult inventoryResult = player->CanStoreNewItem(NULL_BAG, NULL_SLOT, destination, itemId, count, &noSpaceForCount);
        if (inventoryResult != EQUIP_ERR_OK)
        {
            count -= noSpaceForCount;
        }
        if (count == 0 || destination.empty())
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "inventory_full", {}, {{"item_id", itemId}, {"player_guid", playerGuid}}), "inventory_full");
            return true;
        }

        Item* item = player->StoreNewItem(destination, itemId, true);
        if (!item)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "item_not_created", {}, {{"item_id", itemId}, {"count", count}}), "item_not_created");
            return true;
        }

        bool soulbound = false;
        if (TryExtractAnyBoolField(payloadJson, {"soulbound", "bind", "bind_on_grant", "bindOnGrant"}, soulbound) && soulbound)
        {
            item->SetBinding(true);
            item->SetState(ITEM_CHANGED, player);
        }
        player->SendNewItem(item, count, true, false);

        CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
        player->SaveInventoryAndGoldToDB(trans);
        CharacterDatabase.CommitTransaction(trans);
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "item_added", {}, {{"item_id", itemId}, {"count", count}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecutePlayerRemoveItem(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 itemId = 0;
        uint32 count = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"item_id", "itemId", "entry"}, itemId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_item_id"), "missing_item_id");
            return true;
        }
        if (!TryExtractAnyUInt32Field(payloadJson, {"count", "quantity"}, count) || count == 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_positive_count"), "missing_positive_count");
            return true;
        }
        count = std::clamp<uint32>(count, 1, 200);
        if (!sObjectMgr->GetItemTemplate(itemId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_item", {}, {{"item_id", itemId}}), "invalid_item");
            return true;
        }

        bool adminOverride = false;
        TryExtractAnyBoolField(payloadJson, {"admin_override", "adminOverride"}, adminOverride);
        if (!adminOverride)
        {
            QueryResult reservedItem = WorldDatabase.Query(
                "SELECT ReservedID FROM wm_reserved_slot WHERE EntityType = 'item' AND ReservedID = {} LIMIT 1",
                itemId);
            if (!reservedItem)
            {
                CompleteAction(
                    requestId,
                    "rejected",
                    actionKind,
                    ActionResultJson("rejected", actionKind, "non_managed_item_remove_denied", {}, {{"item_id", itemId}, {"player_guid", playerGuid}}),
                    "non_managed_item_remove_denied");
                return true;
            }
        }

        uint32 itemCount = player->GetItemCount(itemId, false);
        if (itemCount < count)
        {
            CompleteAction(
                requestId,
                "failed",
                actionKind,
                ActionResultJson("failed", actionKind, "insufficient_item_count", {}, {{"item_id", itemId}, {"requested_count", count}, {"available_count", itemCount}, {"player_guid", playerGuid}}),
                "insufficient_item_count");
            return true;
        }

        player->DestroyItemCount(itemId, count, true, true);
        CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
        player->SaveInventoryAndGoldToDB(trans);
        CharacterDatabase.CommitTransaction(trans);
        uint32 remainingCount = player->GetItemCount(itemId, false);
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson("done", actionKind, "item_removed", {}, {{"item_id", itemId}, {"count", count}, {"remaining_count", remainingCount}, {"player_guid", playerGuid}}));
        return true;
    }

    bool IsRandomEnchantEligibleItem(Item const* item)
    {
        return WmBridge::RandomEnchant::IsEligibleItem(item);
    }

    bool TryResolveEquipmentSlot(std::string rawSlot, uint8& slot)
    {
        std::string normalized = NormalizeToken(rawSlot);
        if (normalized == "head")
            slot = EQUIPMENT_SLOT_HEAD;
        else if (normalized == "neck")
            slot = EQUIPMENT_SLOT_NECK;
        else if (normalized == "shoulder" || normalized == "shoulders")
            slot = EQUIPMENT_SLOT_SHOULDERS;
        else if (normalized == "body" || normalized == "shirt")
            slot = EQUIPMENT_SLOT_BODY;
        else if (normalized == "chest")
            slot = EQUIPMENT_SLOT_CHEST;
        else if (normalized == "waist" || normalized == "belt")
            slot = EQUIPMENT_SLOT_WAIST;
        else if (normalized == "legs")
            slot = EQUIPMENT_SLOT_LEGS;
        else if (normalized == "feet" || normalized == "boots")
            slot = EQUIPMENT_SLOT_FEET;
        else if (normalized == "wrist" || normalized == "wrists" || normalized == "bracers")
            slot = EQUIPMENT_SLOT_WRISTS;
        else if (normalized == "hands" || normalized == "gloves")
            slot = EQUIPMENT_SLOT_HANDS;
        else if (normalized == "finger1" || normalized == "ring1")
            slot = EQUIPMENT_SLOT_FINGER1;
        else if (normalized == "finger2" || normalized == "ring2")
            slot = EQUIPMENT_SLOT_FINGER2;
        else if (normalized == "trinket1")
            slot = EQUIPMENT_SLOT_TRINKET1;
        else if (normalized == "trinket2")
            slot = EQUIPMENT_SLOT_TRINKET2;
        else if (normalized == "back" || normalized == "cloak")
            slot = EQUIPMENT_SLOT_BACK;
        else if (normalized == "mainhand" || normalized == "main_hand")
            slot = EQUIPMENT_SLOT_MAINHAND;
        else if (normalized == "offhand" || normalized == "off_hand")
            slot = EQUIPMENT_SLOT_OFFHAND;
        else if (normalized == "ranged")
            slot = EQUIPMENT_SLOT_RANGED;
        else if (normalized == "tabard")
            slot = EQUIPMENT_SLOT_TABARD;
        else
            return false;

        return true;
    }

    bool ExecutePlayerRandomEnchantItem(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        std::string targetError;
        Item* item = ResolveRandomEnchantTargetItem(player, payloadJson, targetError);
        if (!item)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, targetError, {}, {{"player_guid", playerGuid}}), targetError);
            return true;
        }
        if (!IsRandomEnchantEligibleItem(item))
        {
            CompleteAction(
                requestId,
                "rejected",
                actionKind,
                ActionResultJson(
                    "rejected",
                    actionKind,
                    "item_not_random_enchant_eligible",
                    {},
                    {{"item_id", item->GetEntry()}, {"item_guid_low", static_cast<long long>(item->GetGUID().GetCounter())}, {"player_guid", playerGuid}}),
                "item_not_random_enchant_eligible");
            return true;
        }

        WmBridge::RandomEnchant::ApplyOptions options = WmBridge::RandomEnchant::DefaultApplyOptionsFromConfig();
        TryExtractAnyUInt32Field(payloadJson, {"max_enchants", "maxEnchants"}, options.maxEnchants);
        TryExtractAnyBoolField(payloadJson, {"guarantee_first", "guaranteeFirst"}, options.guaranteeFirst);
        TryExtractAnyFloatField(
            payloadJson,
            {"preserve_existing_chance_pct", "preserveExistingChancePct", "do_not_erase_old_chance_pct", "doNotEraseOldChancePct"},
            options.preserveExistingChancePct);
        TryExtractAnyUInt32Field(payloadJson, {"minimum_tier", "minimumTier", "min_tier", "minTier"}, options.minimumTier);
        TryExtractAnyUInt32Field(payloadJson, {"forced_tier", "forcedTier", "tier"}, options.forcedTier);
        TryExtractAnyUInt32Field(payloadJson, {"bonus_tier", "bonusTier"}, options.bonusTier);
        TryExtractAnyFloatField(payloadJson, {"bonus_tier_chance_pct", "bonusTierChancePct"}, options.bonusTierChancePct);
        uint32 selectedEnchantSlotIndex = 0;
        if (TryExtractAnyUInt32Field(payloadJson, {"selected_enchant_slot_index", "selectedEnchantSlotIndex", "enchant_slot_index", "enchantSlotIndex"}, selectedEnchantSlotIndex))
        {
            options.selectedEnchantSlotIndex = static_cast<int32>(selectedEnchantSlotIndex);
        }
        TryExtractAnyFloatField(payloadJson, {"enchant_chance_1", "enchantChance1"}, options.enchantChance1);
        TryExtractAnyFloatField(payloadJson, {"enchant_chance_2", "enchantChance2"}, options.enchantChance2);
        TryExtractAnyFloatField(payloadJson, {"enchant_chance_3", "enchantChance3"}, options.enchantChance3);

        WmBridge::RandomEnchant::ApplyResult applyResult = WmBridge::RandomEnchant::ApplyToItem(player, item, options);
        if (!applyResult.ok)
        {
            CompleteAction(
                requestId,
                "rejected",
                actionKind,
                ActionResultJson("rejected", actionKind, applyResult.message, {}, {{"player_guid", playerGuid}}),
                applyResult.message);
            return true;
        }

        CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
        player->SaveInventoryAndGoldToDB(trans);
        CharacterDatabase.CommitTransaction(trans);

        std::ostringstream playerMessage;
        playerMessage << "WM random enchant applied to " << item->GetTemplate()->Name1 << ": "
                      << applyResult.appliedCount << " new, " << applyResult.preservedCount << " preserved.";
        player->GetSession()->SendAreaTriggerMessage(playerMessage.str());

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                applyResult.message,
                {},
                {
                    {"player_guid", playerGuid},
                    {"item_id", item->GetEntry()},
                    {"item_guid_low", static_cast<long long>(item->GetGUID().GetCounter())},
                    {"applied_count", applyResult.appliedCount},
                    {"replaced_count", applyResult.replacedCount},
                    {"preserved_count", applyResult.preservedCount},
                    {"first_enchant_id", applyResult.firstEnchantId},
                    {"last_enchant_id", applyResult.lastEnchantId},
                    {"minimum_tier", options.minimumTier},
                    {"forced_tier", options.forcedTier},
                    {"bonus_tier", options.bonusTier},
                    {"selected_enchant_slot_index", options.selectedEnchantSlotIndex},
                },
                {
                    {"preserve_existing_chance_pct", std::clamp<float>(options.preserveExistingChancePct, 0.0f, 100.0f)},
                    {"bonus_tier_chance_pct", std::clamp<float>(options.bonusTierChancePct, 0.0f, 100.0f)},
                }));
        return true;
    }

    Item* SelectRandomEligibleEquippedItem(Player* player)
    {
        if (!player)
        {
            return nullptr;
        }

        std::vector<uint8> slots;
        for (uint8 slot = EQUIPMENT_SLOT_START; slot < EQUIPMENT_SLOT_END; ++slot)
        {
            if (Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
            {
                if (IsRandomEnchantEligibleItem(item))
                {
                    slots.push_back(slot);
                }
            }
        }

        if (slots.empty())
        {
            return nullptr;
        }

        return player->GetItemByPos(INVENTORY_SLOT_BAG_0, slots[urand(0, static_cast<uint32>(slots.size() - 1))]);
    }

    Item* ResolveRandomEnchantTargetItem(Player* player, std::string const& payloadJson, std::string& errorText)
    {
        if (!player)
        {
            errorText = "player_not_online";
            return nullptr;
        }

        uint32 itemGuidLow = 0;
        if (TryExtractAnyUInt32Field(payloadJson, {"item_guid_low", "itemGuidLow", "item_guid", "itemGuid"}, itemGuidLow) && itemGuidLow > 0)
        {
            Item* item = player->GetItemByGuid(ObjectGuid::Create<HighGuid::Item>(itemGuidLow));
            if (!item)
            {
                errorText = "item_not_owned_or_loaded";
                return nullptr;
            }
            return item;
        }

        uint32 numericSlot = 0;
        if (TryExtractAnyUInt32Field(payloadJson, {"equipment_slot", "equipmentSlot", "slot"}, numericSlot))
        {
            if (numericSlot >= EQUIPMENT_SLOT_END)
            {
                errorText = "invalid_equipment_slot";
                return nullptr;
            }

            Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, static_cast<uint8>(numericSlot));
            if (!item)
            {
                errorText = "empty_equipment_slot";
                return nullptr;
            }
            return item;
        }

        std::string selector = ExtractJsonStringField(payloadJson, "selector");
        if (selector.empty())
            selector = ExtractJsonStringField(payloadJson, "target");
        if (selector.empty())
            selector = ExtractJsonStringField(payloadJson, "equipment_slot");
        if (selector.empty())
            selector = ExtractJsonStringField(payloadJson, "equipmentSlot");
        if (selector.empty())
            selector = ExtractJsonStringField(payloadJson, "slot");

        if (!selector.empty())
        {
            std::string normalized = NormalizeToken(selector);
            if (normalized == "random" || normalized == "random_equipped" || normalized == "equipped_random")
            {
                Item* item = SelectRandomEligibleEquippedItem(player);
                if (!item)
                {
                    errorText = "no_eligible_equipped_item";
                    return nullptr;
                }
                return item;
            }

            uint8 equipmentSlot = 0;
            if (!TryResolveEquipmentSlot(selector, equipmentSlot))
            {
                errorText = "invalid_equipment_slot";
                return nullptr;
            }

            Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, equipmentSlot);
            if (!item)
            {
                errorText = "empty_equipment_slot";
                return nullptr;
            }
            return item;
        }

        errorText = "missing_item_target";
        return nullptr;
    }

}

namespace WmBridge
{
    void RegisterWmBridgeInventoryActions(ActionRegistry& registry)
    {
        registry.Register("player_add_item", &ExecutePlayerAddItem);
        registry.Register("player_remove_item", &ExecutePlayerRemoveItem);
        registry.Register("player_random_enchant_item", &ExecutePlayerRandomEnchantItem);
    }
}
