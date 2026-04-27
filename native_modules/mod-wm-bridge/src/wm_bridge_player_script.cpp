#include "CellImpl.h"
#include "ScriptMgr.h"
#include "Creature.h"
#include "GameObject.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "LootMgr.h"
#include "Map.h"
#include "Opcodes.h"
#include "Player.h"
#include "QuestDef.h"
#include "Spell.h"
#include "WorldPacket.h"
#include "wm_bridge_common.h"

#include <algorithm>
#include <list>
#include <unordered_set>

namespace
{
    std::unordered_set<uint32> gAoeLootPlayersInProgress;

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

    void NotifyAoeLootMoney(Player* player, uint32 amount)
    {
        if (!player || amount == 0)
            return;

        WorldPacket data(SMSG_LOOT_MONEY_NOTIFY, 4 + 1);
        data << uint32(amount);
        data << uint8(1);
        player->SendDirectMessage(&data);
    }

    bool CanAoeLootCreature(Player* player, Creature* creature, ObjectGuid const& currentLootGuid)
    {
        if (!player || !creature || creature->GetGUID() == currentLootGuid || creature->IsAlive())
            return false;

        if (creature->loot.loot_type != LOOT_CORPSE || creature->loot.isLooted())
            return false;

        if (!creature->HasDynamicFlag(UNIT_DYNFLAG_LOOTABLE) || !creature->isTappedBy(player))
            return false;

        return creature->IsWithinDistInMap(player, std::max(1.0f, WmBridge::GetConfig().aoeLootRadius));
    }

    bool AutoLootCreatureCorpse(Player* player, Creature* creature, ObjectGuid const& currentLootGuid)
    {
        if (!CanAoeLootCreature(player, creature, currentLootGuid))
            return true;

        Loot& loot = creature->loot;
        if (loot.gold > 0)
        {
            uint32 gold = loot.gold;
            loot.NotifyMoneyRemoved();
            player->ModifyMoney(gold);
            player->UpdateAchievementCriteria(ACHIEVEMENT_CRITERIA_TYPE_LOOT_MONEY, gold);
            NotifyAoeLootMoney(player, gold);
            sScriptMgr->OnLootMoney(player, gold);
            loot.gold = 0;
        }

        ObjectGuid previousLootGuid = player->GetLootGUID();
        player->SetLootGUID(creature->GetGUID());

        bool keepScanning = true;
        uint32 maxSlot = loot.GetMaxSlotInLootFor(player);
        for (uint32 slot = 0; slot < maxSlot; ++slot)
        {
            InventoryResult result = EQUIP_ERR_OK;
            player->StoreLootItem(static_cast<uint8>(slot), &loot, result);
            if (result != EQUIP_ERR_OK)
            {
                keepScanning = false;
                break;
            }
        }

        player->SetLootGUID(previousLootGuid);

        if (loot.isLooted())
        {
            creature->AllLootRemovedFromCorpse();
            creature->RemoveDynamicFlag(UNIT_DYNFLAG_LOOTABLE);
            loot.clear();
        }
        else
        {
            creature->ForceValuesUpdateAtIndex(UNIT_DYNAMIC_FLAGS);
        }

        return keepScanning;
    }

    void TryAoeLootNearbyCorpses(Player* player)
    {
        WmBridge::BridgeConfig const& config = WmBridge::GetConfig();
        if (!config.aoeLootEnabled || !WmBridge::IsPlayerAllowed(player))
            return;

        ObjectGuid currentLootGuid = player->GetLootGUID();
        if (!currentLootGuid || !currentLootGuid.IsCreatureOrVehicle())
            return;

        uint32 playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        if (gAoeLootPlayersInProgress.find(playerGuid) != gAoeLootPlayersInProgress.end())
            return;

        gAoeLootPlayersInProgress.insert(playerGuid);

        std::list<Unit*> nearbyUnits;
        float radius = std::max(1.0f, config.aoeLootRadius);
        Acore::AllDeadCreaturesInRange check(player, radius);
        Acore::UnitListSearcher<Acore::AllDeadCreaturesInRange> searcher(player, nearbyUnits, check);
        Cell::VisitObjects(player, searcher, radius);

        uint32 lootedCorpses = 0;
        uint32 maxCorpses = std::max<uint32>(1u, config.aoeLootMaxCorpses);
        for (Unit* unit : nearbyUnits)
        {
            Creature* creature = unit ? unit->ToCreature() : nullptr;
            if (!creature || !CanAoeLootCreature(player, creature, currentLootGuid))
                continue;

            if (!AutoLootCreatureCorpse(player, creature, currentLootGuid))
                break;

            ++lootedCorpses;
            if (lootedCorpses >= maxCorpses)
                break;
        }

        gAoeLootPlayersInProgress.erase(playerGuid);
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

    void OnPlayerAfterCreatureLoot(Player* player) override
    {
        TryAoeLootNearbyCorpses(player);
    }

    void OnPlayerAfterCreatureLootMoney(Player* player) override
    {
        TryAoeLootNearbyCorpses(player);
    }
};

void AddSC_mod_wm_bridge_player_script()
{
    new wm_bridge_player_script();
}
