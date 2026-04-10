#include "wm_bridge_action_queue.h"

#include "DatabaseEnv.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "QueryResult.h"
#include "WorldSession.h"
#include "wm_bridge_common.h"

#include <algorithm>
#include <cctype>
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
            WorldDatabase.Execute(
                "INSERT INTO wm_bridge_context_request (PlayerGUID, ContextKind, Radius, Status, RequestedBy, MetadataJSON) "
                "VALUES ({}, 'action_request', 40, 'pending', 'wm_bridge_action_queue', {})",
                playerGuid,
                SqlString(payloadJson));
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "context_request_queued"));
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
