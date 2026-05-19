#include "wm_bridge_action_queue.h"

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
    uint32 gActionPollTimer = 0;

    // Phase 0B: the local (buggy, signed-char, no \b/\f) EscapeForJson was
    // deleted. All call sites below now use the canonical WmBridge one
    // (wm_bridge_json.h) — correct UTF-8 + \b/\f handling. Documented
    // behavior change: result JSON no longer corrupts non-ASCII text.
    using WmBridge::EscapeForJson;
    using namespace WmBridge::detail;

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

    std::string BuildNearbyContextSnapshotJson(Player* player, uint64 actionRequestId, std::string const& contextKind, uint32 radius)
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

    bool ResolvePowerType(std::string const& payloadJson, Player* player, Powers& power, std::string& errorText)
    {
        power = player ? player->getPowerType() : POWER_MANA;

        uint32 numericPower = 0;
        if (TryExtractAnyUInt32Field(payloadJson, {"power_type", "powerType"}, numericPower))
        {
            if (numericPower >= MAX_POWERS)
            {
                errorText = "invalid_power_type";
                return false;
            }
            power = static_cast<Powers>(numericPower);
            return true;
        }

        std::string rawPower = ExtractJsonStringField(payloadJson, "power_type");
        if (rawPower.empty())
        {
            rawPower = ExtractJsonStringField(payloadJson, "powerType");
        }
        std::transform(rawPower.begin(), rawPower.end(), rawPower.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });

        if (rawPower.empty() || rawPower == "active" || rawPower == "current")
        {
            return true;
        }
        if (rawPower == "mana")
        {
            power = POWER_MANA;
            return true;
        }
        if (rawPower == "rage")
        {
            power = POWER_RAGE;
            return true;
        }
        if (rawPower == "focus")
        {
            power = POWER_FOCUS;
            return true;
        }
        if (rawPower == "energy")
        {
            power = POWER_ENERGY;
            return true;
        }
        if (rawPower == "runic_power" || rawPower == "runic")
        {
            power = POWER_RUNIC_POWER;
            return true;
        }

        errorText = "invalid_power_type";
        return false;
    }

    uint32 ResolveRestoreAmount(
        std::string const& payloadJson,
        std::initializer_list<char const*> amountKeys,
        std::initializer_list<char const*> percentKeys,
        uint32 maximum)
    {
        uint32 amount = 0;
        if (TryExtractAnyUInt32Field(payloadJson, amountKeys, amount))
        {
            return amount;
        }

        uint32 percent = 0;
        if (TryExtractAnyUInt32Field(payloadJson, percentKeys, percent))
        {
            percent = std::clamp<uint32>(percent, 0, 100);
            return static_cast<uint32>((static_cast<uint64>(maximum) * percent) / 100);
        }

        return 0;
    }

    struct OwnedCreatureRef
    {
        uint64 objectId = 0;
        uint32 entry = 0;
        uint32 liveGuidLow = 0;
        std::string liveGuid;
        std::string arcKey;
    };

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

    Unit* ResolvePlayerCastTarget(Player* player, std::string const& payloadJson, std::string& errorText)
    {
        std::string target = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "target"));
        if (target.empty())
        {
            target = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "target_kind"));
        }

        if (target.empty() || target == "self" || target == "player")
        {
            return player;
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

    bool ExecutePlayerApplyAura(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
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

        Aura* aura = player->AddAura(spellId, player);
        if (!aura)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "aura_not_applied", {}, {{"spell_id", spellId}, {"player_guid", playerGuid}}), "aura_not_applied");
            return true;
        }

        {
            std::string effectKind = ExtractJsonStringField(payloadJson, "effect_kind");
            uint32 durationSec = 0;
            TryExtractJsonUInt32Field(payloadJson, "duration_sec", durationSec);
            WmBridge::WMEffectRegistry::Instance().Register(
                playerGuid, playerGuid, /*targetIsPlayer=*/true,
                spellId, effectKind, "{}", durationSec);
        }

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "aura_applied", {}, {{"spell_id", spellId}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecutePlayerRemoveAura(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"spell_id", "spellId"}, spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }

        player->RemoveAurasDueToSpell(spellId);
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "aura_removed", {}, {{"spell_id", spellId}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecutePlayerRestoreHealthPower(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }
        if (!player->IsAlive())
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "player_dead", {}, {{"player_guid", playerGuid}}), "player_dead");
            return true;
        }

        Powers power = POWER_MANA;
        std::string powerError;
        if (!ResolvePowerType(payloadJson, player, power, powerError))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, powerError), powerError);
            return true;
        }

        uint32 healthRestore = ResolveRestoreAmount(payloadJson, {"health", "health_amount", "healthAmount"}, {"health_percent", "healthPercent"}, player->GetMaxHealth());
        uint32 powerRestore = ResolveRestoreAmount(payloadJson, {"power", "power_amount", "powerAmount", "mana", "mana_amount", "manaAmount"}, {"power_percent", "powerPercent", "mana_percent", "manaPercent"}, player->GetMaxPower(power));
        if (healthRestore == 0 && powerRestore == 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_restore_amount"), "missing_restore_amount");
            return true;
        }

        uint32 healthBefore = player->GetHealth();
        uint32 powerBefore = player->GetPower(power);
        uint32 healthAfter = std::min<uint32>(player->GetMaxHealth(), healthBefore + healthRestore);
        uint32 powerAfter = std::min<uint32>(player->GetMaxPower(power), powerBefore + powerRestore);
        player->SetHealth(healthAfter);
        player->SetPower(power, powerAfter);

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "health_power_restored",
                {},
                {
                    {"player_guid", playerGuid},
                    {"health_before", healthBefore},
                    {"health_after", healthAfter},
                    {"power_type", static_cast<long long>(power)},
                    {"power_before", powerBefore},
                    {"power_after", powerAfter},
                }));
        return true;
    }

    bool ExecutePlayerAddMoney(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        int32 copper = 0;
        if (!TryExtractAnyInt32Field(payloadJson, {"copper", "amount", "money"}, copper) || copper <= 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_positive_copper"), "missing_positive_copper");
            return true;
        }
        if (!player->ModifyMoney(copper))
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "money_not_added", {}, {{"copper", copper}, {"player_guid", playerGuid}}), "money_not_added");
            return true;
        }

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "money_added", {}, {{"copper", copper}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecutePlayerAddReputation(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 factionId = 0;
        int32 value = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"faction_id", "factionId"}, factionId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_faction_id"), "missing_faction_id");
            return true;
        }
        if (!TryExtractAnyInt32Field(payloadJson, {"value", "amount", "reputation"}, value) || value == 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_reputation_value"), "missing_reputation_value");
            return true;
        }

        FactionEntry const* faction = sFactionStore.LookupEntry(factionId);
        if (!faction)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_faction", {}, {{"faction_id", factionId}}), "invalid_faction");
            return true;
        }

        bool noSpillover = true;
        TryExtractAnyBoolField(payloadJson, {"no_spillover", "noSpillover"}, noSpillover);
        if (!player->GetReputationMgr().ModifyReputation(faction, static_cast<float>(value), noSpillover))
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "reputation_not_added", {}, {{"faction_id", factionId}, {"value", value}}), "reputation_not_added");
            return true;
        }

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "reputation_added", {}, {{"faction_id", factionId}, {"value", value}, {"player_guid", playerGuid}}));
        return true;
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

    bool ExecutePlayerCastSpell(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
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
        Unit* target = ResolvePlayerCastTarget(player, payloadJson, targetError);
        if (!target)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, targetError), targetError);
            return true;
        }

        bool triggered = ResolveTriggeredCastFlag(payloadJson);
        player->CastSpell(target, spellId, triggered);
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "spell_cast",
                {{"target_guid", target->GetGUID().ToString()}},
                {{"spell_id", spellId}, {"player_guid", playerGuid}},
                {{"target_distance", player->GetDistance(target)}}));
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

    // Phase 0C: previously-inline dispatch bodies extracted into the same
    // uniform handler signature as the existing Execute* functions so the
    // dispatch can become table-driven. Bodies are verbatim moves
    // (return; -> return true;), behavior-preserving.

    bool ExecuteDebugPing(uint64 requestId, uint32 /*playerGuid*/, std::string const& actionKind, std::string const& /*payloadJson*/)
    {
        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "pong"));
        return true;
    }

    bool ExecuteDebugEcho(uint64 requestId, uint32 /*playerGuid*/, std::string const& actionKind, std::string const& payloadJson)
    {
        std::string result = "{\"ok\":true,\"action_kind\":\"debug_echo\",\"payload_json\":\"" + EscapeForJson(payloadJson) + "\"}";
        CompleteAction(requestId, "done", actionKind, result);
        return true;
    }

    bool ExecuteDebugFail(uint64 requestId, uint32 /*playerGuid*/, std::string const& actionKind, std::string const& /*payloadJson*/)
    {
        CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "debug_fail_requested"), "debug_fail_requested");
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

    bool ExecutePlayerLearnSpell(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (!player)
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractJsonUInt32Field(payloadJson, "spell_id", spellId) &&
            !TryExtractJsonUInt32Field(payloadJson, "spellId", spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }

        if (!sSpellMgr->GetSpellInfo(spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "invalid_spell"), "invalid_spell");
            return true;
        }

        if (player->HasSpell(spellId))
        {
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "already_known"));
            return true;
        }

        player->learnSpell(spellId, false, false);
        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "spell_learned"));
        return true;
    }

    bool ExecutePlayerUnlearnSpell(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (!player)
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractJsonUInt32Field(payloadJson, "spell_id", spellId) &&
            !TryExtractJsonUInt32Field(payloadJson, "spellId", spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }

        if (!player->HasSpell(spellId))
        {
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "already_absent"));
            return true;
        }

        player->removeSpell(spellId, SPEC_MASK_ALL, false);
        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "spell_unlearned"));
        return true;
    }

    WmBridge::ActionRegistry const& GetActionRegistry()
    {
        static WmBridge::ActionRegistry registry = []
        {
            WmBridge::ActionRegistry r;
            r.Register("debug_ping", &ExecuteDebugPing);
            r.Register("debug_echo", &ExecuteDebugEcho);
            r.Register("debug_fail", &ExecuteDebugFail);
            r.Register("context_snapshot_request", &ExecuteContextSnapshotRequest);
            r.Register("world_announce_to_player", &ExecuteWorldAnnounceToPlayer);
            r.Register("quest_add", &ExecuteQuestAdd);
            r.Register("quest_remove", &ExecuteQuestRemove);
            r.Register("player_apply_aura", &ExecutePlayerApplyAura);
            r.Register("player_cast_spell", &ExecutePlayerCastSpell);
            r.Register("player_set_display_id", &ExecutePlayerSetDisplayId);
            r.Register("player_remove_aura", &ExecutePlayerRemoveAura);
            r.Register("player_restore_health_power", &ExecutePlayerRestoreHealthPower);
            r.Register("player_add_item", &ExecutePlayerAddItem);
            r.Register("player_remove_item", &ExecutePlayerRemoveItem);
            r.Register("player_random_enchant_item", &ExecutePlayerRandomEnchantItem);
            r.Register("player_add_money", &ExecutePlayerAddMoney);
            r.Register("player_add_reputation", &ExecutePlayerAddReputation);
            r.Register("creature_spawn", &ExecuteCreatureSpawn);
            r.Register("creature_despawn", &ExecuteCreatureDespawn);
            r.Register("creature_say", &ExecuteCreatureSay);
            r.Register("creature_emote", &ExecuteCreatureEmote);
            r.Register("creature_cast_spell", &ExecuteCreatureCastSpell);
            r.Register("creature_set_display_id", &ExecuteCreatureSetDisplayId);
            r.Register("creature_set_scale", &ExecuteCreatureSetScale);
            r.Register("player_learn_spell", &ExecutePlayerLearnSpell);
            r.Register("player_unlearn_spell", &ExecutePlayerUnlearnSpell);
            return r;
        }();

        return registry;
    }

    void ExecuteClaimedAction(
        uint64 requestId,
        uint32 playerGuid,
        std::string const& actionKind,
        std::string const& payloadJson,
        std::string const& riskLevel,
        std::string const& createdBy)
    {
        if (!WmBridge::IsPlayerGuidAllowed(playerGuid))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "player_not_scoped"), "player_not_scoped");
            return;
        }

        std::string rejectReason;
        if (!ActionPolicyAllows(requestId, playerGuid, actionKind, riskLevel, createdBy, rejectReason))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, rejectReason), rejectReason);
            return;
        }

        // Phase 0C: table-driven dispatch. Pre-checks above are unchanged;
        // the not-implemented fallback below is the same. Only the
        // selection mechanism changed (26-branch if-chain -> O(1) lookup).
        if (WmBridge::ActionHandler handler = GetActionRegistry().Find(actionKind))
        {
            handler(requestId, playerGuid, actionKind, payloadJson);
            return;
        }

        CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "not_implemented"), "not_implemented");
    }

    void RecoverExpiredClaims()
    {
        WorldDatabase.Execute(
            "UPDATE wm_bridge_action_request "
            "SET Status = 'pending', ClaimedAt = NULL, ClaimExpiresAt = NULL, ErrorText = 'claim_expired_requeued', UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE Status = 'claimed' AND ClaimExpiresAt IS NOT NULL AND ClaimExpiresAt <= NOW() AND AttemptCount < MaxAttempts");

        WorldDatabase.Execute(
            "UPDATE wm_bridge_action_request "
            "SET Status = 'failed', ProcessedAt = NOW(), ResultJSON = {}, ErrorText = 'claim_expired_max_attempts', UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE Status = 'claimed' AND ClaimExpiresAt IS NOT NULL AND ClaimExpiresAt <= NOW() AND AttemptCount >= MaxAttempts",
            SqlString(ResultJson("failed", "action_queue", "claim_expired_max_attempts")));
    }

    void ExpireBlockedSequenceRows()
    {
        WorldDatabase.Execute(
            "UPDATE wm_bridge_action_request req "
            "JOIN wm_bridge_action_request prior "
            "ON prior.SequenceID = req.SequenceID "
            "AND prior.SequenceOrder < req.SequenceOrder "
            "AND prior.Status IN ('failed', 'rejected', 'expired') "
            "SET req.Status = 'failed', req.ProcessedAt = NOW(), req.ResultJSON = {}, req.ErrorText = 'sequence_prior_failed', req.UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE req.Status = 'pending' AND req.WaitForPrior <> 0 AND req.SequenceID IS NOT NULL",
            SqlString(ResultJson("failed", "action_queue", "sequence_prior_failed")));
    }
}

namespace WmBridge
{
    void PollActionQueue(uint32 diff)
    {
        BridgeConfig const& config = GetConfig();
        if (!config.enabled || !config.actionQueueEnabled)
        {
            return;
        }

        if (gActionPollTimer > diff)
        {
            gActionPollTimer -= diff;
            return;
        }

        gActionPollTimer = config.actionPollIntervalMs;
        WorldDatabase.Execute(
            "UPDATE wm_bridge_action_request "
            "SET Status = 'expired', ProcessedAt = NOW(), ErrorText = 'expired', UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE Status = 'pending' AND ExpiresAt IS NOT NULL AND ExpiresAt <= NOW()");
        RecoverExpiredClaims();
        ExpireBlockedSequenceRows();

        QueryResult result = WorldDatabase.Query(
            "SELECT RequestID, PlayerGUID, ActionKind, PayloadJSON, RiskLevel, CreatedBy "
            "FROM wm_bridge_action_request req "
            "WHERE req.Status = 'pending' AND (req.ExpiresAt IS NULL OR req.ExpiresAt > NOW()) "
            "AND (req.WaitForPrior = 0 OR req.SequenceID IS NULL OR NOT EXISTS ("
            "SELECT 1 FROM wm_bridge_action_request prior "
            "WHERE prior.SequenceID = req.SequenceID "
            "AND prior.SequenceOrder < req.SequenceOrder "
            "AND prior.Status <> 'done')) "
            "ORDER BY req.Priority ASC, COALESCE(req.SequenceID, ''), req.SequenceOrder ASC, req.RequestID ASC LIMIT 1");

        if (!result)
        {
            return;
        }

        Field* fields = result->Fetch();
        uint64 requestId = fields[0].Get<uint64>();
        uint32 playerGuid = fields[1].Get<uint32>();
        std::string actionKind = fields[2].Get<std::string>();
        std::string payloadJson = fields[3].Get<std::string>();
        std::string riskLevel = fields[4].Get<std::string>();
        std::string createdBy = fields[5].Get<std::string>();

        WorldDatabase.Execute(
            "UPDATE wm_bridge_action_request "
            "SET Status = 'claimed', ClaimedAt = NOW(), "
            "ClaimExpiresAt = DATE_ADD(NOW(), INTERVAL {} MICROSECOND), "
            "AttemptCount = AttemptCount + 1, UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE RequestID = {} AND Status = 'pending'",
            std::max<uint32>(config.actionPollIntervalMs * 3, 5000) * 1000,
            requestId);

        ExecuteClaimedAction(requestId, playerGuid, actionKind, payloadJson, riskLevel, createdBy);
    }
}
