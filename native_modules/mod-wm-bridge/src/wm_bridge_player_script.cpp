#include "ScriptMgr.h"
#include "Creature.h"
#include "GameObject.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Map.h"
#include "Player.h"
#include "QuestDef.h"
#include "Spell.h"
#include "wm_bridge_common.h"

namespace
{
    std::string GetItemName(Item const* item)
    {
        if (!item || !item->GetTemplate())
        {
            return "";
        }

        return item->GetTemplate()->Name1;
    }

    void EmitKill(Player* player, Creature* killed, char const* killSource)
    {
        if (!WmBridge::IsPlayerAllowed(player) || !killed)
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "combat", "kill");
        row.subjectType = "creature";
        row.subjectGuid = killed->GetGUID().ToString();
        row.subjectEntry = killed->GetEntry();

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendString(payload, firstField, "subject_name", killed->GetName());
        WmBridge::JsonAppendString(payload, firstField, "kill_source", killSource);
        WmBridge::JsonAppendNumber(payload, firstField, "player_guid", static_cast<long long>(player->GetGUID().GetCounter()));
        WmBridge::JsonAppendNumber(payload, firstField, "subject_entry", static_cast<long long>(killed->GetEntry()));
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }

    void PopulateLootSource(Player* player, ObjectGuid const& lootGuid, WmBridge::EventRow& row, std::string& payload, bool& firstField)
    {
        if (!player || lootGuid.IsEmpty())
        {
            return;
        }

        row.subjectGuid = lootGuid.ToString();

        if (lootGuid.IsCreature())
        {
            row.subjectType = "creature";
            row.subjectEntry = lootGuid.GetEntry();
            WmBridge::JsonAppendString(payload, firstField, "loot_source_type", "creature");
            if (Creature* creature = player->GetMap() ? player->GetMap()->GetCreature(lootGuid) : nullptr)
            {
                WmBridge::JsonAppendString(payload, firstField, "loot_source_name", creature->GetName());
            }
            return;
        }

        if (lootGuid.IsGameObject())
        {
            row.subjectType = "gameobject";
            row.subjectEntry = lootGuid.GetEntry();
            WmBridge::JsonAppendString(payload, firstField, "loot_source_type", "gameobject");
            if (GameObject* gameObject = player->GetMap() ? player->GetMap()->GetGameObject(lootGuid) : nullptr)
            {
                WmBridge::JsonAppendString(payload, firstField, "loot_source_name", gameObject->GetName());
            }
        }
    }
}

class wm_bridge_player_script : public PlayerScript
{
public:
    wm_bridge_player_script() : PlayerScript("wm_bridge_player_script")
    {
    }

    void OnPlayerCreatureKill(Player* killer, Creature* killed) override
    {
        if (!WmBridge::GetConfig().emitKill)
        {
            return;
        }

        EmitKill(killer, killed, "player");
    }

    void OnPlayerCreatureKilledByPet(Player* petOwner, Creature* killed) override
    {
        if (!WmBridge::GetConfig().emitKill)
        {
            return;
        }

        EmitKill(petOwner, killed, "pet");
    }

    void OnPlayerCompleteQuest(Player* player, Quest const* quest) override
    {
        if (!WmBridge::GetConfig().emitQuest || !WmBridge::IsPlayerAllowed(player) || !quest)
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "quest", "completed");
        row.objectType = "quest";
        row.objectEntry = quest->GetQuestId();

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendNumber(payload, firstField, "quest_id", static_cast<long long>(quest->GetQuestId()));
        WmBridge::JsonAppendString(payload, firstField, "quest_title", quest->GetTitle());
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }

    void OnPlayerUpdateArea(Player* player, uint32 oldArea, uint32 newArea) override
    {
        if (!WmBridge::GetConfig().emitArea || !WmBridge::IsPlayerAllowed(player))
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "area", "entered");
        row.areaId = newArea;
        row.subjectType = "area";
        row.subjectEntry = newArea;

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendNumber(payload, firstField, "old_area_id", static_cast<long long>(oldArea));
        WmBridge::JsonAppendNumber(payload, firstField, "new_area_id", static_cast<long long>(newArea));
        WmBridge::JsonAppendString(payload, firstField, "area_name", WmBridge::LookupAreaName(newArea));
        WmBridge::JsonAppendString(payload, firstField, "zone_name", WmBridge::LookupAreaName(player->GetZoneId()));
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }

    void OnPlayerLootItem(Player* player, Item* item, uint32 count, ObjectGuid lootGuid) override
    {
        if (!WmBridge::GetConfig().emitLoot || !WmBridge::IsPlayerAllowed(player) || !item)
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "loot", "item");
        row.objectType = "item";
        row.objectEntry = item->GetEntry();

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendNumber(payload, firstField, "item_entry", static_cast<long long>(item->GetEntry()));
        WmBridge::JsonAppendString(payload, firstField, "item_name", GetItemName(item));
        WmBridge::JsonAppendNumber(payload, firstField, "count", static_cast<long long>(count));
        PopulateLootSource(player, lootGuid, row, payload, firstField);
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }
};

void AddSC_mod_wm_bridge_player_script()
{
    new wm_bridge_player_script();
}
