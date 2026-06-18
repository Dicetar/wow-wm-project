// Phase 0D: quest-domain native WM action handlers. Bodies moved
// verbatim from wm_bridge_action_queue.cpp; shared infra lives in
// wm_bridge_action_support.h (WmBridge::detail). Registered via
// RegisterWmBridgeQuestActions from the queue bootstrap.

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

    void EmitQuestGrantedEvent(Player* player, Quest const* quest)
    {
        if (!player || !quest || !WmBridge::GetConfig().emitQuest || !WmBridge::IsPlayerAllowed(player))
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "quest", "granted");
        row.objectType = "quest";
        row.objectEntry = quest->GetQuestId();

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendNumber(payload, firstField, "quest_id", static_cast<long long>(quest->GetQuestId()));
        WmBridge::JsonAppendString(payload, firstField, "quest_title", quest->GetTitle());
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendString(payload, firstField, "grant_source", "native_action_queue");
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }

    void EmitQuestRemovedEvent(Player* player, Quest const* quest, uint32 removedSlots, bool removedRewarded)
    {
        if (!player || !quest || !WmBridge::GetConfig().emitQuest || !WmBridge::IsPlayerAllowed(player))
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "quest", "removed");
        row.objectType = "quest";
        row.objectEntry = quest->GetQuestId();

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendNumber(payload, firstField, "quest_id", static_cast<long long>(quest->GetQuestId()));
        WmBridge::JsonAppendString(payload, firstField, "quest_title", quest->GetTitle());
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendNumber(payload, firstField, "removed_slots", static_cast<long long>(removedSlots));
        WmBridge::JsonAppendNumber(payload, firstField, "removed_rewarded", removedRewarded ? 1 : 0);
        WmBridge::JsonAppendString(payload, firstField, "remove_source", "native_action_queue");
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }

    bool ResolveCounterKey(std::string const& payloadJson, std::string& counterKey, std::string& errorText)
    {
        counterKey = ExtractJsonStringField(payloadJson, "counter_key");
        if (counterKey.empty())
        {
            counterKey = ExtractJsonStringField(payloadJson, "counterKey");
        }
        if (counterKey.empty())
        {
            errorText = "missing_counter_key";
            return false;
        }
        if (counterKey.size() > 128)
        {
            errorText = "counter_key_too_long";
            return false;
        }

        return true;
    }

    std::string ExtractArcKey(std::string const& payloadJson)
    {
        std::string arcKey = ExtractJsonStringField(payloadJson, "arc_key");
        if (arcKey.empty())
        {
            arcKey = ExtractJsonStringField(payloadJson, "arcKey");
        }
        if (arcKey.size() > 128)
        {
            arcKey.resize(128);
        }
        return arcKey;
    }

    int32 ReadCounterValue(uint32 playerGuid, std::string const& counterKey)
    {
        QueryResult result = WorldDatabase.Query(
            "SELECT CounterValue FROM wm_bridge_counter WHERE PlayerGUID = {} AND CounterKey = {} LIMIT 1",
            playerGuid,
            SqlString(counterKey));
        return result ? result->Fetch()[0].Get<int32>() : 0;
    }

    bool ExecuteWmCounterSet(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        std::string counterKey;
        std::string errorText;
        if (!ResolveCounterKey(payloadJson, counterKey, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        int32 value = 0;
        if (!TryExtractAnyInt32Field(payloadJson, {"value", "counter_value", "counterValue"}, value))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_counter_value"), "missing_counter_value");
            return true;
        }

        std::string arcKey = ExtractArcKey(payloadJson);
        WorldDatabase.DirectExecute(
            "INSERT INTO wm_bridge_counter (PlayerGUID, CounterKey, CounterValue, ArcKey, MetadataJSON) "
            "VALUES ({}, {}, {}, {}, {}) "
            "ON DUPLICATE KEY UPDATE CounterValue = VALUES(CounterValue), ArcKey = VALUES(ArcKey), MetadataJSON = VALUES(MetadataJSON), UpdatedAt = CURRENT_TIMESTAMP",
            playerGuid,
            SqlString(counterKey),
            value,
            arcKey.empty() ? "NULL" : SqlString(arcKey),
            SqlString(payloadJson));

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson("done", actionKind, "counter_set", {{"counter_key", counterKey}, {"arc_key", arcKey}}, {{"player_guid", playerGuid}, {"value", value}}));
        return true;
    }

    bool ExecuteWmCounterIncrement(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        std::string counterKey;
        std::string errorText;
        if (!ResolveCounterKey(payloadJson, counterKey, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        int32 delta = 1;
        TryExtractAnyInt32Field(payloadJson, {"delta", "value"}, delta);
        if (delta == 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "zero_counter_delta"), "zero_counter_delta");
            return true;
        }

        std::string arcKey = ExtractArcKey(payloadJson);
        WorldDatabase.DirectExecute(
            "INSERT INTO wm_bridge_counter (PlayerGUID, CounterKey, CounterValue, ArcKey, MetadataJSON) "
            "VALUES ({}, {}, {}, {}, {}) "
            "ON DUPLICATE KEY UPDATE CounterValue = CounterValue + VALUES(CounterValue), ArcKey = VALUES(ArcKey), MetadataJSON = VALUES(MetadataJSON), UpdatedAt = CURRENT_TIMESTAMP",
            playerGuid,
            SqlString(counterKey),
            delta,
            arcKey.empty() ? "NULL" : SqlString(arcKey),
            SqlString(payloadJson));

        int32 value = ReadCounterValue(playerGuid, counterKey);
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson("done", actionKind, "counter_incremented", {{"counter_key", counterKey}, {"arc_key", arcKey}}, {{"player_guid", playerGuid}, {"delta", delta}, {"value", value}}));
        return true;
    }

    bool ExecuteWmCounterClear(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        std::string counterKey;
        std::string errorText;
        if (!ResolveCounterKey(payloadJson, counterKey, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        WorldDatabase.DirectExecute(
            "DELETE FROM wm_bridge_counter WHERE PlayerGUID = {} AND CounterKey = {}",
            playerGuid,
            SqlString(counterKey));

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson("done", actionKind, "counter_cleared", {{"counter_key", counterKey}}, {{"player_guid", playerGuid}}));
        return true;
    }

    bool ExecuteQuestRemove(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 questId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"quest_id", "questId", "entry"}, questId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_quest_id"), "missing_quest_id");
            return true;
        }

        Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
        if (!quest)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_quest", {}, {{"quest_id", questId}}), "invalid_quest");
            return true;
        }

        bool adminOverride = false;
        TryExtractAnyBoolField(payloadJson, {"admin_override", "adminOverride"}, adminOverride);
        if (!adminOverride)
        {
            QueryResult reservedQuest = WorldDatabase.Query(
                "SELECT ReservedID FROM wm_reserved_slot WHERE EntityType = 'quest' AND ReservedID = {} LIMIT 1",
                questId);
            if (!reservedQuest)
            {
                CompleteAction(
                    requestId,
                    "rejected",
                    actionKind,
                    ActionResultJson("rejected", actionKind, "non_managed_quest_remove_denied", {}, {{"quest_id", questId}, {"player_guid", playerGuid}}),
                    "non_managed_quest_remove_denied");
                return true;
            }
        }

        bool removeRewarded = false;
        TryExtractAnyBoolField(payloadJson, {"remove_rewarded", "removeRewarded"}, removeRewarded);
        bool wasRewarded = player->GetQuestRewardStatus(questId);
        QuestStatus beforeStatus = player->GetQuestStatus(questId);
        uint32 removedSlots = 0;

        for (uint8 slot = 0; slot < MAX_QUEST_LOG_SIZE; ++slot)
        {
            uint32 logQuest = player->GetQuestSlotQuestId(slot);
            if (logQuest != questId)
            {
                continue;
            }

            player->SetQuestSlot(slot, 0);
            player->TakeQuestSourceItem(logQuest, false);
            if (quest->HasFlag(QUEST_FLAGS_FLAGS_PVP))
            {
                player->pvpInfo.IsHostile = player->pvpInfo.IsInHostileArea || player->HasPvPForcingQuest();
                player->UpdatePvPState();
            }
            ++removedSlots;
        }

        if (beforeStatus != QUEST_STATUS_NONE || removedSlots > 0)
        {
            if (quest->HasSpecialFlag(QUEST_SPECIAL_FLAGS_TIMED))
            {
                player->RemoveTimedQuest(questId);
            }
            player->RemoveActiveQuest(questId, true);
        }

        bool removedRewarded = false;
        if (removeRewarded && wasRewarded)
        {
            player->RemoveRewardedQuest(questId, true);
            removedRewarded = true;
        }

        player->SaveToDB(false, false);
        EmitQuestRemovedEvent(player, quest, removedSlots, removedRewarded);
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                removedSlots > 0 || beforeStatus != QUEST_STATUS_NONE || removedRewarded ? "quest_removed" : "quest_not_active",
                {},
                {{"quest_id", questId}, {"player_guid", playerGuid}, {"removed_slots", removedSlots}, {"removed_rewarded", removedRewarded ? 1 : 0}}));
        return true;
    }

    bool ExecuteQuestAdd(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (!player)
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
            return true;
        }

        uint32 questId = 0;
        if (!TryExtractJsonUInt32Field(payloadJson, "quest_id", questId) &&
            !TryExtractJsonUInt32Field(payloadJson, "questId", questId))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_quest_id"), "missing_quest_id");
            return true;
        }

        Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
        if (!quest)
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "invalid_quest"), "invalid_quest");
            return true;
        }

        ItemTemplateContainer const* itemTemplates = sObjectMgr->GetItemTemplateStore();
        bool startsFromItem = std::any_of(
            itemTemplates->begin(),
            itemTemplates->end(),
            [questId](ItemTemplateContainer::value_type const& entry)
            {
                return entry.second.StartQuest == questId;
            }
        );

        if (startsFromItem)
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "quest_starts_from_item"), "quest_starts_from_item");
            return true;
        }

        // Mirror GM .quest add semantics for WM grants instead of player quest-offer eligibility.
        if (player->IsActiveQuest(questId))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "quest_already_active"), "quest_already_active");
            return true;
        }

        if (!player->CanAddQuest(quest, false))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "cannot_add_quest"), "cannot_add_quest");
            return true;
        }

        player->AddQuestAndCheckCompletion(quest, nullptr);
        EmitQuestGrantedEvent(player, quest);
        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "quest_added"));
        return true;
    }

    bool ExecuteQuestComplete(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 questId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"quest_id", "questId", "entry"}, questId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_quest_id"), "missing_quest_id");
            return true;
        }

        Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
        if (!quest)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_quest", {}, {{"quest_id", questId}}), "invalid_quest");
            return true;
        }

        bool adminOverride = false;
        TryExtractAnyBoolField(payloadJson, {"admin_override", "adminOverride"}, adminOverride);
        if (!adminOverride)
        {
            QueryResult reservedQuest = WorldDatabase.Query(
                "SELECT ReservedID FROM wm_reserved_slot WHERE EntityType = 'quest' AND ReservedID = {} LIMIT 1",
                questId);
            if (!reservedQuest)
            {
                CompleteAction(
                    requestId,
                    "rejected",
                    actionKind,
                    ActionResultJson("rejected", actionKind, "non_managed_quest_complete_denied", {}, {{"quest_id", questId}, {"player_guid", playerGuid}}),
                    "non_managed_quest_complete_denied");
                return true;
            }
        }

        QuestStatus beforeStatus = player->GetQuestStatus(questId);
        if (beforeStatus == QUEST_STATUS_NONE)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "quest_not_active", {}, {{"quest_id", questId}, {"player_guid", playerGuid}}), "quest_not_active");
            return true;
        }
        if (beforeStatus == QUEST_STATUS_REWARDED)
        {
            CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "quest_already_rewarded", {}, {{"quest_id", questId}, {"player_guid", playerGuid}}));
            return true;
        }

        player->CompleteQuest(questId);
        QuestStatus afterStatus = player->GetQuestStatus(questId);
        player->SaveToDB(false, false);

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                afterStatus == QUEST_STATUS_COMPLETE ? "quest_completed" : "quest_not_completed",
                {},
                {{"quest_id", questId}, {"player_guid", playerGuid}, {"before_status", static_cast<long long>(beforeStatus)}, {"after_status", static_cast<long long>(afterStatus)}}));
        return true;
    }

    bool ExecuteQuestFail(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 questId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"quest_id", "questId", "entry"}, questId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_quest_id"), "missing_quest_id");
            return true;
        }

        Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
        if (!quest)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_quest", {}, {{"quest_id", questId}}), "invalid_quest");
            return true;
        }

        bool adminOverride = false;
        TryExtractAnyBoolField(payloadJson, {"admin_override", "adminOverride"}, adminOverride);
        if (!adminOverride)
        {
            QueryResult reservedQuest = WorldDatabase.Query(
                "SELECT ReservedID FROM wm_reserved_slot WHERE EntityType = 'quest' AND ReservedID = {} LIMIT 1",
                questId);
            if (!reservedQuest)
            {
                CompleteAction(
                    requestId,
                    "rejected",
                    actionKind,
                    ActionResultJson("rejected", actionKind, "non_managed_quest_fail_denied", {}, {{"quest_id", questId}, {"player_guid", playerGuid}}),
                    "non_managed_quest_fail_denied");
                return true;
            }
        }

        QuestStatus beforeStatus = player->GetQuestStatus(questId);
        player->FailQuest(questId);
        QuestStatus afterStatus = player->GetQuestStatus(questId);
        player->SaveToDB(false, false);

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                afterStatus == QUEST_STATUS_FAILED ? "quest_failed" : "quest_not_failed",
                {},
                {{"quest_id", questId}, {"player_guid", playerGuid}, {"before_status", static_cast<long long>(beforeStatus)}, {"after_status", static_cast<long long>(afterStatus)}}));
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgeQuestActions(ActionRegistry& registry)
    {
        registry.Register("quest_add", &ExecuteQuestAdd);
        registry.Register("quest_remove", &ExecuteQuestRemove);
        registry.Register("quest_complete", &ExecuteQuestComplete);
        registry.Register("quest_fail", &ExecuteQuestFail);
        registry.Register("wm_counter_set", &ExecuteWmCounterSet);
        registry.Register("wm_counter_increment", &ExecuteWmCounterIncrement);
        registry.Register("wm_counter_clear", &ExecuteWmCounterClear);
    }
}
