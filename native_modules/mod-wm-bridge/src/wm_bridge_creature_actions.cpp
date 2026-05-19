// Phase 0D: creature-domain native WM action handlers. Bodies moved
// verbatim from wm_bridge_action_queue.cpp; shared infra lives in
// wm_bridge_action_support.h (WmBridge::detail). Registered via
// RegisterWmBridgeCreatureActions from the queue bootstrap.

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

    struct OwnedCreatureRef
    {
        uint64 objectId = 0;
        uint32 entry = 0;
        uint32 liveGuidLow = 0;
        std::string liveGuid;
        std::string arcKey;
    };

    bool LoadOwnedCreatureRef(uint32 playerGuid, std::string const& payloadJson, OwnedCreatureRef& ref, std::string& errorText)
    {
        QueryResult result;
        uint32 objectId = 0;
        uint32 liveGuidLow = 0;
        std::string arcKey = ExtractJsonStringField(payloadJson, "arc_key");
        if (arcKey.empty())
        {
            arcKey = ExtractJsonStringField(payloadJson, "arcKey");
        }
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

        if (TryExtractAnyUInt32Field(payloadJson, {"object_id", "objectId"}, objectId))
        {
            result = WorldDatabase.Query(
                "SELECT ObjectID, TemplateEntry, LiveGUIDLow, LiveGUID, ArcKey "
                "FROM wm_bridge_world_object "
                "WHERE ObjectID = {} AND ObjectType = 'creature' AND OwnerPlayerGUID = {} AND DespawnPolicy <> 'despawned' "
                "LIMIT 1",
                objectId,
                playerGuid);
        }
        else if (TryExtractAnyUInt32Field(payloadJson, {"live_guid_low", "liveGuidLow", "creature_guid_low", "creatureGuidLow"}, liveGuidLow))
        {
            result = WorldDatabase.Query(
                "SELECT ObjectID, TemplateEntry, LiveGUIDLow, LiveGUID, ArcKey "
                "FROM wm_bridge_world_object "
                "WHERE LiveGUIDLow = {} AND ObjectType = 'creature' AND OwnerPlayerGUID = {} AND DespawnPolicy <> 'despawned' "
                "ORDER BY ObjectID DESC LIMIT 1",
                liveGuidLow,
                playerGuid);
        }
        else if (!liveGuid.empty())
        {
            result = WorldDatabase.Query(
                "SELECT ObjectID, TemplateEntry, LiveGUIDLow, LiveGUID, ArcKey "
                "FROM wm_bridge_world_object "
                "WHERE LiveGUID = {} AND ObjectType = 'creature' AND OwnerPlayerGUID = {} AND DespawnPolicy <> 'despawned' "
                "ORDER BY ObjectID DESC LIMIT 1",
                SqlString(liveGuid),
                playerGuid);
        }
        else if (!arcKey.empty())
        {
            result = WorldDatabase.Query(
                "SELECT ObjectID, TemplateEntry, LiveGUIDLow, LiveGUID, ArcKey "
                "FROM wm_bridge_world_object "
                "WHERE ArcKey = {} AND ObjectType = 'creature' AND OwnerPlayerGUID = {} AND DespawnPolicy <> 'despawned' "
                "ORDER BY ObjectID DESC LIMIT 1",
                SqlString(arcKey),
                playerGuid);
        }
        else
        {
            errorText = "missing_creature_reference";
            return false;
        }

        if (!result)
        {
            errorText = "wm_owned_creature_not_found";
            return false;
        }

        Field* fields = result->Fetch();
        if (fields[1].IsNull() || fields[2].IsNull())
        {
            errorText = "wm_owned_creature_incomplete";
            return false;
        }

        ref.objectId = fields[0].Get<uint64>();
        ref.entry = fields[1].Get<uint32>();
        ref.liveGuidLow = fields[2].Get<uint32>();
        ref.liveGuid = fields[3].IsNull() ? "" : fields[3].Get<std::string>();
        ref.arcKey = fields[4].IsNull() ? "" : fields[4].Get<std::string>();
        return true;
    }

    Creature* ResolveOwnedCreature(Player* player, OwnedCreatureRef const& ref)
    {
        if (!player || ref.entry == 0 || ref.liveGuidLow == 0)
        {
            return nullptr;
        }

        ObjectGuid guid = ObjectGuid::Create<HighGuid::Unit>(ref.entry, static_cast<ObjectGuid::LowType>(ref.liveGuidLow));
        return ObjectAccessor::GetCreature(*player, guid);
    }

    Unit* ResolveCreatureCastTarget(Player* player, Creature* creature, std::string const& payloadJson, std::string& errorText)
    {
        std::string target = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "target"));
        if (target.empty())
        {
            target = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "target_kind"));
        }

        if (target.empty() || target == "player" || target == "owner")
        {
            return player;
        }

        if (target == "self" || target == "creature" || target == "caster")
        {
            return creature;
        }

        if (target == "selected" || target == "selection" || target == "target" || target == "player_target")
        {
            Unit* selected = ObjectAccessor::GetUnit(*player, player->GetTarget());
            if (!selected)
            {
                errorText = "target_not_found";
                return nullptr;
            }
            return selected;
        }

        errorText = "unsupported_target";
        return nullptr;
    }

    void MarkOwnedCreatureDespawned(OwnedCreatureRef const& ref, std::string const& reason)
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

    bool ExecuteCreatureSpawn(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
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

        uint32 durationMs = 30000;
        TryExtractAnyUInt32Field(payloadJson, {"duration_ms", "durationMs"}, durationMs);
        durationMs = std::clamp<uint32>(durationMs, 1000, 600000);
        float distance = 2.5f;
        float angleOffset = 0.0f;
        TryExtractAnyFloatField(payloadJson, {"distance", "spawn_distance", "spawnDistance"}, distance);
        TryExtractAnyFloatField(payloadJson, {"angle_offset", "angleOffset"}, angleOffset);
        distance = std::clamp<float>(distance, 0.5f, 30.0f);

        Position position;
        player->GetClosePoint(position.m_positionX, position.m_positionY, position.m_positionZ, 1.0f, distance, player->GetOrientation() + angleOffset);
        TempSummon* creature = player->SummonCreature(
            entry,
            position.m_positionX,
            position.m_positionY,
            position.m_positionZ,
            player->GetOrientation(),
            TEMPSUMMON_TIMED_DESPAWN,
            durationMs);
        if (!creature)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "creature_not_spawned", {}, {{"creature_entry", entry}}), "creature_not_spawned");
            return true;
        }

        creature->SetCreatorGUID(player->GetGUID());
        creature->SetOwnerGUID(player->GetGUID());
        creature->SetFaction(player->GetFaction());
        creature->SetPhaseMask(player->GetPhaseMask(), false);

        bool followPlayer = false;
        if (TryExtractAnyBoolField(payloadJson, {"follow_player", "followPlayer"}, followPlayer) && followPlayer)
        {
            float followDistance = distance;
            float followAngle = angleOffset;
            TryExtractAnyFloatField(payloadJson, {"follow_distance", "followDistance"}, followDistance);
            TryExtractAnyFloatField(payloadJson, {"follow_angle", "followAngle"}, followAngle);
            creature->GetMotionMaster()->MoveFollow(player, std::clamp<float>(followDistance, 0.5f, 30.0f), followAngle);
        }

        std::string arcKey = ExtractJsonStringField(payloadJson, "arc_key");
        if (arcKey.empty())
        {
            arcKey = ExtractJsonStringField(payloadJson, "arcKey");
        }
        std::string metadata = "{";
        bool firstField = true;
        JsonAppendNumberField(metadata, firstField, "request_id", static_cast<long long>(requestId));
        JsonAppendNumberField(metadata, firstField, "duration_ms", durationMs);
        JsonAppendBoolField(metadata, firstField, "follow_player", followPlayer);
        metadata += "}";

        // Spawn result payload needs the WM-owned ObjectID immediately, so the insert cannot be queued async.
        WorldDatabase.DirectExecute(
            "INSERT INTO wm_bridge_world_object ("
            "ObjectType, OwnerPlayerGUID, ArcKey, TemplateEntry, LiveGUID, LiveGUIDLow, MapID, PositionX, PositionY, PositionZ, Orientation, PhaseMask, DespawnPolicy, MetadataJSON"
            ") VALUES ('creature', {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, 'timed', {})",
            playerGuid,
            arcKey.empty() ? "NULL" : SqlString(arcKey),
            entry,
            SqlString(creature->GetGUID().ToString()),
            static_cast<uint32>(creature->GetGUID().GetCounter()),
            player->GetMapId(),
            creature->GetPositionX(),
            creature->GetPositionY(),
            creature->GetPositionZ(),
            creature->GetOrientation(),
            creature->GetPhaseMask(),
            SqlString(metadata));

        QueryResult objectIdResult = WorldDatabase.Query(
            "SELECT ObjectID FROM wm_bridge_world_object "
            "WHERE ObjectType = 'creature' AND OwnerPlayerGUID = {} AND LiveGUIDLow = {} "
            "ORDER BY ObjectID DESC LIMIT 1",
            playerGuid,
            static_cast<uint32>(creature->GetGUID().GetCounter()));
        uint64 objectId = objectIdResult ? objectIdResult->Fetch()[0].Get<uint64>() : 0;
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "creature_spawned",
                {{"live_guid", creature->GetGUID().ToString()}, {"arc_key", arcKey}},
                {
                    {"object_id", static_cast<long long>(objectId)},
                    {"creature_entry", entry},
                    {"live_guid_low", static_cast<long long>(creature->GetGUID().GetCounter())},
                    {"player_guid", playerGuid},
                }));
        return true;
    }

    bool ExecuteCreatureDespawn(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        OwnedCreatureRef ref;
        std::string errorText;
        if (!LoadOwnedCreatureRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        Creature* creature = ResolveOwnedCreature(player, ref);
        if (!creature)
        {
            MarkOwnedCreatureDespawned(ref, "creature_not_live");
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "creature_not_live", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "creature_not_live");
            return true;
        }

        creature->DespawnOrUnsummon();
        MarkOwnedCreatureDespawned(ref, "requested");
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "creature_despawned", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}, {"live_guid_low", ref.liveGuidLow}}));
        return true;
    }

    bool ExecuteCreatureSay(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        OwnedCreatureRef ref;
        std::string errorText;
        if (!LoadOwnedCreatureRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        Creature* creature = ResolveOwnedCreature(player, ref);
        if (!creature)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "creature_not_live", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "creature_not_live");
            return true;
        }

        std::string text = ExtractJsonStringField(payloadJson, "text");
        if (text.empty())
        {
            text = ExtractJsonStringField(payloadJson, "message");
        }
        if (text.empty())
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_text"), "missing_text");
            return true;
        }
        if (text.size() > 255)
        {
            text.resize(255);
        }

        creature->Say(text, LANG_UNIVERSAL, player);
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "creature_said", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}));
        return true;
    }

    bool ExecuteCreatureEmote(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        OwnedCreatureRef ref;
        std::string errorText;
        if (!LoadOwnedCreatureRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        Creature* creature = ResolveOwnedCreature(player, ref);
        if (!creature)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "creature_not_live", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "creature_not_live");
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
            creature->HandleEmoteCommand(emoteId);
        }
        if (!text.empty())
        {
            if (text.size() > 255)
            {
                text.resize(255);
            }
            creature->TextEmote(text, player);
        }

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "creature_emoted", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}, {"emote_id", emoteId}}));
        return true;
    }

    bool ExecuteCreatureCastSpell(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        OwnedCreatureRef ref;
        std::string errorText;
        if (!LoadOwnedCreatureRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        Creature* creature = ResolveOwnedCreature(player, ref);
        if (!creature)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "creature_not_live", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "creature_not_live");
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"spell_id", "spellId"}, spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }
        if (!sSpellMgr->GetSpellInfo(spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_spell", {}, {{"spell_id", spellId}}), "invalid_spell");
            return true;
        }

        std::string targetError;
        Unit* target = ResolveCreatureCastTarget(player, creature, payloadJson, targetError);
        if (!target)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, targetError), targetError);
            return true;
        }

        bool triggered = ResolveTriggeredCastFlag(payloadJson);
        creature->CastSpell(target, spellId, triggered);
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "creature_spell_cast",
                {{"arc_key", ref.arcKey}, {"target_guid", target->GetGUID().ToString()}},
                {{"object_id", static_cast<long long>(ref.objectId)}, {"spell_id", spellId}, {"player_guid", playerGuid}},
                {{"target_distance", creature->GetDistance(target)}}));
        return true;
    }

    bool ExecuteCreatureSetDisplayId(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        OwnedCreatureRef ref;
        std::string errorText;
        if (!LoadOwnedCreatureRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        Creature* creature = ResolveOwnedCreature(player, ref);
        if (!creature)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "creature_not_live", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "creature_not_live");
            return true;
        }

        bool restoreDisplay = false;
        if (TryExtractAnyBoolField(payloadJson, {"restore", "restore_display", "restoreDisplay"}, restoreDisplay) && restoreDisplay)
        {
            creature->RestoreDisplayId();
            CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "creature_display_restored", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}, {"display_id", creature->GetDisplayId()}}));
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
        creature->SetDisplayId(displayId);
        creature->SetNativeDisplayId(nativeDisplayId);

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "creature_display_set", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}, {"display_id", displayId}, {"native_display_id", nativeDisplayId}}));
        return true;
    }

    bool ExecuteCreatureSetScale(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        OwnedCreatureRef ref;
        std::string errorText;
        if (!LoadOwnedCreatureRef(playerGuid, payloadJson, ref, errorText))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, errorText), errorText);
            return true;
        }

        Creature* creature = ResolveOwnedCreature(player, ref);
        if (!creature)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "creature_not_live", {{"arc_key", ref.arcKey}}, {{"object_id", static_cast<long long>(ref.objectId)}}), "creature_not_live");
            return true;
        }

        float scale = 0.0f;
        if (!TryExtractAnyFloatField(payloadJson, {"scale", "object_scale", "objectScale"}, scale) || scale <= 0.0f)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_scale"), "missing_scale");
            return true;
        }

        scale = std::clamp<float>(scale, 0.10f, 5.0f);
        creature->SetObjectScale(scale);
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "creature_scale_set",
                {{"arc_key", ref.arcKey}},
                {{"object_id", static_cast<long long>(ref.objectId)}},
                {{"scale", scale}}));
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgeCreatureActions(ActionRegistry& registry)
    {
        registry.Register("creature_spawn", &ExecuteCreatureSpawn);
        registry.Register("creature_despawn", &ExecuteCreatureDespawn);
        registry.Register("creature_say", &ExecuteCreatureSay);
        registry.Register("creature_emote", &ExecuteCreatureEmote);
        registry.Register("creature_cast_spell", &ExecuteCreatureCastSpell);
        registry.Register("creature_set_display_id", &ExecuteCreatureSetDisplayId);
        registry.Register("creature_set_scale", &ExecuteCreatureSetScale);
    }
}
