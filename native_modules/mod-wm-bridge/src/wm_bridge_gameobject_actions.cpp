#include "DatabaseEnv.h"
#include "GameObject.h"
#include "MapMgr.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QueryResult.h"
#include "wm_bridge_action_registry.h"
#include "wm_bridge_action_support.h"
#include "wm_bridge_json.h"
#include "wm_bridge_placement.h"

#include <algorithm>
#include <cmath>
#include <string>

namespace
{
    using WmBridge::EscapeForJson;
    using namespace WmBridge::detail;

    struct OwnedGameObjectRef
    {
        uint64 objectId = 0;
        uint32 entry = 0;
        uint32 liveGuidLow = 0;
        std::string liveGuid;
        std::string arcKey;
    };

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

    std::string ExtractLiveGuid(std::string const& payloadJson)
    {
        std::string liveGuid = ExtractJsonStringField(payloadJson, "live_guid");
        if (liveGuid.empty())
        {
            liveGuid = ExtractJsonStringField(payloadJson, "liveGuid");
        }
        if (liveGuid.empty())
        {
            liveGuid = ExtractJsonStringField(payloadJson, "gameobject_guid");
        }
        if (liveGuid.empty())
        {
            liveGuid = ExtractJsonStringField(payloadJson, "gameobjectGuid");
        }

        return liveGuid;
    }

    bool LoadOwnedGameObjectRef(uint32 playerGuid, std::string const& payloadJson, OwnedGameObjectRef& ref, std::string& errorText)
    {
        QueryResult result;
        uint32 objectId = 0;
        uint32 liveGuidLow = 0;
        std::string arcKey = ExtractArcKey(payloadJson);
        std::string liveGuid = ExtractLiveGuid(payloadJson);

        if (TryExtractAnyUInt32Field(payloadJson, {"object_id", "objectId"}, objectId))
        {
            result = WorldDatabase.Query(
                "SELECT ObjectID, TemplateEntry, LiveGUIDLow, LiveGUID, ArcKey "
                "FROM wm_bridge_world_object "
                "WHERE ObjectID = {} AND ObjectType = 'gameobject' AND OwnerPlayerGUID = {} AND DespawnPolicy <> 'despawned' "
                "LIMIT 1",
                objectId,
                playerGuid);
        }
        else if (TryExtractAnyUInt32Field(payloadJson, {"live_guid_low", "liveGuidLow", "gameobject_guid_low", "gameobjectGuidLow"}, liveGuidLow))
        {
            result = WorldDatabase.Query(
                "SELECT ObjectID, TemplateEntry, LiveGUIDLow, LiveGUID, ArcKey "
                "FROM wm_bridge_world_object "
                "WHERE LiveGUIDLow = {} AND ObjectType = 'gameobject' AND OwnerPlayerGUID = {} AND DespawnPolicy <> 'despawned' "
                "ORDER BY ObjectID DESC LIMIT 1",
                liveGuidLow,
                playerGuid);
        }
        else if (!liveGuid.empty())
        {
            result = WorldDatabase.Query(
                "SELECT ObjectID, TemplateEntry, LiveGUIDLow, LiveGUID, ArcKey "
                "FROM wm_bridge_world_object "
                "WHERE LiveGUID = {} AND ObjectType = 'gameobject' AND OwnerPlayerGUID = {} AND DespawnPolicy <> 'despawned' "
                "ORDER BY ObjectID DESC LIMIT 1",
                SqlString(liveGuid),
                playerGuid);
        }
        else if (!arcKey.empty())
        {
            result = WorldDatabase.Query(
                "SELECT ObjectID, TemplateEntry, LiveGUIDLow, LiveGUID, ArcKey "
                "FROM wm_bridge_world_object "
                "WHERE ArcKey = {} AND ObjectType = 'gameobject' AND OwnerPlayerGUID = {} AND DespawnPolicy <> 'despawned' "
                "ORDER BY ObjectID DESC LIMIT 1",
                SqlString(arcKey),
                playerGuid);
        }
        else
        {
            errorText = "missing_gameobject_reference";
            return false;
        }

        if (!result)
        {
            errorText = "wm_owned_gameobject_not_found";
            return false;
        }

        Field* fields = result->Fetch();
        if (fields[1].IsNull() || fields[2].IsNull())
        {
            errorText = "wm_owned_gameobject_incomplete";
            return false;
        }

        ref.objectId = fields[0].Get<uint64>();
        ref.entry = fields[1].Get<uint32>();
        ref.liveGuidLow = fields[2].Get<uint32>();
        ref.liveGuid = fields[3].IsNull() ? "" : fields[3].Get<std::string>();
        ref.arcKey = fields[4].IsNull() ? "" : fields[4].Get<std::string>();
        return true;
    }

    GameObject* ResolveOwnedGameObject(Player* player, OwnedGameObjectRef const& ref)
    {
        if (!player || ref.entry == 0 || ref.liveGuidLow == 0)
        {
            return nullptr;
        }

        ObjectGuid guid = ObjectGuid::Create<HighGuid::GameObject>(ref.entry, static_cast<ObjectGuid::LowType>(ref.liveGuidLow));
        return ObjectAccessor::GetGameObject(*player, guid);
    }

    bool ResolveOwnedLiveGameObject(
        uint64 requestId,
        uint32 playerGuid,
        std::string const& actionKind,
        std::string const& payloadJson,
        Player*& player,
        OwnedGameObjectRef& ref,
        GameObject*& gameObject)
    {
        player = nullptr;
        gameObject = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return false;
        }

        std::string errorText;
        if (!LoadOwnedGameObjectRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return false;
        }

        gameObject = ResolveOwnedGameObject(player, ref);
        if (!gameObject)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "gameobject_not_live", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "gameobject_not_live");
            return false;
        }

        return true;
    }

    void MarkOwnedGameObjectDespawned(OwnedGameObjectRef const& ref, std::string const& reason)
    {
        if (ref.objectId == 0)
        {
            return;
        }

        std::string metadata = "{\"despawn_reason\":\"" + EscapeForJson(reason) + "\"}";
        WorldDatabase.Execute(
            "UPDATE wm_bridge_world_object "
            "SET DespawnPolicy = 'despawned', MetadataJSON = {}, UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE ObjectID = {}",
            SqlString(metadata),
            ref.objectId);
    }

    bool TryResolveGoState(std::string const& payloadJson, GOState& state)
    {
        uint32 value = 0;
        if (TryExtractAnyUInt32Field(payloadJson, {"state", "go_state", "goState"}, value))
        {
            if (value > static_cast<uint32>(GO_STATE_ACTIVE_ALTERNATIVE))
            {
                return false;
            }

            state = static_cast<GOState>(value);
            return true;
        }

        std::string token = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "state"));
        if (token.empty())
        {
            token = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "go_state"));
        }
        if (token.empty())
        {
            token = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "goState"));
        }

        if (token == "active" || token == "open" || token == "used")
        {
            state = GO_STATE_ACTIVE;
            return true;
        }
        if (token == "ready" || token == "closed" || token == "close")
        {
            state = GO_STATE_READY;
            return true;
        }
        if (token == "active_alternative" || token == "active-alternative" || token == "alternative" || token == "alt")
        {
            state = GO_STATE_ACTIVE_ALTERNATIVE;
            return true;
        }

        return false;
    }

    bool ExecuteGameObjectSpawn(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 entry = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"gameobject_entry", "gameobjectEntry", "entry"}, entry))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_gameobject_entry"), "missing_gameobject_entry");
            return true;
        }
        if (!sObjectMgr->GetGameObjectTemplate(entry))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_gameobject", {}, {{"gameobject_entry", entry}}), "invalid_gameobject");
            return true;
        }

        uint32 durationMs = 30000;
        TryExtractAnyUInt32Field(payloadJson, {"duration_ms", "durationMs"}, durationMs);
        durationMs = std::clamp<uint32>(durationMs, 1000, 600000);
        uint32 durationSeconds = std::max<uint32>(1, (durationMs + 999) / 1000);

        float distance = 2.5f;
        float angleOffset = 0.0f;
        TryExtractAnyFloatField(payloadJson, {"distance", "spawn_distance", "spawnDistance"}, distance);
        TryExtractAnyFloatField(payloadJson, {"angle_offset", "angleOffset"}, angleOffset);
        distance = std::clamp<float>(distance, 0.5f, 30.0f);

        Position position;
        player->GetClosePoint(position.m_positionX, position.m_positionY, position.m_positionZ, 1.0f, distance, player->GetOrientation() + angleOffset);
        position.SetOrientation(Position::NormalizeOrientation(player->GetOrientation() + angleOffset));
        if (!WmBridge::ResolvePlacement(player, payloadJson, position))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_spawn_position"), "invalid_spawn_position");
            return true;
        }

        float rot2 = std::sin(position.GetOrientation() / 2.0f);
        float rot3 = std::cos(position.GetOrientation() / 2.0f);
        GameObject* gameObject = player->SummonGameObject(
            entry,
            position.GetPositionX(),
            position.GetPositionY(),
            position.GetPositionZ(),
            position.GetOrientation(),
            0.0f,
            0.0f,
            rot2,
            rot3,
            durationSeconds);
        if (!gameObject)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "gameobject_not_spawned", {}, {{"gameobject_entry", entry}}), "gameobject_not_spawned");
            return true;
        }

        std::string arcKey = ExtractArcKey(payloadJson);
        std::string metadata = "{";
        bool firstField = true;
        JsonAppendNumberField(metadata, firstField, "request_id", static_cast<long long>(requestId));
        JsonAppendNumberField(metadata, firstField, "duration_ms", durationMs);
        JsonAppendNumberField(metadata, firstField, "duration_seconds", durationSeconds);
        metadata += "}";

        WorldDatabase.DirectExecute(
            "INSERT INTO wm_bridge_world_object ("
            "ObjectType, OwnerPlayerGUID, ArcKey, TemplateEntry, LiveGUID, LiveGUIDLow, MapID, PositionX, PositionY, PositionZ, Orientation, PhaseMask, DespawnPolicy, MetadataJSON"
            ") VALUES ('gameobject', {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, 'timed', {})",
            playerGuid,
            arcKey.empty() ? "NULL" : SqlString(arcKey),
            entry,
            SqlString(gameObject->GetGUID().ToString()),
            static_cast<uint32>(gameObject->GetGUID().GetCounter()),
            player->GetMapId(),
            gameObject->GetPositionX(),
            gameObject->GetPositionY(),
            gameObject->GetPositionZ(),
            gameObject->GetOrientation(),
            gameObject->GetPhaseMask(),
            SqlString(metadata));

        QueryResult objectIdResult = WorldDatabase.Query(
            "SELECT ObjectID FROM wm_bridge_world_object "
            "WHERE ObjectType = 'gameobject' AND OwnerPlayerGUID = {} AND LiveGUIDLow = {} "
            "ORDER BY ObjectID DESC LIMIT 1",
            playerGuid,
            static_cast<uint32>(gameObject->GetGUID().GetCounter()));
        uint64 objectId = objectIdResult ? objectIdResult->Fetch()[0].Get<uint64>() : 0;
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "gameobject_spawned",
                {{"live_guid", gameObject->GetGUID().ToString()}, {"arc_key", arcKey}},
                {
                    {"object_id", static_cast<long long>(objectId)},
                    {"gameobject_entry", entry},
                    {"live_guid_low", static_cast<long long>(gameObject->GetGUID().GetCounter())},
                    {"player_guid", playerGuid},
                }));
        return true;
    }

    bool ExecuteGameObjectDespawn(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        OwnedGameObjectRef ref;
        std::string errorText;
        if (!LoadOwnedGameObjectRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        GameObject* gameObject = ResolveOwnedGameObject(player, ref);
        if (!gameObject)
        {
            MarkOwnedGameObjectDespawned(ref, "gameobject_not_live");
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "gameobject_not_live", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "gameobject_not_live");
            return true;
        }

        gameObject->SetRespawnTime(0);
        gameObject->Delete();
        MarkOwnedGameObjectDespawned(ref, "requested");
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "gameobject_despawned", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}, {"live_guid_low", ref.liveGuidLow}}));
        return true;
    }

    bool ExecuteGameObjectSetState(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        OwnedGameObjectRef ref;
        GameObject* gameObject = nullptr;
        if (!ResolveOwnedLiveGameObject(requestId, playerGuid, actionKind, payloadJson, player, ref, gameObject))
        {
            return true;
        }

        GOState state = GO_STATE_READY;
        if (!TryResolveGoState(payloadJson, state))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_gameobject_state"), "invalid_gameobject_state");
            return true;
        }

        gameObject->SetGoState(state);
        gameObject->UpdateObjectVisibility();
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "gameobject_state_set",
                {{"arc_key", ref.arcKey}},
                {{"object_id", static_cast<long long>(ref.objectId)}, {"state", static_cast<long long>(state)}}));
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgeGameObjectActions(ActionRegistry& registry)
    {
        registry.Register("gameobject_spawn", &ExecuteGameObjectSpawn);
        registry.Register("gameobject_despawn", &ExecuteGameObjectDespawn);
        registry.Register("gameobject_set_state", &ExecuteGameObjectSetState);
    }
}
