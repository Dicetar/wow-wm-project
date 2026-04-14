#include "wm_bridge_action_queue.h"

#include "DatabaseEnv.h"
#include "Cell.h"
#include "CellImpl.h"
#include "Creature.h"
#include "GameObject.h"
#include "GridNotifiers.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QueryResult.h"
#include "SpellMgr.h"
#include "WorldSession.h"
#include "wm_bridge_common.h"

#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <limits>
#include <list>
#include <sstream>
#include <string>

namespace
{
    uint32 gActionPollTimer = 0;

    std::string EscapeForSql(std::string value)
    {
        WorldDatabase.EscapeString(value);
        return value;
    }

    std::string EscapeForJson(std::string const& value)
    {
        std::string escaped;
        escaped.reserve(value.size());
        for (char ch : value)
        {
            switch (ch)
            {
                case '\\':
                    escaped += "\\\\";
                    break;
                case '"':
                    escaped += "\\\"";
                    break;
                case '\n':
                    escaped += "\\n";
                    break;
                case '\r':
                    escaped += "\\r";
                    break;
                case '\t':
                    escaped += "\\t";
                    break;
                default:
                    escaped += ch < 0x20 ? ' ' : ch;
                    break;
            }
        }

        return escaped;
    }

    std::string SqlString(std::string const& value)
    {
        return "'" + EscapeForSql(value) + "'";
    }

    std::string ExtractJsonStringField(std::string const& json, std::string const& key)
    {
        std::string const quotedKey = "\"" + key + "\"";
        size_t keyPos = json.find(quotedKey);
        if (keyPos == std::string::npos)
        {
            return "";
        }

        size_t colonPos = json.find(':', keyPos + quotedKey.size());
        if (colonPos == std::string::npos)
        {
            return "";
        }

        size_t valuePos = colonPos + 1;
        while (valuePos < json.size() && std::isspace(static_cast<unsigned char>(json[valuePos])))
        {
            ++valuePos;
        }

        if (valuePos >= json.size())
        {
            return "";
        }

        if (json[valuePos] != '"')
        {
            size_t endPos = json.find_first_of(",}", valuePos);
            std::string value = json.substr(valuePos, endPos == std::string::npos ? std::string::npos : endPos - valuePos);
            while (!value.empty() && std::isspace(static_cast<unsigned char>(value.back())))
            {
                value.pop_back();
            }
            return value;
        }

        std::string value;
        bool escaped = false;
        for (size_t index = valuePos + 1; index < json.size(); ++index)
        {
            char ch = json[index];
            if (escaped)
            {
                switch (ch)
                {
                    case 'n':
                        value += '\n';
                        break;
                    case 'r':
                        value += '\r';
                        break;
                    case 't':
                        value += '\t';
                        break;
                    default:
                        value += ch;
                        break;
                }
                escaped = false;
                continue;
            }

            if (ch == '\\')
            {
                escaped = true;
                continue;
            }

            if (ch == '"')
            {
                break;
            }

            value += ch;
        }

        return value;
    }

    bool TryExtractJsonUInt32Field(std::string const& json, std::string const& key, uint32& value)
    {
        std::string rawValue = ExtractJsonStringField(json, key);
        if (rawValue.empty())
        {
            return false;
        }

        try
        {
            size_t consumed = 0;
            unsigned long parsed = std::stoul(rawValue, &consumed, 10);
            if (consumed != rawValue.size() || parsed > std::numeric_limits<uint32>::max())
            {
                return false;
            }

            value = static_cast<uint32>(parsed);
            return true;
        }
        catch (std::exception const&)
        {
            return false;
        }
    }

    int RiskRank(std::string risk)
    {
        std::transform(risk.begin(), risk.end(), risk.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
        if (risk == "low")
        {
            return 0;
        }
        if (risk == "medium")
        {
            return 1;
        }
        if (risk == "high")
        {
            return 2;
        }
        return 99;
    }

    std::string ResultJson(std::string const& status, std::string const& actionKind, std::string const& message = "")
    {
        std::string result = "{\"ok\":";
        result += status == "done" ? "true" : "false";
        result += ",\"action_kind\":\"" + EscapeForJson(actionKind) + "\"";
        if (!message.empty())
        {
            result += ",\"message\":\"" + EscapeForJson(message) + "\"";
        }
        result += "}";
        return result;
    }

    std::string FloatString(float value)
    {
        std::ostringstream out;
        out << std::fixed << std::setprecision(3) << value;
        return out.str();
    }

    void JsonAppendComma(std::string& json, bool& firstField)
    {
        if (!firstField)
        {
            json += ",";
        }

        firstField = false;
    }

    void JsonAppendStringField(std::string& json, bool& firstField, std::string const& key, std::string const& value)
    {
        JsonAppendComma(json, firstField);
        json += "\"" + EscapeForJson(key) + "\":\"" + EscapeForJson(value) + "\"";
    }

    void JsonAppendNumberField(std::string& json, bool& firstField, std::string const& key, long long value)
    {
        JsonAppendComma(json, firstField);
        json += "\"" + EscapeForJson(key) + "\":" + std::to_string(value);
    }

    void JsonAppendFloatField(std::string& json, bool& firstField, std::string const& key, float value)
    {
        JsonAppendComma(json, firstField);
        json += "\"" + EscapeForJson(key) + "\":" + FloatString(value);
    }

    void JsonAppendBoolField(std::string& json, bool& firstField, std::string const& key, bool value)
    {
        JsonAppendComma(json, firstField);
        json += "\"" + EscapeForJson(key) + "\":" + (value ? "true" : "false");
    }

    void JsonAppendRawField(std::string& json, bool& firstField, std::string const& key, std::string const& rawJson)
    {
        JsonAppendComma(json, firstField);
        json += "\"" + EscapeForJson(key) + "\":" + rawJson;
    }

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

    void CompleteAction(uint64 requestId, std::string const& status, std::string const& actionKind, std::string const& resultJson, std::string const& errorText = "")
    {
        WorldDatabase.Execute(
            "UPDATE wm_bridge_action_request "
            "SET Status = {}, ClaimExpiresAt = NULL, ProcessedAt = NOW(), ResultJSON = {}, ErrorText = {}, UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE RequestID = {}",
            SqlString(status),
            SqlString(resultJson),
            errorText.empty() ? "NULL" : SqlString(errorText),
            requestId);

        WorldDatabase.Execute(
            "INSERT INTO wm_bridge_runtime_status (StatusKey, StatusValue, PayloadJSON) VALUES "
            "('action_queue.last_processed', {}, {}) "
            "ON DUPLICATE KEY UPDATE StatusValue = VALUES(StatusValue), PayloadJSON = VALUES(PayloadJSON), UpdatedAt = CURRENT_TIMESTAMP",
            SqlString(status),
            SqlString(ResultJson(status, actionKind, errorText)));
    }

    bool ActionPolicyAllows(
        uint64 requestId,
        uint32 playerGuid,
        std::string const& actionKind,
        std::string const& riskLevel,
        std::string const& createdBy,
        std::string& rejectReason)
    {
        QueryResult result = WorldDatabase.Query(
            "SELECT Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly FROM wm_bridge_action_policy "
            "WHERE ActionKind = {} AND Profile = 'default' LIMIT 1",
            SqlString(actionKind));

        if (!result)
        {
            rejectReason = "missing_action_policy";
            return false;
        }

        Field* fields = result->Fetch();
        if (fields[0].Get<uint8>() == 0)
        {
            rejectReason = "action_policy_disabled";
            return false;
        }

        std::string maxRisk = fields[1].Get<std::string>();
        if (RiskRank(riskLevel) > RiskRank(maxRisk))
        {
            rejectReason = "risk_exceeds_policy";
            return false;
        }

        std::string normalizedCreatedBy = createdBy;
        std::transform(normalizedCreatedBy.begin(), normalizedCreatedBy.end(), normalizedCreatedBy.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
        if (fields[4].Get<uint8>() != 0 && normalizedCreatedBy.find("llm") != std::string::npos)
        {
            rejectReason = "admin_only_action";
            return false;
        }

        if (!fields[2].IsNull())
        {
            uint32 cooldownMs = fields[2].Get<uint32>();
            if (cooldownMs > 0)
            {
                QueryResult cooldownResult = WorldDatabase.Query(
                    "SELECT COUNT(*) FROM wm_bridge_action_request "
                    "WHERE RequestID <> {} AND PlayerGUID = {} AND ActionKind = {} AND Status = 'done' "
                    "AND ProcessedAt IS NOT NULL AND TIMESTAMPDIFF(MICROSECOND, ProcessedAt, NOW()) < {}",
                    requestId,
                    playerGuid,
                    SqlString(actionKind),
                    cooldownMs * 1000);
                if (cooldownResult && cooldownResult->Fetch()[0].Get<uint64>() > 0)
                {
                    rejectReason = "action_policy_cooldown";
                    return false;
                }
            }
        }

        if (!fields[3].IsNull())
        {
            uint32 burstLimit = fields[3].Get<uint32>();
            if (burstLimit > 0)
            {
                QueryResult burstResult = WorldDatabase.Query(
                    "SELECT COUNT(*) FROM wm_bridge_action_request "
                    "WHERE PlayerGUID = {} AND ActionKind = {} AND Status IN ('pending', 'claimed', 'done') "
                    "AND CreatedAt >= DATE_SUB(NOW(), INTERVAL 60 SECOND)",
                    playerGuid,
                    SqlString(actionKind));
                if (burstResult && burstResult->Fetch()[0].Get<uint64>() > burstLimit)
                {
                    rejectReason = "action_policy_burst_limit";
                    return false;
                }
            }
        }

        return true;
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

        if (actionKind == "debug_ping")
        {
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "pong"));
            return;
        }

        if (actionKind == "debug_echo")
        {
            std::string result = "{\"ok\":true,\"action_kind\":\"debug_echo\",\"payload_json\":\"" + EscapeForJson(payloadJson) + "\"}";
            CompleteAction(requestId, "done", actionKind, result);
            return;
        }

        if (actionKind == "debug_fail")
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "debug_fail_requested"), "debug_fail_requested");
            return;
        }

        if (actionKind == "context_snapshot_request")
        {
            std::string errorText;
            if (!WriteContextSnapshot(requestId, playerGuid, payloadJson, errorText))
            {
                CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, errorText), errorText);
                return;
            }

            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "context_snapshot_written"));
            return;
        }

        if (actionKind == "world_announce_to_player")
        {
            Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
            if (!player || !player->GetSession())
            {
                CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
                return;
            }

            std::string message = ExtractJsonStringField(payloadJson, "message");
            if (message.empty())
            {
                message = ExtractJsonStringField(payloadJson, "text");
            }
            if (message.empty())
            {
                CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_message"), "missing_message");
                return;
            }

            player->GetSession()->SendAreaTriggerMessage(message);
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "message_sent"));
            return;
        }

        if (actionKind == "quest_add")
        {
            Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
            if (!player)
            {
                CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
                return;
            }

            uint32 questId = 0;
            if (!TryExtractJsonUInt32Field(payloadJson, "quest_id", questId) &&
                !TryExtractJsonUInt32Field(payloadJson, "questId", questId))
            {
                CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_quest_id"), "missing_quest_id");
                return;
            }

            Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
            if (!quest)
            {
                CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "invalid_quest"), "invalid_quest");
                return;
            }

            if (!player->CanTakeQuest(quest, false))
            {
                CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "cannot_take_quest"), "cannot_take_quest");
                return;
            }

            if (!player->CanAddQuest(quest, false))
            {
                CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "cannot_add_quest"), "cannot_add_quest");
                return;
            }

            player->AddQuestAndCheckCompletion(quest, nullptr);
            EmitQuestGrantedEvent(player, quest);
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "quest_added"));
            return;
        }

        if (actionKind == "player_learn_spell")
        {
            Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
            if (!player)
            {
                CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
                return;
            }

            uint32 spellId = 0;
            if (!TryExtractJsonUInt32Field(payloadJson, "spell_id", spellId) &&
                !TryExtractJsonUInt32Field(payloadJson, "spellId", spellId))
            {
                CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
                return;
            }

            if (!sSpellMgr->GetSpellInfo(spellId))
            {
                CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "invalid_spell"), "invalid_spell");
                return;
            }

            if (player->HasSpell(spellId))
            {
                CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "already_known"));
                return;
            }

            player->learnSpell(spellId, false, false);
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "spell_learned"));
            return;
        }

        if (actionKind == "player_unlearn_spell")
        {
            Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
            if (!player)
            {
                CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
                return;
            }

            uint32 spellId = 0;
            if (!TryExtractJsonUInt32Field(payloadJson, "spell_id", spellId) &&
                !TryExtractJsonUInt32Field(payloadJson, "spellId", spellId))
            {
                CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
                return;
            }

            if (!player->HasSpell(spellId))
            {
                CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "already_absent"));
                return;
            }

            player->removeSpell(spellId, SPEC_MASK_ALL, false);
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "spell_unlearned"));
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
