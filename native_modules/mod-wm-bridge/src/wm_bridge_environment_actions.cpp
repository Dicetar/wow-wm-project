// Phase 0D: environment-domain native WM action handlers. Bodies moved
// verbatim from wm_bridge_action_queue.cpp; shared infra lives in
// wm_bridge_action_support.h (WmBridge::detail). Registered via
// RegisterWmBridgeEnvironmentActions from the queue bootstrap.

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
#include "Opcodes.h"
#include "Player.h"
#include "QueryResult.h"
#include "Random.h"
#include "ReputationMgr.h"
#include "SharedDefines.h"
#include "SpellMgr.h"
#include "TemporarySummon.h"
#include "Unit.h"
#include "WorldPacket.h"
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

    uint32 gPerceptionRefreshTimer = 0;

    std::string BuildCreatureJson(Player const* player, Creature const* creature)
    {
        std::string json = "{";
        bool firstField = true;
        JsonAppendNumberField(json, firstField, "entry", creature->GetEntry());
        JsonAppendStringField(json, firstField, "name", creature->GetName());
        JsonAppendStringField(json, firstField, "guid", creature->GetGUID().ToString());
        JsonAppendNumberField(json, firstField, "level", creature->GetLevel());
        JsonAppendBoolField(json, firstField, "alive", creature->IsAlive());
        JsonAppendFloatField(json, firstField, "distance", player->GetDistance(creature));
        JsonAppendFloatField(json, firstField, "x", creature->GetPositionX());
        JsonAppendFloatField(json, firstField, "y", creature->GetPositionY());
        JsonAppendFloatField(json, firstField, "z", creature->GetPositionZ());
        json += "}";
        return json;
    }

    std::string BuildGameObjectJson(Player const* player, GameObject const* gameObject)
    {
        std::string json = "{";
        bool firstField = true;
        JsonAppendNumberField(json, firstField, "entry", gameObject->GetEntry());
        JsonAppendStringField(json, firstField, "name", gameObject->GetName());
        JsonAppendStringField(json, firstField, "guid", gameObject->GetGUID().ToString());
        JsonAppendNumberField(json, firstField, "type", static_cast<long long>(gameObject->GetGoType()));
        JsonAppendFloatField(json, firstField, "distance", player->GetDistance(gameObject));
        JsonAppendFloatField(json, firstField, "x", gameObject->GetPositionX());
        JsonAppendFloatField(json, firstField, "y", gameObject->GetPositionY());
        JsonAppendFloatField(json, firstField, "z", gameObject->GetPositionZ());
        json += "}";
        return json;
    }

    std::string BuildNearbyContextSnapshotJson(Player* player, uint64 actionRequestId, std::string const& contextKind, uint32 radius, uint32* outCreatureCount = nullptr, uint32* outGameObjectCount = nullptr)
    {
        std::list<WorldObject*> nearbyObjects;
        Acore::AllWorldObjectsInRange check(player, static_cast<float>(radius));
        Acore::WorldObjectListSearcher<Acore::AllWorldObjectsInRange> searcher(player, nearbyObjects, check);
        Cell::VisitObjects(player, searcher, static_cast<float>(radius));

        std::string creatures = "[";
        bool firstCreature = true;
        uint32 creatureCount = 0;
        std::string gameObjects = "[";
        bool firstGameObject = true;
        uint32 gameObjectCount = 0;

        for (WorldObject* object : nearbyObjects)
        {
            if (!object || object == player)
            {
                continue;
            }

            if (Creature* creature = object->ToCreature())
            {
                if (creatureCount >= 25)
                {
                    continue;
                }
                if (!firstCreature)
                {
                    creatures += ",";
                }
                firstCreature = false;
                creatures += BuildCreatureJson(player, creature);
                ++creatureCount;
                continue;
            }

            if (GameObject* gameObject = object->ToGameObject())
            {
                if (gameObjectCount >= 25)
                {
                    continue;
                }
                if (!firstGameObject)
                {
                    gameObjects += ",";
                }
                firstGameObject = false;
                gameObjects += BuildGameObjectJson(player, gameObject);
                ++gameObjectCount;
            }
        }

        creatures += "]";
        gameObjects += "]";

        if (outCreatureCount)
        {
            *outCreatureCount = creatureCount;
        }
        if (outGameObjectCount)
        {
            *outGameObjectCount = gameObjectCount;
        }

        std::string json = "{";
        bool firstField = true;
        JsonAppendStringField(json, firstField, "schema_version", "wm.bridge_context_snapshot.v1");
        JsonAppendNumberField(json, firstField, "action_request_id", static_cast<long long>(actionRequestId));
        JsonAppendStringField(json, firstField, "context_kind", contextKind);
        JsonAppendNumberField(json, firstField, "radius", radius);
        JsonAppendNumberField(json, firstField, "player_guid", static_cast<long long>(player->GetGUID().GetCounter()));
        JsonAppendStringField(json, firstField, "player_name", player->GetName());
        JsonAppendNumberField(json, firstField, "map_id", player->GetMapId());
        JsonAppendNumberField(json, firstField, "zone_id", player->GetZoneId());
        JsonAppendNumberField(json, firstField, "area_id", player->GetAreaId());
        JsonAppendFloatField(json, firstField, "x", player->GetPositionX());
        JsonAppendFloatField(json, firstField, "y", player->GetPositionY());
        JsonAppendFloatField(json, firstField, "z", player->GetPositionZ());
        JsonAppendFloatField(json, firstField, "o", player->GetOrientation());
        JsonAppendNumberField(json, firstField, "nearby_creature_count", creatureCount);
        JsonAppendNumberField(json, firstField, "nearby_gameobject_count", gameObjectCount);
        JsonAppendRawField(json, firstField, "nearby_creatures", creatures);
        JsonAppendRawField(json, firstField, "nearby_gameobjects", gameObjects);
        json += "}";
        return json;
    }

    bool WriteContextSnapshot(uint64 actionRequestId, uint32 playerGuid, std::string const& payloadJson, std::string& errorText)
    {
        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (!player)
        {
            errorText = "player_not_online";
            return false;
        }

        std::string contextKind = ExtractJsonStringField(payloadJson, "context_kind");
        if (contextKind.empty())
        {
            contextKind = ExtractJsonStringField(payloadJson, "contextKind");
        }
        if (contextKind.empty())
        {
            contextKind = "nearby";
        }

        uint32 radius = 40;
        uint32 requestedRadius = 0;
        if (TryExtractJsonUInt32Field(payloadJson, "radius", requestedRadius) && requestedRadius > 0)
        {
            radius = std::clamp<uint32>(requestedRadius, 5, 100);
        }

        std::string snapshotJson = BuildNearbyContextSnapshotJson(player, actionRequestId, contextKind, radius);
        WorldDatabase.Execute(
            "INSERT INTO wm_bridge_context_request (PlayerGUID, ContextKind, Radius, Status, RequestedBy, MetadataJSON, ProcessedAt) "
            "VALUES ({}, {}, {}, 'done', 'wm_bridge_action_queue', {}, NOW())",
            playerGuid,
            SqlString(contextKind),
            radius,
            SqlString(payloadJson));

        WorldDatabase.Execute(
            "INSERT INTO wm_bridge_context_snapshot (RequestID, PlayerGUID, ContextKind, Radius, MapID, ZoneID, AreaID, Source, PayloadJSON) "
            "VALUES (NULL, {}, {}, {}, {}, {}, {}, 'native_bridge', {})",
            playerGuid,
            SqlString(contextKind),
            radius,
            player->GetMapId(),
            player->GetZoneId(),
            player->GetAreaId(),
            SqlString(snapshotJson));

        return true;
    }

    bool ExecutePlayerSetDisplayId(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        bool restoreDisplay = false;
        if (TryExtractAnyBoolField(payloadJson, {"restore", "restore_display", "restoreDisplay"}, restoreDisplay) && restoreDisplay)
        {
            player->RestoreDisplayId();
            CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "display_restored", {}, {{"player_guid", playerGuid}, {"display_id", player->GetDisplayId()}}));
            return true;
        }

        uint32 displayId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"display_id", "displayId"}, displayId) || displayId == 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_display_id"), "missing_display_id");
            return true;
        }

        uint32 nativeDisplayId = displayId;
        TryExtractAnyUInt32Field(payloadJson, {"native_display_id", "nativeDisplayId"}, nativeDisplayId);
        float scale = player->GetObjectScale();
        bool hasScale = TryExtractAnyFloatField(payloadJson, {"scale", "object_scale", "objectScale"}, scale);
        if (hasScale)
        {
            scale = std::clamp<float>(scale, 0.25f, 3.0f);
        }

        player->SetDisplayId(displayId);
        player->SetNativeDisplayId(nativeDisplayId);
        if (hasScale)
        {
            player->SetObjectScale(scale);
        }

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "display_set",
                {},
                {{"player_guid", playerGuid}, {"display_id", displayId}, {"native_display_id", nativeDisplayId}},
                {{"scale", player->GetObjectScale()}}));
        return true;
    }

    bool ExecuteContextSnapshotRequest(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        std::string errorText;
        if (!WriteContextSnapshot(requestId, playerGuid, payloadJson, errorText))
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, errorText), errorText);
            return true;
        }

        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "context_snapshot_written"));
        return true;
    }

    bool ExecuteWorldAnnounceToPlayer(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (!player || !player->GetSession())
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
            return true;
        }

        std::string message = ExtractJsonStringField(payloadJson, "message");
        if (message.empty())
        {
            message = ExtractJsonStringField(payloadJson, "text");
        }
        if (message.empty())
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_message"), "missing_message");
            return true;
        }

        player->GetSession()->SendAreaTriggerMessage(message);
        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "message_sent"));
        return true;
    }

    std::string NormalizeChatStyle(std::string style)
    {
        if (style.empty())
        {
            style = "channel";
        }
        std::transform(style.begin(), style.end(), style.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
        if (style == "channel" || style == "whisper" || style == "system")
        {
            return style;
        }
        return "channel";
    }

    // The WoW 3.3.5a client refuses to render a single chat line longer than
    // ~255 bytes, so a long WM reply must be delivered as several packets rather
    // than truncated.  Split greedily on the last space at or after limit/2 to
    // keep words intact; hard-split only when there is no sensible break point.
    std::vector<std::string> SplitChatText(std::string const& text, std::size_t limit)
    {
        std::vector<std::string> parts;
        if (limit == 0)
        {
            parts.push_back(text);
            return parts;
        }

        std::string remaining = text;
        while (remaining.size() > limit)
        {
            std::size_t cut = remaining.rfind(' ', limit);
            if (cut == std::string::npos || cut < limit / 2)
            {
                cut = limit;
            }

            std::string chunk = remaining.substr(0, cut);
            while (!chunk.empty() && chunk.back() == ' ')
            {
                chunk.pop_back();
            }
            if (!chunk.empty())
            {
                parts.push_back(chunk);
            }

            remaining = remaining.substr(cut);
            std::size_t start = remaining.find_first_not_of(' ');
            remaining = (start == std::string::npos) ? std::string() : remaining.substr(start);
        }

        while (!remaining.empty() && remaining.back() == ' ')
        {
            remaining.pop_back();
        }
        if (!remaining.empty())
        {
            parts.push_back(remaining);
        }
        if (parts.empty())
        {
            parts.push_back(text);
        }
        return parts;
    }

    void BuildPlayerVisibleChatPacket(
        WorldPacket& data,
        ChatMsg chatType,
        ObjectGuid receiverGuid,
        std::string const& message,
        std::string const& senderName,
        std::string const& channelName)
    {
        data.Initialize(SMSG_MESSAGECHAT);
        data << uint8(chatType);
        data << int32(LANG_UNIVERSAL);
        data << ObjectGuid();
        data << uint32(0);

        if (chatType == CHAT_MSG_WHISPER_FOREIGN)
        {
            data << uint32(senderName.length() + 1);
            data << senderName;
        }
        else if (chatType == CHAT_MSG_CHANNEL)
        {
            data << channelName;
        }

        data << receiverGuid;
        data << uint32(message.length() + 1);
        data << message;
        data << uint8(CHAT_TAG_NONE);
    }

    bool ExecutePlayerChatMessage(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (!player || !player->GetSession())
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
            return true;
        }

        std::string message = ExtractJsonStringField(payloadJson, "message");
        if (message.empty())
        {
            message = ExtractJsonStringField(payloadJson, "text");
        }
        if (message.empty())
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_message"), "missing_message");
            return true;
        }

        std::string style = NormalizeChatStyle(ExtractJsonStringField(payloadJson, "style"));
        std::string channelName = ExtractJsonStringField(payloadJson, "channel_name");
        if (channelName.empty())
        {
            channelName = ExtractJsonStringField(payloadJson, "channelName");
        }
        if (channelName.empty())
        {
            channelName = "WM";
        }
        std::string senderName = ExtractJsonStringField(payloadJson, "sender_name");
        if (senderName.empty())
        {
            senderName = ExtractJsonStringField(payloadJson, "senderName");
        }
        if (senderName.empty())
        {
            senderName = "WorldMaster";
        }

        std::vector<std::string> chunks = SplitChatText(message, 220);
        std::size_t const maxParts = 6;  // ceiling so a runaway reply can't flood chat
        if (chunks.size() > maxParts)
        {
            chunks.resize(maxParts);
        }

        for (std::string const& chunk : chunks)
        {
            WorldPacket data;
            if (style == "system")
            {
                BuildPlayerVisibleChatPacket(
                    data,
                    CHAT_MSG_SYSTEM,
                    player->GetGUID(),
                    "[WM] " + chunk,
                    senderName,
                    channelName);
            }
            else if (style == "whisper")
            {
                BuildPlayerVisibleChatPacket(
                    data,
                    CHAT_MSG_WHISPER_FOREIGN,
                    player->GetGUID(),
                    chunk,
                    senderName,
                    channelName);
            }
            else
            {
                BuildPlayerVisibleChatPacket(
                    data,
                    CHAT_MSG_CHANNEL,
                    player->GetGUID(),
                    senderName + ": " + chunk,
                    senderName,
                    channelName);
            }
            player->SendDirectMessage(&data);
        }

        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "chat_message_sent"));
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgeEnvironmentActions(ActionRegistry& registry)
    {
        registry.Register("context_snapshot_request", &ExecuteContextSnapshotRequest);
        registry.Register("world_announce_to_player", &ExecuteWorldAnnounceToPlayer);
        registry.Register("player_chat_message", &ExecutePlayerChatMessage);
        registry.Register("player_set_display_id", &ExecutePlayerSetDisplayId);
    }

    void RefreshPlayerPerception(uint32 diff)
    {
        BridgeConfig const& cfg = GetConfig();
        if (!cfg.enabled || !cfg.perceptionEnabled)
        {
            return;
        }

        if (gPerceptionRefreshTimer > diff)
        {
            gPerceptionRefreshTimer -= diff;
            return;
        }

        gPerceptionRefreshTimer = cfg.perceptionIntervalMs;

        auto upsert = [&](Player* player)
        {
            if (!player || !player->IsInWorld())
            {
                return;
            }

            uint32 creatureCount = 0;
            uint32 gameObjectCount = 0;
            std::string const payload = BuildNearbyContextSnapshotJson(
                player, 0, "perception", cfg.perceptionRadius, &creatureCount, &gameObjectCount);

            WorldDatabase.Execute(
                "INSERT INTO wm_bridge_player_perception ("
                "PlayerGUID, MapID, ZoneID, AreaID, CreatureCount, GameObjectCount, PayloadJSON, UpdatedAt"
                ") VALUES ({}, {}, {}, {}, {}, {}, {}, NOW()) "
                "ON DUPLICATE KEY UPDATE "
                "MapID = VALUES(MapID), ZoneID = VALUES(ZoneID), AreaID = VALUES(AreaID), "
                "CreatureCount = VALUES(CreatureCount), GameObjectCount = VALUES(GameObjectCount), "
                "PayloadJSON = VALUES(PayloadJSON), UpdatedAt = NOW()",
                static_cast<uint32>(player->GetGUID().GetCounter()),
                player->GetMapId(),
                player->GetZoneId(),
                player->GetAreaId(),
                creatureCount,
                gameObjectCount,
                SqlString(payload));
        };

        if (cfg.allowAllPlayers)
        {
            for (auto const& pair : ObjectAccessor::GetPlayers())
            {
                upsert(pair.second);
            }
            return;
        }

        for (uint32 guid : cfg.playerGuidAllowList)
        {
            upsert(ObjectAccessor::FindPlayerByLowGUID(guid));
        }
        for (uint32 guid : cfg.dbPlayerGuidAllowList)
        {
            upsert(ObjectAccessor::FindPlayerByLowGUID(guid));
        }
    }
}
