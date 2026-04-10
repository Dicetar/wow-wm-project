#include "AllCreatureScript.h"
#include "AllGameObjectScript.h"
#include "AllItemScript.h"
#include "Creature.h"
#include "GameObject.h"
#include "Item.h"
#include "Player.h"
#include "QuestDef.h"
#include "wm_bridge_common.h"

namespace
{
    void EmitQuestLifecycle(
        Player* player,
        char const* eventType,
        Quest const* quest,
        std::string const& subjectType,
        std::string const& subjectGuid,
        uint32 subjectEntry,
        std::string const& subjectName)
    {
        if (!WmBridge::IsPlayerAllowed(player) || !quest)
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "quest", eventType);
        row.subjectType = subjectType;
        row.subjectGuid = subjectGuid;
        row.subjectEntry = subjectEntry;
        row.objectType = "quest";
        row.objectEntry = quest->GetQuestId();

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendString(payload, firstField, "subject_name", subjectName);
        WmBridge::JsonAppendString(payload, firstField, "subject_type", subjectType);
        WmBridge::JsonAppendNumber(payload, firstField, "quest_id", static_cast<long long>(quest->GetQuestId()));
        WmBridge::JsonAppendString(payload, firstField, "quest_title", quest->GetTitle());
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }

    void EmitGossipOpened(
        Player* player,
        std::string const& subjectType,
        std::string const& subjectGuid,
        uint32 subjectEntry,
        std::string const& subjectName)
    {
        if (!WmBridge::IsPlayerAllowed(player))
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "gossip", "opened");
        row.subjectType = subjectType;
        row.subjectGuid = subjectGuid;
        row.subjectEntry = subjectEntry;

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendString(payload, firstField, "subject_name", subjectName);
        WmBridge::JsonAppendString(payload, firstField, "subject_type", subjectType);
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }

    void EmitGossipSelected(
        Player* player,
        std::string const& subjectType,
        std::string const& subjectGuid,
        uint32 subjectEntry,
        std::string const& subjectName,
        uint32 sender,
        uint32 action)
    {
        if (!WmBridge::IsPlayerAllowed(player))
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "gossip", "selected");
        row.subjectType = subjectType;
        row.subjectGuid = subjectGuid;
        row.subjectEntry = subjectEntry;

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendString(payload, firstField, "subject_name", subjectName);
        WmBridge::JsonAppendString(payload, firstField, "subject_type", subjectType);
        WmBridge::JsonAppendNumber(payload, firstField, "sender", static_cast<long long>(sender));
        WmBridge::JsonAppendNumber(payload, firstField, "action", static_cast<long long>(action));
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }
}

class wm_bridge_all_creature_script : public AllCreatureScript
{
public:
    wm_bridge_all_creature_script() : AllCreatureScript("wm_bridge_all_creature_script")
    {
    }

    bool CanCreatureGossipHello(Player* player, Creature* creature) override
    {
        if (WmBridge::GetConfig().emitGossip && WmBridge::IsPlayerAllowed(player) && creature)
        {
            EmitGossipOpened(player, "creature", creature->GetGUID().ToString(), creature->GetEntry(), creature->GetName());
        }

        return false;
    }

    bool CanCreatureGossipSelect(Player* player, Creature* creature, uint32 sender, uint32 action) override
    {
        if (WmBridge::GetConfig().emitGossip && WmBridge::IsPlayerAllowed(player) && creature)
        {
            EmitGossipSelected(
                player,
                "creature",
                creature->GetGUID().ToString(),
                creature->GetEntry(),
                creature->GetName(),
                sender,
                action);
        }

        return false;
    }

    bool CanCreatureQuestAccept(Player* player, Creature* creature, Quest const* quest) override
    {
        if (WmBridge::GetConfig().emitQuest && WmBridge::IsPlayerAllowed(player) && creature && quest)
        {
            EmitQuestLifecycle(player, "accepted", quest, "creature", creature->GetGUID().ToString(), creature->GetEntry(), creature->GetName());
            EmitQuestLifecycle(player, "granted", quest, "creature", creature->GetGUID().ToString(), creature->GetEntry(), creature->GetName());
        }

        return false;
    }

    bool CanCreatureQuestReward(Player* player, Creature* creature, Quest const* quest, uint32 /*opt*/) override
    {
        if (WmBridge::GetConfig().emitQuest && WmBridge::IsPlayerAllowed(player) && creature && quest)
        {
            EmitQuestLifecycle(player, "rewarded", quest, "creature", creature->GetGUID().ToString(), creature->GetEntry(), creature->GetName());
        }

        return false;
    }
};

class wm_bridge_all_gameobject_script : public AllGameObjectScript
{
public:
    wm_bridge_all_gameobject_script() : AllGameObjectScript("wm_bridge_all_gameobject_script")
    {
    }

    bool CanGameObjectGossipHello(Player* player, GameObject* gameObject) override
    {
        if (WmBridge::GetConfig().emitGossip && WmBridge::IsPlayerAllowed(player) && gameObject)
        {
            EmitGossipOpened(
                player,
                "gameobject",
                gameObject->GetGUID().ToString(),
                gameObject->GetEntry(),
                gameObject->GetName());
        }

        return false;
    }

    bool CanGameObjectGossipSelect(Player* player, GameObject* gameObject, uint32 sender, uint32 action) override
    {
        if (WmBridge::GetConfig().emitGossip && WmBridge::IsPlayerAllowed(player) && gameObject)
        {
            EmitGossipSelected(
                player,
                "gameobject",
                gameObject->GetGUID().ToString(),
                gameObject->GetEntry(),
                gameObject->GetName(),
                sender,
                action);
        }

        return false;
    }

    bool CanGameObjectQuestAccept(Player* player, GameObject* gameObject, Quest const* quest) override
    {
        if (WmBridge::GetConfig().emitQuest && WmBridge::IsPlayerAllowed(player) && gameObject && quest)
        {
            EmitQuestLifecycle(
                player,
                "accepted",
                quest,
                "gameobject",
                gameObject->GetGUID().ToString(),
                gameObject->GetEntry(),
                gameObject->GetName());
            EmitQuestLifecycle(
                player,
                "granted",
                quest,
                "gameobject",
                gameObject->GetGUID().ToString(),
                gameObject->GetEntry(),
                gameObject->GetName());
        }

        return false;
    }

    bool CanGameObjectQuestReward(Player* player, GameObject* gameObject, Quest const* quest, uint32 /*opt*/) override
    {
        if (WmBridge::GetConfig().emitQuest && WmBridge::IsPlayerAllowed(player) && gameObject && quest)
        {
            EmitQuestLifecycle(
                player,
                "rewarded",
                quest,
                "gameobject",
                gameObject->GetGUID().ToString(),
                gameObject->GetEntry(),
                gameObject->GetName());
        }

        return false;
    }
};

class wm_bridge_all_item_script : public AllItemScript
{
public:
    wm_bridge_all_item_script() : AllItemScript("wm_bridge_all_item_script")
    {
    }

    bool CanItemQuestAccept(Player* player, Item* item, Quest const* quest) override
    {
        if (WmBridge::GetConfig().emitQuest && WmBridge::IsPlayerAllowed(player) && item && quest)
        {
            EmitQuestLifecycle(
                player,
                "accepted",
                quest,
                "item",
                item->GetGUID().ToString(),
                item->GetEntry(),
                item->GetTemplate() ? item->GetTemplate()->Name1 : "");
            EmitQuestLifecycle(
                player,
                "granted",
                quest,
                "item",
                item->GetGUID().ToString(),
                item->GetEntry(),
                item->GetTemplate() ? item->GetTemplate()->Name1 : "");
        }

        return true;
    }
};

void AddSC_mod_wm_bridge_interaction_scripts()
{
    new wm_bridge_all_creature_script();
    new wm_bridge_all_gameobject_script();
    new wm_bridge_all_item_script();
}
