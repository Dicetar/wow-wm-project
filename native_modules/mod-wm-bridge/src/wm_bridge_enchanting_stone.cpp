#include "wm_bridge_random_enchant.h"

#include "Bag.h"
#include "Chat.h"
#include "DatabaseEnv.h"
#include "Item.h"
#include "ItemScript.h"
#include "Player.h"
#include "Random.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "WorldPacket.h"
#include "WorldSession.h"
#include "wm_bridge_common.h"

#include <algorithm>
#include <cstdlib>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>

namespace
{
    constexpr uint32 WM_ENCHANTING_STONE_ITEM_ENTRY = 910015;
    constexpr uint8 WM_ENCHANTING_STONE_MAX_LEVEL = 8;
    constexpr char const* WM_ADDON_PREFIX = "WMBRIDGE";
    constexpr char const* WM_ADDON_MARKER = "WMB1";

    enum class TargetLocation
    {
        None,
        Bag,
        Equipment,
    };

    struct AddonCommand
    {
        std::string type;
        TargetLocation location = TargetLocation::None;
        uint32 bag = 0;
        uint32 slot = 0;
    };

    std::unordered_map<uint32, uint8> gUpgradeLevelByItemGuid;

    uint32 ItemLowGuid(Item const* item)
    {
        return item ? static_cast<uint32>(item->GetGUID().GetCounter()) : 0;
    }

    void SendPlayerMessage(Player* player, std::string const& message)
    {
        if (player && player->GetSession())
        {
            player->GetSession()->SendAreaTriggerMessage(message);
        }
    }

    std::string SanitizeAddonValue(std::string value)
    {
        std::replace(value.begin(), value.end(), '|', '/');
        std::replace(value.begin(), value.end(), '\r', ' ');
        std::replace(value.begin(), value.end(), '\n', ' ');
        return value;
    }

    void SendStoneAddonPayload(Player* player, std::string const& payload)
    {
        if (!player || !player->GetSession())
        {
            return;
        }

        std::string addonMessage = std::string(WM_ADDON_PREFIX) + "\t" + payload;
        WorldPacket data;
        ChatHandler::BuildChatPacket(data, CHAT_MSG_WHISPER, LANG_ADDON, player, player, addonMessage);
        player->GetSession()->SendPacket(&data);
    }

    void SendStoneOpen(Player* player)
    {
        std::ostringstream payload;
        payload << WM_ADDON_MARKER
                << "|type=STONE_OPEN"
                << "|entry=" << WM_ENCHANTING_STONE_ITEM_ENTRY
                << "|max=" << static_cast<uint32>(WM_ENCHANTING_STONE_MAX_LEVEL);
        SendStoneAddonPayload(player, payload.str());
    }

    void SendStoneResult(Player* player, bool ok, std::string const& message)
    {
        std::ostringstream payload;
        payload << WM_ADDON_MARKER
                << "|type=STONE_RESULT"
                << "|ok=" << (ok ? "1" : "0")
                << "|message=" << SanitizeAddonValue(message);
        SendStoneAddonPayload(player, payload.str());
        SendPlayerMessage(player, message);
    }

    void EnsureUpgradeTable()
    {
        static bool initialized = false;
        if (initialized)
        {
            return;
        }

        CharacterDatabase.Execute(
            "CREATE TABLE IF NOT EXISTS `wm_item_stat_upgrade` ("
            "`ItemGuid` INT UNSIGNED NOT NULL,"
            "`UpgradeLevel` TINYINT UNSIGNED NOT NULL DEFAULT 0,"
            "`UpdatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
            "PRIMARY KEY (`ItemGuid`)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
        initialized = true;
    }

    uint8 ClampUpgradeLevel(uint32 level)
    {
        return static_cast<uint8>(std::min<uint32>(level, WM_ENCHANTING_STONE_MAX_LEVEL));
    }

    uint8 GetUpgradeLevelByGuid(uint32 itemGuidLow)
    {
        if (!itemGuidLow)
        {
            return 0;
        }

        auto cached = gUpgradeLevelByItemGuid.find(itemGuidLow);
        if (cached != gUpgradeLevelByItemGuid.end())
        {
            return cached->second;
        }

        EnsureUpgradeTable();
        uint8 level = 0;
        if (QueryResult result = CharacterDatabase.Query(
            "SELECT `UpgradeLevel` FROM `wm_item_stat_upgrade` WHERE `ItemGuid` = {}",
            itemGuidLow))
        {
            level = ClampUpgradeLevel(result->Fetch()[0].Get<uint32>());
        }

        gUpgradeLevelByItemGuid[itemGuidLow] = level;
        return level;
    }

    uint8 GetUpgradeLevel(Item const* item)
    {
        return GetUpgradeLevelByGuid(ItemLowGuid(item));
    }

    void SaveUpgradeLevel(Item const* item, uint8 level)
    {
        uint32 const itemGuidLow = ItemLowGuid(item);
        if (!itemGuidLow)
        {
            return;
        }

        level = ClampUpgradeLevel(level);
        EnsureUpgradeTable();
        CharacterDatabase.Execute(
            "INSERT INTO `wm_item_stat_upgrade` (`ItemGuid`, `UpgradeLevel`) VALUES ({}, {}) "
            "ON DUPLICATE KEY UPDATE `UpgradeLevel` = VALUES(`UpgradeLevel`), `UpdatedAt` = CURRENT_TIMESTAMP",
            itemGuidLow,
            static_cast<uint32>(level));
        gUpgradeLevelByItemGuid[itemGuidLow] = level;
    }

    uint32 UpgradeMultiplier(uint8 level)
    {
        level = ClampUpgradeLevel(level);
        return level == 0 ? 1u : (1u << level);
    }

    int32 ScaleIntValue(int32 value, uint8 level)
    {
        if (level == 0 || value == 0)
        {
            return value;
        }

        int64 scaled = static_cast<int64>(value) * static_cast<int64>(UpgradeMultiplier(level));
        scaled = std::clamp<int64>(
            scaled,
            static_cast<int64>(std::numeric_limits<int32>::min()),
            static_cast<int64>(std::numeric_limits<int32>::max()));
        return static_cast<int32>(scaled);
    }

    float ScaleFloatValue(float value, uint8 level)
    {
        return level == 0 ? value : value * static_cast<float>(UpgradeMultiplier(level));
    }

    float SuccessChanceForNextLevel(uint8 nextLevel)
    {
        if (nextLevel <= 2)
        {
            return 100.0f;
        }

        switch (nextLevel)
        {
            case 3:
                return 65.0f;
            case 4:
                return 25.0f;
            case 5:
                return 8.0f;
            case 6:
                return 2.0f;
            case 7:
                return 1.0f;
            default:
                return 0.25f;
        }
    }

    uint8 UpgradeLevelForEquippedSlot(Player* player, uint8 slot)
    {
        if (!player || slot >= EQUIPMENT_SLOT_END)
        {
            return 0;
        }

        return GetUpgradeLevel(player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot));
    }

    bool IsEquippedItem(Player* player, Item const* item)
    {
        return player
            && item
            && item->GetBagSlot() == INVENTORY_SLOT_BAG_0
            && item->GetSlot() < EQUIPMENT_SLOT_END
            && player->GetItemByPos(INVENTORY_SLOT_BAG_0, item->GetSlot()) == item;
    }

    bool IsEligibleTarget(Item const* item)
    {
        return item
            && item->GetEntry() != WM_ENCHANTING_STONE_ITEM_ENTRY
            && WmBridge::RandomEnchant::IsEligibleItem(item);
    }

    uint32 ReadUIntField(std::string const& value)
    {
        if (value.empty())
        {
            return 0;
        }

        char* end = nullptr;
        unsigned long parsed = std::strtoul(value.c_str(), &end, 10);
        if (!end || *end != '\0')
        {
            return 0;
        }

        return static_cast<uint32>(parsed);
    }

    bool ParseStoneAddonCommand(std::string const& rawMessage, AddonCommand& command)
    {
        std::string message = rawMessage;
        std::string const prefixed = std::string(WM_ADDON_PREFIX) + "\t";
        if (message.rfind(prefixed, 0) == 0)
        {
            message = message.substr(prefixed.size());
        }

        std::string const marker = std::string(WM_ADDON_MARKER) + "|";
        if (message.rfind(marker, 0) != 0)
        {
            return false;
        }

        std::size_t start = marker.size();
        while (start <= message.size())
        {
            std::size_t end = message.find('|', start);
            std::string field = message.substr(start, end == std::string::npos ? std::string::npos : end - start);
            std::size_t equals = field.find('=');
            if (equals != std::string::npos)
            {
                std::string key = field.substr(0, equals);
                std::string value = field.substr(equals + 1);
                if (key == "type")
                {
                    command.type = value;
                }
                else if (key == "loc")
                {
                    if (value == "BAG")
                    {
                        command.location = TargetLocation::Bag;
                    }
                    else if (value == "EQUIP")
                    {
                        command.location = TargetLocation::Equipment;
                    }
                }
                else if (key == "bag")
                {
                    command.bag = ReadUIntField(value);
                }
                else if (key == "slot")
                {
                    command.slot = ReadUIntField(value);
                }
            }

            if (end == std::string::npos)
            {
                break;
            }
            start = end + 1;
        }

        return command.type == "STONE_UPGRADE";
    }

    Item* ResolveSelectedItem(Player* player, AddonCommand const& command)
    {
        if (!player)
        {
            return nullptr;
        }

        if (command.location == TargetLocation::Equipment)
        {
            if (command.slot >= EQUIPMENT_SLOT_END)
            {
                return nullptr;
            }
            return player->GetItemByPos(INVENTORY_SLOT_BAG_0, static_cast<uint8>(command.slot));
        }

        if (command.location != TargetLocation::Bag || command.slot == 0)
        {
            return nullptr;
        }

        uint8 const clientSlotIndex = static_cast<uint8>(command.slot - 1);
        if (command.bag == 0)
        {
            uint32 const serverSlot = INVENTORY_SLOT_ITEM_START + clientSlotIndex;
            if (serverSlot >= INVENTORY_SLOT_ITEM_END)
            {
                return nullptr;
            }
            return player->GetItemByPos(INVENTORY_SLOT_BAG_0, static_cast<uint8>(serverSlot));
        }

        if (command.bag > 4)
        {
            return nullptr;
        }

        uint32 const serverBagSlot = INVENTORY_SLOT_BAG_START + command.bag - 1;
        Bag* bag = player->GetBagByPos(static_cast<uint8>(serverBagSlot));
        if (!bag || clientSlotIndex >= bag->GetBagSize())
        {
            return nullptr;
        }

        return bag->GetItemByPos(clientSlotIndex);
    }

    void ConsumeStone(Player* player)
    {
        player->DestroyItemCount(WM_ENCHANTING_STONE_ITEM_ENTRY, 1, true, true);

        CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
        player->SaveInventoryAndGoldToDB(trans);
        CharacterDatabase.CommitTransaction(trans);
    }

    void AttemptUpgrade(Player* player, Item* targetItem)
    {
        if (!player)
        {
            return;
        }

        if (player->GetItemCount(WM_ENCHANTING_STONE_ITEM_ENTRY, false) == 0)
        {
            SendStoneResult(player, false, "You need an Enchanting Stone.");
            return;
        }

        if (!targetItem || !IsEligibleTarget(targetItem) || !targetItem->GetTemplate())
        {
            SendStoneResult(player, false, "That item cannot be upgraded.");
            return;
        }

        uint8 const currentLevel = GetUpgradeLevel(targetItem);
        if (currentLevel >= WM_ENCHANTING_STONE_MAX_LEVEL)
        {
            std::ostringstream message;
            message << targetItem->GetTemplate()->Name1 << " is already at +"
                    << static_cast<uint32>(WM_ENCHANTING_STONE_MAX_LEVEL) << ".";
            SendStoneResult(player, false, message.str());
            return;
        }

        uint8 const nextLevel = currentLevel + 1;
        float const successChance = SuccessChanceForNextLevel(nextLevel);
        bool const success = roll_chance_f(successChance);

        if (success)
        {
            bool const equipped = IsEquippedItem(player, targetItem);
            if (equipped)
            {
                player->_ApplyItemMods(targetItem, targetItem->GetSlot(), false);
            }

            SaveUpgradeLevel(targetItem, nextLevel);

            if (equipped)
            {
                player->_ApplyItemMods(targetItem, targetItem->GetSlot(), true);
            }
        }

        std::string const targetName = targetItem->GetTemplate()->Name1;
        ConsumeStone(player);

        std::ostringstream message;
        if (success)
        {
            message << targetName << " upgraded to +" << static_cast<uint32>(nextLevel)
                    << " (x" << UpgradeMultiplier(nextLevel) << " item stats).";
        }
        else
        {
            message << "Enchanting Stone failed on " << targetName << " (+"
                    << static_cast<uint32>(currentLevel) << " -> +" << static_cast<uint32>(nextLevel)
                    << ", " << std::fixed << std::setprecision(successChance < 1.0f ? 2 : 0)
                    << successChance << "%). The stone was consumed.";
        }
        SendStoneResult(player, success, message.str());
    }
}

class wm_enchanting_stone_item : public ItemScript
{
public:
    wm_enchanting_stone_item() : ItemScript("wm_enchanting_stone") { }

    bool OnUse(Player* player, Item* item, SpellCastTargets const& /*targets*/) override
    {
        if (!player || !item || item->GetEntry() != WM_ENCHANTING_STONE_ITEM_ENTRY)
        {
            return true;
        }

        SendStoneOpen(player);
        return true;
    }
};

class wm_enchanting_stone_player_script : public PlayerScript
{
public:
    wm_enchanting_stone_player_script() : PlayerScript("wm_enchanting_stone_player_script") { }

    void OnPlayerBeforeSendChatMessage(Player* player, uint32& /*type*/, uint32& lang, std::string& msg) override
    {
        if (!player || lang != LANG_ADDON)
        {
            return;
        }

        AddonCommand command;
        if (!ParseStoneAddonCommand(msg, command))
        {
            return;
        }

        AttemptUpgrade(player, ResolveSelectedItem(player, command));
    }

    void OnPlayerApplyItemModsBefore(Player* player, uint8 slot, bool /*apply*/, uint8 /*itemProtoStatNumber*/, uint32 /*statType*/, int32& val) override
    {
        val = ScaleIntValue(val, UpgradeLevelForEquippedSlot(player, slot));
    }

    void OnPlayerApplyItemBonusModsBefore(Player* player, uint8 slot, bool /*apply*/, uint32 /*bonusType*/, int32& val) override
    {
        val = ScaleIntValue(val, UpgradeLevelForEquippedSlot(player, slot));
    }

    void OnPlayerApplyEnchantmentItemModsBefore(Player* /*player*/, Item* item, EnchantmentSlot /*slot*/, bool /*apply*/, uint32 /*enchant_spell_id*/, uint32& enchant_amount) override
    {
        enchant_amount = static_cast<uint32>(std::max<int32>(
            0,
            ScaleIntValue(static_cast<int32>(enchant_amount), GetUpgradeLevel(item))));
    }

    void OnPlayerApplyWeaponDamage(Player* player, uint8 slot, ItemTemplate const* /*proto*/, float& minDamage, float& maxDamage, uint8 /*damageIndex*/) override
    {
        uint8 const level = UpgradeLevelForEquippedSlot(player, slot);
        minDamage = ScaleFloatValue(minDamage, level);
        maxDamage = ScaleFloatValue(maxDamage, level);
    }
};

class wm_enchanting_stone_worldscript : public WorldScript
{
public:
    wm_enchanting_stone_worldscript() : WorldScript("wm_enchanting_stone_worldscript") { }

    void OnStartup() override
    {
        EnsureUpgradeTable();
    }
};

void AddSC_mod_wm_bridge_enchanting_stone()
{
    new wm_enchanting_stone_item();
    new wm_enchanting_stone_player_script();
    new wm_enchanting_stone_worldscript();
}
