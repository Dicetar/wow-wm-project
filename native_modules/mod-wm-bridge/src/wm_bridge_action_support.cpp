#include "wm_bridge_action_support.h"

#include "DatabaseEnv.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "QueryResult.h"
#include "wm_bridge_json.h"

#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>

// Phase 0D: bodies moved verbatim from wm_bridge_action_queue.cpp's
// anonymous namespace. No behavior change — same escaping, same SQL,
// same result-JSON shapes. Only the namespace (internal -> WmBridge::detail)
// changed so the per-domain handler files can share these.

namespace WmBridge
{
    namespace detail
    {
        std::string EscapeForSql(std::string value)
        {
            WorldDatabase.EscapeString(value);
            return value;
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

        bool TryExtractJsonInt32Field(std::string const& json, std::string const& key, int32& value)
        {
            std::string rawValue = ExtractJsonStringField(json, key);
            if (rawValue.empty())
            {
                return false;
            }

            try
            {
                size_t consumed = 0;
                long parsed = std::stol(rawValue, &consumed, 10);
                if (consumed != rawValue.size() || parsed < std::numeric_limits<int32>::min() || parsed > std::numeric_limits<int32>::max())
                {
                    return false;
                }

                value = static_cast<int32>(parsed);
                return true;
            }
            catch (std::exception const&)
            {
                return false;
            }
        }

        bool TryExtractJsonFloatField(std::string const& json, std::string const& key, float& value)
        {
            std::string rawValue = ExtractJsonStringField(json, key);
            if (rawValue.empty())
            {
                return false;
            }

            try
            {
                size_t consumed = 0;
                float parsed = std::stof(rawValue, &consumed);
                if (consumed != rawValue.size())
                {
                    return false;
                }

                value = parsed;
                return true;
            }
            catch (std::exception const&)
            {
                return false;
            }
        }

        bool TryExtractJsonBoolField(std::string const& json, std::string const& key, bool& value)
        {
            std::string rawValue = ExtractJsonStringField(json, key);
            std::transform(rawValue.begin(), rawValue.end(), rawValue.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
            if (rawValue == "1" || rawValue == "true" || rawValue == "yes" || rawValue == "on")
            {
                value = true;
                return true;
            }
            if (rawValue == "0" || rawValue == "false" || rawValue == "no" || rawValue == "off")
            {
                value = false;
                return true;
            }
            return false;
        }

        bool TryExtractAnyUInt32Field(std::string const& json, std::initializer_list<char const*> keys, uint32& value)
        {
            for (char const* key : keys)
            {
                if (TryExtractJsonUInt32Field(json, key, value))
                {
                    return true;
                }
            }
            return false;
        }

        bool TryExtractAnyInt32Field(std::string const& json, std::initializer_list<char const*> keys, int32& value)
        {
            for (char const* key : keys)
            {
                if (TryExtractJsonInt32Field(json, key, value))
                {
                    return true;
                }
            }
            return false;
        }

        bool TryExtractAnyFloatField(std::string const& json, std::initializer_list<char const*> keys, float& value)
        {
            for (char const* key : keys)
            {
                if (TryExtractJsonFloatField(json, key, value))
                {
                    return true;
                }
            }
            return false;
        }

        bool TryExtractAnyBoolField(std::string const& json, std::initializer_list<char const*> keys, bool& value)
        {
            for (char const* key : keys)
            {
                if (TryExtractJsonBoolField(json, key, value))
                {
                    return true;
                }
            }
            return false;
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

        std::string ResultJson(std::string const& status, std::string const& actionKind, std::string const& message)
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

        std::string ActionResultJson(std::string const& status, std::string const& actionKind, std::string const& message)
        {
            std::string json = "{";
            bool firstField = true;
            JsonAppendBoolField(json, firstField, "ok", status == "done");
            JsonAppendStringField(json, firstField, "action_kind", actionKind);
            JsonAppendStringField(json, firstField, "status", status);
            if (!message.empty())
            {
                JsonAppendStringField(json, firstField, "message", message);
            }
            json += "}";
            return json;
        }

        std::string ActionResultJson(
            std::string const& status,
            std::string const& actionKind,
            std::string const& message,
            std::initializer_list<std::pair<std::string, std::string>> stringFields,
            std::initializer_list<std::pair<std::string, long long>> numberFields)
        {
            std::string json = "{";
            bool firstField = true;
            JsonAppendBoolField(json, firstField, "ok", status == "done");
            JsonAppendStringField(json, firstField, "action_kind", actionKind);
            JsonAppendStringField(json, firstField, "status", status);
            if (!message.empty())
            {
                JsonAppendStringField(json, firstField, "message", message);
            }
            for (auto const& field : stringFields)
            {
                JsonAppendStringField(json, firstField, field.first, field.second);
            }
            for (auto const& field : numberFields)
            {
                JsonAppendNumberField(json, firstField, field.first, field.second);
            }
            json += "}";
            return json;
        }

        std::string ActionResultJson(
            std::string const& status,
            std::string const& actionKind,
            std::string const& message,
            std::initializer_list<std::pair<std::string, std::string>> stringFields,
            std::initializer_list<std::pair<std::string, long long>> numberFields,
            std::initializer_list<std::pair<std::string, float>> floatFields)
        {
            std::string json = "{";
            bool firstField = true;
            JsonAppendBoolField(json, firstField, "ok", status == "done");
            JsonAppendStringField(json, firstField, "action_kind", actionKind);
            JsonAppendStringField(json, firstField, "status", status);
            if (!message.empty())
            {
                JsonAppendStringField(json, firstField, "message", message);
            }
            for (auto const& field : stringFields)
            {
                JsonAppendStringField(json, firstField, field.first, field.second);
            }
            for (auto const& field : numberFields)
            {
                JsonAppendNumberField(json, firstField, field.first, field.second);
            }
            for (auto const& field : floatFields)
            {
                JsonAppendFloatField(json, firstField, field.first, field.second);
            }
            json += "}";
            return json;
        }

        void CompleteAction(uint64 requestId, std::string const& status, std::string const& actionKind, std::string const& resultJson, std::string const& errorText)
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

        bool ResolveScopedOnlinePlayer(
            uint64 requestId,
            uint32 playerGuid,
            std::string const& actionKind,
            std::string const& payloadJson,
            Player*& player)
        {
            uint32 targetPlayerGuid = playerGuid;
            uint32 explicitTargetGuid = 0;
            if (TryExtractAnyUInt32Field(payloadJson, {"target_player_guid", "targetPlayerGuid", "player_guid", "playerGuid"}, explicitTargetGuid))
            {
                targetPlayerGuid = explicitTargetGuid;
            }

            if (targetPlayerGuid != playerGuid)
            {
                CompleteAction(
                    requestId,
                    "rejected",
                    actionKind,
                    ActionResultJson(
                        "rejected",
                        actionKind,
                        "target_player_must_match_scoped_player",
                        {},
                        {{"player_guid", playerGuid}, {"target_player_guid", targetPlayerGuid}}),
                    "target_player_must_match_scoped_player");
                return false;
            }

            player = ObjectAccessor::FindPlayerByLowGUID(targetPlayerGuid);
            if (!player)
            {
                CompleteAction(
                    requestId,
                    "failed",
                    actionKind,
                    ActionResultJson("failed", actionKind, "player_not_online", {}, {{"player_guid", targetPlayerGuid}}),
                    "player_not_online");
                return false;
            }

            return true;
        }

        std::string NormalizedJsonToken(std::string value)
        {
            std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
            return value;
        }

        bool ResolveTriggeredCastFlag(std::string const& payloadJson)
        {
            bool triggered = true;
            TryExtractAnyBoolField(payloadJson, {"triggered", "is_triggered", "isTriggered"}, triggered);
            return triggered;
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
    }
}
