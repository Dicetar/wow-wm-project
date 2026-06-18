#include "Creature.h"
#include "DatabaseEnv.h"
#include "MapMgr.h"
#include "MotionMaster.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QueryResult.h"
#include "TemporarySummon.h"
#include "WorldSession.h"
#include "wm_bridge_action_registry.h"
#include "wm_bridge_action_support.h"
#include "wm_bridge_common.h"
#include "wm_bridge_json.h"

#include <algorithm>
#include <cctype>
#include <string>

namespace
{
    using WmBridge::EscapeForJson;
    using namespace WmBridge::detail;

    struct CompanionRef
    {
        uint64 objectId = 0;
        uint32 entry = 0;
        uint32 liveGuidLow = 0;
        std::string liveGuid;
        std::string arcKey;
        std::string companionKey;
        std::string state;
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

    std::string ExtractCompanionKey(std::string const& payloadJson)
    {
        std::string companionKey = ExtractJsonStringField(payloadJson, "companion_key");
        if (companionKey.empty())
        {
            companionKey = ExtractJsonStringField(payloadJson, "companionKey");
        }
        if (companionKey.size() > 128)
        {
            companionKey.resize(128);
        }

        return companionKey;
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
            liveGuid = ExtractJsonStringField(payloadJson, "creature_guid");
        }
        if (liveGuid.empty())
        {
            liveGuid = ExtractJsonStringField(payloadJson, "creatureGuid");
        }

        return liveGuid;
    }

    bool ExtractCompanionText(std::string const& payloadJson, std::string& text)
    {
        text = ExtractJsonStringField(payloadJson, "text");
        if (text.empty())
        {
            text = ExtractJsonStringField(payloadJson, "message");
        }
        if (text.empty())
        {
            return false;
        }
        if (text.size() > 255)
        {
            text.resize(255);
        }

        return true;
    }

    bool ExtractCompanionState(std::string const& payloadJson, std::string& state)
    {
        state = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "state"));
        if (state.empty())
        {
            state = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "companion_state"));
        }
        if (state.empty())
        {
            state = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "companionState"));
        }
        if (state.empty() || state.size() > 64)
        {
            return false;
        }

        for (char c : state)
        {
            if (!std::isalnum(static_cast<unsigned char>(c)) && c != '_' && c != '-')
            {
                return false;
            }
        }

        return true;
    }

    void PopulateCompanionRef(Field* fields, CompanionRef& ref)
    {
        ref.objectId = fields[0].IsNull() ? 0 : fields[0].Get<uint64>();
        ref.entry = fields[1].IsNull() ? 0 : fields[1].Get<uint32>();
        ref.liveGuidLow = fields[2].IsNull() ? 0 : fields[2].Get<uint32>();
        ref.liveGuid = fields[3].IsNull() ? "" : fields[3].Get<std::string>();
        ref.arcKey = fields[4].IsNull() ? "" : fields[4].Get<std::string>();
        ref.companionKey = fields[5].IsNull() ? "" : fields[5].Get<std::string>();
        ref.state = fields[6].IsNull() ? "" : fields[6].Get<std::string>();
    }

    bool LoadCompanionRef(uint32 playerGuid, std::string const& payloadJson, CompanionRef& ref, std::string& errorText)
    {
        QueryResult result;
        uint32 objectId = 0;
        uint32 liveGuidLow = 0;
        std::string arcKey = ExtractArcKey(payloadJson);
        std::string companionKey = ExtractCompanionKey(payloadJson);
        std::string liveGuid = ExtractLiveGuid(payloadJson);

        if (TryExtractAnyUInt32Field(payloadJson, {"object_id", "objectId"}, objectId))
        {
            result = WorldDatabase.Query(
                "SELECT wo.ObjectID, wo.TemplateEntry, wo.LiveGUIDLow, wo.LiveGUID, wo.ArcKey, c.CompanionKey, c.State "
                "FROM wm_bridge_world_object wo "
                "LEFT JOIN wm_bridge_companion c ON c.PlayerGUID = wo.OwnerPlayerGUID AND c.ActiveCreatureGUID = wo.LiveGUID "
                "WHERE wo.ObjectID = {} AND wo.ObjectType = 'companion' AND wo.OwnerPlayerGUID = {} AND wo.DespawnPolicy <> 'despawned' "
                "LIMIT 1",
                objectId,
                playerGuid);
        }
        else if (TryExtractAnyUInt32Field(payloadJson, {"live_guid_low", "liveGuidLow", "creature_guid_low", "creatureGuidLow"}, liveGuidLow))
        {
            result = WorldDatabase.Query(
                "SELECT wo.ObjectID, wo.TemplateEntry, wo.LiveGUIDLow, wo.LiveGUID, wo.ArcKey, c.CompanionKey, c.State "
                "FROM wm_bridge_world_object wo "
                "LEFT JOIN wm_bridge_companion c ON c.PlayerGUID = wo.OwnerPlayerGUID AND c.ActiveCreatureGUID = wo.LiveGUID "
                "WHERE wo.LiveGUIDLow = {} AND wo.ObjectType = 'companion' AND wo.OwnerPlayerGUID = {} AND wo.DespawnPolicy <> 'despawned' "
                "ORDER BY wo.ObjectID DESC LIMIT 1",
                liveGuidLow,
                playerGuid);
        }
        else if (!liveGuid.empty())
        {
            result = WorldDatabase.Query(
                "SELECT wo.ObjectID, wo.TemplateEntry, wo.LiveGUIDLow, wo.LiveGUID, wo.ArcKey, c.CompanionKey, c.State "
                "FROM wm_bridge_world_object wo "
                "LEFT JOIN wm_bridge_companion c ON c.PlayerGUID = wo.OwnerPlayerGUID AND c.ActiveCreatureGUID = wo.LiveGUID "
                "WHERE wo.LiveGUID = {} AND wo.ObjectType = 'companion' AND wo.OwnerPlayerGUID = {} AND wo.DespawnPolicy <> 'despawned' "
                "ORDER BY wo.ObjectID DESC LIMIT 1",
                SqlString(liveGuid),
                playerGuid);
        }
        else if (!arcKey.empty())
        {
            result = WorldDatabase.Query(
                "SELECT wo.ObjectID, wo.TemplateEntry, wo.LiveGUIDLow, wo.LiveGUID, wo.ArcKey, c.CompanionKey, c.State "
                "FROM wm_bridge_world_object wo "
                "LEFT JOIN wm_bridge_companion c ON c.PlayerGUID = wo.OwnerPlayerGUID AND c.ActiveCreatureGUID = wo.LiveGUID "
                "WHERE wo.ArcKey = {} AND wo.ObjectType = 'companion' AND wo.OwnerPlayerGUID = {} AND wo.DespawnPolicy <> 'despawned' "
                "ORDER BY wo.ObjectID DESC LIMIT 1",
                SqlString(arcKey),
                playerGuid);
        }
        else if (!companionKey.empty())
        {
            result = WorldDatabase.Query(
                "SELECT wo.ObjectID, wo.TemplateEntry, wo.LiveGUIDLow, wo.LiveGUID, wo.ArcKey, c.CompanionKey, c.State "
                "FROM wm_bridge_companion c "
                "LEFT JOIN wm_bridge_world_object wo ON wo.OwnerPlayerGUID = c.PlayerGUID AND wo.LiveGUID = c.ActiveCreatureGUID AND wo.ObjectType = 'companion' AND wo.DespawnPolicy <> 'despawned' "
                "WHERE c.PlayerGUID = {} AND c.CompanionKey = {} AND c.ActiveCreatureGUID IS NOT NULL "
                "ORDER BY wo.ObjectID DESC LIMIT 1",
                playerGuid,
                SqlString(companionKey));
        }
        else
        {
            errorText = "missing_companion_reference";
            return false;
        }

        if (!result)
        {
            errorText = "wm_companion_not_found";
            return false;
        }

        PopulateCompanionRef(result->Fetch(), ref);
        if (ref.entry == 0 || ref.liveGuidLow == 0)
        {
            errorText = "wm_companion_not_active";
            return false;
        }

        return true;
    }

    Creature* ResolveCompanionCreature(Player* player, CompanionRef const& ref)
    {
        if (!player || ref.entry == 0 || ref.liveGuidLow == 0)
        {
            return nullptr;
        }

        ObjectGuid guid = ObjectGuid::Create<HighGuid::Unit>(ref.entry, static_cast<ObjectGuid::LowType>(ref.liveGuidLow));
        return ObjectAccessor::GetCreature(*player, guid);
    }

    bool ResolveLiveCompanion(
        uint64 requestId,
        uint32 playerGuid,
        std::string const& actionKind,
        std::string const& payloadJson,
        Player*& player,
        CompanionRef& ref,
        Creature*& companion)
    {
        player = nullptr;
        companion = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return false;
        }

        std::string errorText;
        if (!LoadCompanionRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return false;
        }

        companion = ResolveCompanionCreature(player, ref);
        if (!companion)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "companion_not_live", {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "companion_not_live");
            return false;
        }

        return true;
    }

    void MarkCompanionObjectDespawned(CompanionRef const& ref, std::string const& reason)
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

    void UpdateCompanionTableByRef(uint32 playerGuid, CompanionRef const& ref, std::string const& state, std::string const& followMode)
    {
        if (!ref.companionKey.empty())
        {
            WorldDatabase.Execute(
                "UPDATE wm_bridge_companion "
                "SET State = {}, FollowMode = {}, UpdatedAt = CURRENT_TIMESTAMP "
                "WHERE PlayerGUID = {} AND CompanionKey = {}",
                SqlString(state),
                followMode.empty() ? "NULL" : SqlString(followMode),
                playerGuid,
                SqlString(ref.companionKey));
            return;
        }

        if (!ref.liveGuid.empty())
        {
            WorldDatabase.Execute(
                "UPDATE wm_bridge_companion "
                "SET State = {}, FollowMode = {}, UpdatedAt = CURRENT_TIMESTAMP "
                "WHERE PlayerGUID = {} AND ActiveCreatureGUID = {}",
                SqlString(state),
                followMode.empty() ? "NULL" : SqlString(followMode),
                playerGuid,
                SqlString(ref.liveGuid));
        }
    }

    void ClearCompanionActiveCreature(uint32 playerGuid, CompanionRef const& ref)
    {
        if (!ref.companionKey.empty())
        {
            WorldDatabase.Execute(
                "UPDATE wm_bridge_companion "
                "SET State = 'inactive', FollowMode = NULL, ActiveCreatureGUID = NULL, UpdatedAt = CURRENT_TIMESTAMP "
                "WHERE PlayerGUID = {} AND CompanionKey = {}",
                playerGuid,
                SqlString(ref.companionKey));
            return;
        }

        if (!ref.liveGuid.empty())
        {
            WorldDatabase.Execute(
                "UPDATE wm_bridge_companion "
                "SET State = 'inactive', FollowMode = NULL, ActiveCreatureGUID = NULL, UpdatedAt = CURRENT_TIMESTAMP "
                "WHERE PlayerGUID = {} AND ActiveCreatureGUID = {}",
                playerGuid,
                SqlString(ref.liveGuid));
        }
    }

    void DespawnPreviousCompanionForKey(Player* player, uint32 playerGuid, std::string const& companionKey)
    {
        if (!player || companionKey.empty())
        {
            return;
        }

        QueryResult result = WorldDatabase.Query(
            "SELECT wo.ObjectID, wo.TemplateEntry, wo.LiveGUIDLow, wo.LiveGUID, wo.ArcKey, c.CompanionKey, c.State "
            "FROM wm_bridge_companion c "
            "LEFT JOIN wm_bridge_world_object wo ON wo.OwnerPlayerGUID = c.PlayerGUID AND wo.LiveGUID = c.ActiveCreatureGUID AND wo.ObjectType = 'companion' AND wo.DespawnPolicy <> 'despawned' "
            "WHERE c.PlayerGUID = {} AND c.CompanionKey = {} AND c.ActiveCreatureGUID IS NOT NULL "
            "ORDER BY wo.ObjectID DESC LIMIT 1",
            playerGuid,
            SqlString(companionKey));
        if (!result)
        {
            return;
        }

        CompanionRef ref;
        PopulateCompanionRef(result->Fetch(), ref);
        if (Creature* previous = ResolveCompanionCreature(player, ref))
        {
            previous->DespawnOrUnsummon();
        }
        MarkCompanionObjectDespawned(ref, "replaced");
    }

    bool ExecuteCompanionSpawn(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 entry = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"creature_entry", "creatureEntry", "entry"}, entry))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_creature_entry"), "missing_creature_entry");
            return true;
        }
        if (!sObjectMgr->GetCreatureTemplate(entry))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_creature", {}, {{"creature_entry", entry}}), "invalid_creature");
            return true;
        }

        std::string arcKey = ExtractArcKey(payloadJson);
        std::string companionKey = ExtractCompanionKey(payloadJson);
        if (companionKey.empty())
        {
            companionKey = arcKey.empty() ? "default" : arcKey;
        }

        uint32 durationMs = 600000;
        TryExtractAnyUInt32Field(payloadJson, {"duration_ms", "durationMs"}, durationMs);
        durationMs = std::clamp<uint32>(durationMs, 5000, 3600000);
        float followDistance = 2.5f;
        float followAngle = 0.0f;
        TryExtractAnyFloatField(payloadJson, {"follow_distance", "followDistance"}, followDistance);
        TryExtractAnyFloatField(payloadJson, {"follow_angle", "followAngle"}, followAngle);
        followDistance = std::clamp<float>(followDistance, 0.5f, 30.0f);

        DespawnPreviousCompanionForKey(player, playerGuid, companionKey);

        Position position;
        player->GetClosePoint(position.m_positionX, position.m_positionY, position.m_positionZ, 1.0f, followDistance, player->GetOrientation() + followAngle);
        TempSummon* companion = player->SummonCreature(
            entry,
            position.m_positionX,
            position.m_positionY,
            position.m_positionZ,
            player->GetOrientation(),
            TEMPSUMMON_TIMED_DESPAWN,
            durationMs);
        if (!companion)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "companion_not_spawned", {}, {{"creature_entry", entry}}), "companion_not_spawned");
            return true;
        }

        companion->SetCreatorGUID(player->GetGUID());
        companion->SetOwnerGUID(player->GetGUID());
        companion->SetFaction(player->GetFaction());
        companion->SetPhaseMask(player->GetPhaseMask(), false);
        companion->GetMotionMaster()->MoveFollow(player, followDistance, followAngle);

        std::string metadata = "{";
        bool firstField = true;
        JsonAppendNumberField(metadata, firstField, "request_id", static_cast<long long>(requestId));
        JsonAppendNumberField(metadata, firstField, "duration_ms", durationMs);
        JsonAppendStringField(metadata, firstField, "companion_key", companionKey);
        JsonAppendFloatField(metadata, firstField, "follow_distance", followDistance);
        JsonAppendFloatField(metadata, firstField, "follow_angle", followAngle);
        metadata += "}";

        WorldDatabase.DirectExecute(
            "INSERT INTO wm_bridge_world_object ("
            "ObjectType, OwnerPlayerGUID, ArcKey, TemplateEntry, LiveGUID, LiveGUIDLow, MapID, PositionX, PositionY, PositionZ, Orientation, PhaseMask, DespawnPolicy, MetadataJSON"
            ") VALUES ('companion', {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, 'timed', {})",
            playerGuid,
            arcKey.empty() ? "NULL" : SqlString(arcKey),
            entry,
            SqlString(companion->GetGUID().ToString()),
            static_cast<uint32>(companion->GetGUID().GetCounter()),
            player->GetMapId(),
            companion->GetPositionX(),
            companion->GetPositionY(),
            companion->GetPositionZ(),
            companion->GetOrientation(),
            companion->GetPhaseMask(),
            SqlString(metadata));

        QueryResult objectIdResult = WorldDatabase.Query(
            "SELECT ObjectID FROM wm_bridge_world_object "
            "WHERE ObjectType = 'companion' AND OwnerPlayerGUID = {} AND LiveGUIDLow = {} "
            "ORDER BY ObjectID DESC LIMIT 1",
            playerGuid,
            static_cast<uint32>(companion->GetGUID().GetCounter()));
        uint64 objectId = objectIdResult ? objectIdResult->Fetch()[0].Get<uint64>() : 0;

        std::string appearance = "{\"creature_entry\":" + std::to_string(entry) + "}";
        std::string profile = "{";
        firstField = true;
        JsonAppendNumberField(profile, firstField, "object_id", static_cast<long long>(objectId));
        JsonAppendStringField(profile, firstField, "arc_key", arcKey);
        profile += "}";
        WorldDatabase.Execute(
            "INSERT INTO wm_bridge_companion (PlayerGUID, CompanionKey, State, FollowMode, ActiveCreatureGUID, AppearanceJSON, ProfileJSON) "
            "VALUES ({}, {}, 'active', 'follow', {}, {}, {}) "
            "ON DUPLICATE KEY UPDATE State = VALUES(State), FollowMode = VALUES(FollowMode), ActiveCreatureGUID = VALUES(ActiveCreatureGUID), AppearanceJSON = VALUES(AppearanceJSON), ProfileJSON = VALUES(ProfileJSON), UpdatedAt = CURRENT_TIMESTAMP",
            playerGuid,
            SqlString(companionKey),
            SqlString(companion->GetGUID().ToString()),
            SqlString(appearance),
            SqlString(profile));

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "companion_spawned",
                {{"companion_key", companionKey}, {"live_guid", companion->GetGUID().ToString()}, {"arc_key", arcKey}},
                {{"object_id", static_cast<long long>(objectId)}, {"creature_entry", entry}, {"live_guid_low", static_cast<long long>(companion->GetGUID().GetCounter())}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecuteCompanionDespawn(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        CompanionRef ref;
        Creature* companion = nullptr;
        if (!ResolveLiveCompanion(requestId, playerGuid, actionKind, payloadJson, player, ref, companion))
        {
            return true;
        }

        companion->DespawnOrUnsummon();
        MarkCompanionObjectDespawned(ref, "requested");
        ClearCompanionActiveCreature(playerGuid, ref);
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "companion_despawned", {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}, {"live_guid_low", ref.liveGuidLow}}));
        return true;
    }

    bool ExecuteCompanionFollow(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        CompanionRef ref;
        Creature* companion = nullptr;
        if (!ResolveLiveCompanion(requestId, playerGuid, actionKind, payloadJson, player, ref, companion))
        {
            return true;
        }

        float followDistance = 2.5f;
        float followAngle = 0.0f;
        TryExtractAnyFloatField(payloadJson, {"follow_distance", "followDistance"}, followDistance);
        TryExtractAnyFloatField(payloadJson, {"follow_angle", "followAngle"}, followAngle);
        followDistance = std::clamp<float>(followDistance, 0.5f, 30.0f);

        companion->StopMoving();
        companion->GetMotionMaster()->MoveFollow(player, followDistance, followAngle);
        UpdateCompanionTableByRef(playerGuid, ref, "active", "follow");
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "companion_following_player",
                {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}},
                {{"object_id", static_cast<long long>(ref.objectId)}},
                {{"follow_distance", followDistance}, {"follow_angle", followAngle}}));
        return true;
    }

    bool ExecuteCompanionWait(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        CompanionRef ref;
        Creature* companion = nullptr;
        if (!ResolveLiveCompanion(requestId, playerGuid, actionKind, payloadJson, player, ref, companion))
        {
            return true;
        }

        companion->StopMoving();
        companion->GetMotionMaster()->MoveIdle();
        UpdateCompanionTableByRef(playerGuid, ref, "waiting", "wait");
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "companion_waiting", {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}));
        return true;
    }

    bool ExecuteCompanionMoveTo(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        CompanionRef ref;
        Creature* companion = nullptr;
        if (!ResolveLiveCompanion(requestId, playerGuid, actionKind, payloadJson, player, ref, companion))
        {
            return true;
        }

        float x = 0.0f;
        float y = 0.0f;
        float z = 0.0f;
        if (!TryExtractAnyFloatField(payloadJson, {"x"}, x) ||
            !TryExtractAnyFloatField(payloadJson, {"y"}, y) ||
            !TryExtractAnyFloatField(payloadJson, {"z"}, z))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_coordinates"), "missing_coordinates");
            return true;
        }

        float orientation = companion->GetOrientation();
        TryExtractAnyFloatField(payloadJson, {"o", "orientation"}, orientation);
        orientation = Position::NormalizeOrientation(orientation);
        if (!MapMgr::IsValidMapCoord(player->GetMapId(), x, y, z, orientation))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_coordinates"), "invalid_coordinates");
            return true;
        }

        bool run = true;
        TryExtractAnyBoolField(payloadJson, {"run"}, run);
        companion->StopMoving();
        companion->GetMotionMaster()->MovePoint(0, x, y, z, run ? FORCED_MOVEMENT_RUN : FORCED_MOVEMENT_WALK, 0.0f, orientation);
        UpdateCompanionTableByRef(playerGuid, ref, "active", "move_to");
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "companion_moving_to_point",
                {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}},
                {{"object_id", static_cast<long long>(ref.objectId)}},
                {{"x", x}, {"y", y}, {"z", z}}));
        return true;
    }

    bool ExecuteCompanionSay(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        CompanionRef ref;
        Creature* companion = nullptr;
        if (!ResolveLiveCompanion(requestId, playerGuid, actionKind, payloadJson, player, ref, companion))
        {
            return true;
        }

        std::string text;
        if (!ExtractCompanionText(payloadJson, text))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_text"), "missing_text");
            return true;
        }

        companion->Say(text, LANG_UNIVERSAL, player);
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "companion_said", {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}));
        return true;
    }

    bool ExecuteCompanionWhisper(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        CompanionRef ref;
        Creature* companion = nullptr;
        if (!ResolveLiveCompanion(requestId, playerGuid, actionKind, payloadJson, player, ref, companion))
        {
            return true;
        }

        std::string text;
        if (!ExtractCompanionText(payloadJson, text))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_text"), "missing_text");
            return true;
        }

        companion->Whisper(text, LANG_UNIVERSAL, player);
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "companion_whispered", {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}));
        return true;
    }

    bool ExecuteCompanionEmote(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        CompanionRef ref;
        Creature* companion = nullptr;
        if (!ResolveLiveCompanion(requestId, playerGuid, actionKind, payloadJson, player, ref, companion))
        {
            return true;
        }

        uint32 emoteId = 0;
        std::string text = ExtractJsonStringField(payloadJson, "text");
        if (text.empty())
        {
            text = ExtractJsonStringField(payloadJson, "message");
        }
        if (!TryExtractAnyUInt32Field(payloadJson, {"emote_id", "emoteId"}, emoteId) && text.empty())
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_emote"), "missing_emote");
            return true;
        }

        if (emoteId > 0)
        {
            companion->HandleEmoteCommand(emoteId);
        }
        if (!text.empty())
        {
            if (text.size() > 255)
            {
                text.resize(255);
            }
            companion->TextEmote(text, player);
        }

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "companion_emoted", {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}, {"emote_id", emoteId}}));
        return true;
    }

    bool ExecuteCompanionSetState(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        std::string state;
        if (!ExtractCompanionState(payloadJson, state))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_state"), "invalid_state");
            return true;
        }

        std::string companionKey = ExtractCompanionKey(payloadJson);
        if (!companionKey.empty())
        {
            WorldDatabase.Execute(
                "INSERT INTO wm_bridge_companion (PlayerGUID, CompanionKey, State) "
                "VALUES ({}, {}, {}) "
                "ON DUPLICATE KEY UPDATE State = VALUES(State), UpdatedAt = CURRENT_TIMESTAMP",
                playerGuid,
                SqlString(companionKey),
                SqlString(state));
            CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "companion_state_set", {{"companion_key", companionKey}, {"state", state}}));
            return true;
        }

        CompanionRef ref;
        std::string errorText;
        if (!LoadCompanionRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        UpdateCompanionTableByRef(playerGuid, ref, state, ref.state == "waiting" ? "wait" : "");
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "companion_state_set", {{"companion_key", ref.companionKey}, {"arc_key", ref.arcKey}, {"state", state}}, {{"object_id", static_cast<long long>(ref.objectId)}}));
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgeCompanionActions(ActionRegistry& registry)
    {
        registry.Register("companion_spawn", &ExecuteCompanionSpawn);
        registry.Register("companion_despawn", &ExecuteCompanionDespawn);
        registry.Register("companion_set_state", &ExecuteCompanionSetState);
        registry.Register("companion_follow", &ExecuteCompanionFollow);
        registry.Register("companion_wait", &ExecuteCompanionWait);
        registry.Register("companion_move_to", &ExecuteCompanionMoveTo);
        registry.Register("companion_say", &ExecuteCompanionSay);
        registry.Register("companion_whisper", &ExecuteCompanionWhisper);
        registry.Register("companion_emote", &ExecuteCompanionEmote);
    }
}
