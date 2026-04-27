#include "wm_bridge_common.h"

#include "Config.h"
#include "DBCStores.h"
#include "DatabaseEnv.h"
#include "Player.h"

#include <algorithm>
#include <cctype>
#include <limits>
#include <sstream>
#include <utility>

namespace
{
    WmBridge::BridgeConfig gBridgeConfig;
    uint32 gDbControlRefreshTimer = 0;

    std::string EscapeForSql(std::string value)
    {
        WorldDatabase.EscapeString(value);
        return value;
    }

    std::string Trim(std::string value)
    {
        auto isSpace = [](unsigned char ch) { return std::isspace(ch) != 0; };
        value.erase(value.begin(), std::find_if(value.begin(), value.end(), [isSpace](unsigned char ch) { return !isSpace(ch); }));
        value.erase(std::find_if(value.rbegin(), value.rend(), [isSpace](unsigned char ch) { return !isSpace(ch); }).base(), value.end());
        return value;
    }

    std::unordered_set<uint32> ParsePlayerGuidAllowList(std::string const& rawValue, bool& allowAllPlayers)
    {
        std::unordered_set<uint32> result;
        allowAllPlayers = false;

        std::stringstream stream(rawValue);
        std::string token;
        while (std::getline(stream, token, ','))
        {
            token = Trim(token);
            if (token.empty())
            {
                continue;
            }

            if (token == "*")
            {
                allowAllPlayers = true;
                result.clear();
                return result;
            }

            try
            {
                unsigned long parsed = std::stoul(token);
                if (parsed <= std::numeric_limits<uint32>::max())
                {
                    result.insert(static_cast<uint32>(parsed));
                }
            }
            catch (...)
            {
                // Keep config reload tolerant: a bad token should not prevent boot.
            }
        }

        return result;
    }

    std::string SqlString(std::string const& value)
    {
        return "'" + EscapeForSql(value) + "'";
    }

    std::string SqlStringOrNull(std::optional<std::string> const& value)
    {
        if (!value.has_value() || value->empty())
        {
            return "NULL";
        }

        return SqlString(*value);
    }

    std::string SqlUIntOrNull(std::optional<uint32> value)
    {
        if (!value.has_value())
        {
            return "NULL";
        }

        return std::to_string(*value);
    }

    std::string EscapeForJson(std::string const& value)
    {
        std::ostringstream out;
        for (unsigned char ch : value)
        {
            switch (ch)
            {
                case '\\':
                    out << "\\\\";
                    break;
                case '"':
                    out << "\\\"";
                    break;
                case '\b':
                    out << "\\b";
                    break;
                case '\f':
                    out << "\\f";
                    break;
                case '\n':
                    out << "\\n";
                    break;
                case '\r':
                    out << "\\r";
                    break;
                case '\t':
                    out << "\\t";
                    break;
                default:
                    if (ch < 0x20)
                    {
                        out << ' ';
                    }
                    else
                    {
                        out << static_cast<char>(ch);
                    }
                    break;
            }
        }

        return out.str();
    }
}

namespace WmBridge
{
    BridgeConfig const& GetConfig()
    {
        return gBridgeConfig;
    }

    void LoadConfig()
    {
        gBridgeConfig.enabled = sConfigMgr->GetOption<bool>("WmBridge.Enable", true);
        gBridgeConfig.emitKill = sConfigMgr->GetOption<bool>("WmBridge.Emit.Kill", true);
        gBridgeConfig.emitQuest = sConfigMgr->GetOption<bool>("WmBridge.Emit.Quest", true);
        gBridgeConfig.emitLoot = sConfigMgr->GetOption<bool>("WmBridge.Emit.Loot", true);
        gBridgeConfig.emitGossip = sConfigMgr->GetOption<bool>("WmBridge.Emit.Gossip", true);
        gBridgeConfig.emitArea = sConfigMgr->GetOption<bool>("WmBridge.Emit.Area", true);
        gBridgeConfig.dbControlEnabled = sConfigMgr->GetOption<bool>("WmBridge.DbControl.Enable", false);
        gBridgeConfig.dbControlRefreshIntervalMs = sConfigMgr->GetOption<uint32>("WmBridge.DbControl.RefreshIntervalMS", 5000);
        gBridgeConfig.actionQueueEnabled = sConfigMgr->GetOption<bool>("WmBridge.ActionQueue.Enable", false);
        gBridgeConfig.actionPollIntervalMs = sConfigMgr->GetOption<uint32>("WmBridge.ActionQueue.PollIntervalMS", 1000);
        gBridgeConfig.aoeLootEnabled = sConfigMgr->GetOption<bool>("WmBridge.AoeLoot.Enable", false);
        gBridgeConfig.aoeLootRadius = sConfigMgr->GetOption<float>("WmBridge.AoeLoot.Radius", 35.0f);
        gBridgeConfig.aoeLootMaxCorpses = sConfigMgr->GetOption<uint32>("WmBridge.AoeLoot.MaxCorpses", 25);

        bool allowAllPlayers = false;
        gBridgeConfig.playerGuidAllowList = ParsePlayerGuidAllowList(
            sConfigMgr->GetOption<std::string>("WmBridge.PlayerGuidAllowList", ""),
            allowAllPlayers);
        gBridgeConfig.allowAllPlayers = allowAllPlayers;
        if (!gBridgeConfig.dbControlEnabled)
        {
            gBridgeConfig.dbPlayerGuidAllowList.clear();
        }
        gDbControlRefreshTimer = 0;
    }

    bool IsPlayerGuidAllowed(uint32 playerGuid)
    {
        if (!gBridgeConfig.enabled)
        {
            return false;
        }

        if (gBridgeConfig.allowAllPlayers)
        {
            return true;
        }

        return gBridgeConfig.playerGuidAllowList.find(playerGuid) != gBridgeConfig.playerGuidAllowList.end()
            || gBridgeConfig.dbPlayerGuidAllowList.find(playerGuid) != gBridgeConfig.dbPlayerGuidAllowList.end();
    }

    bool IsPlayerAllowed(Player const* player)
    {
        if (!player)
        {
            return false;
        }

        return IsPlayerGuidAllowed(static_cast<uint32>(player->GetGUID().GetCounter()));
    }

    void RefreshRuntimeControls(uint32 diff)
    {
        if (!gBridgeConfig.enabled || !gBridgeConfig.dbControlEnabled)
        {
            gBridgeConfig.dbPlayerGuidAllowList.clear();
            return;
        }

        if (gDbControlRefreshTimer > diff)
        {
            gDbControlRefreshTimer -= diff;
            return;
        }

        gDbControlRefreshTimer = gBridgeConfig.dbControlRefreshIntervalMs;
        std::unordered_set<uint32> nextAllowList;
        if (QueryResult result = WorldDatabase.Query(
                "SELECT PlayerGUID FROM wm_bridge_player_scope "
                "WHERE Enabled = 1 AND (ExpiresAt IS NULL OR ExpiresAt > NOW())"))
        {
            do
            {
                Field* fields = result->Fetch();
                nextAllowList.insert(fields[0].Get<uint32>());
            } while (result->NextRow());
        }

        gBridgeConfig.dbPlayerGuidAllowList = std::move(nextAllowList);
    }

    EventRow MakePlayerScopedEvent(Player const* player, std::string const& eventFamily, std::string const& eventType)
    {
        EventRow row;
        row.eventFamily = eventFamily;
        row.eventType = eventType;

        if (!player)
        {
            return row;
        }

        row.playerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        row.mapId = player->GetMapId();
        row.zoneId = player->GetZoneId();
        row.areaId = player->GetAreaId();

        if (WorldSession const* session = player->GetSession())
        {
            row.accountId = session->GetAccountId();
        }

        return row;
    }

    void EmitEvent(EventRow const& row)
    {
        if (!gBridgeConfig.enabled || !row.playerGuid.has_value() || !IsPlayerGuidAllowed(*row.playerGuid))
        {
            return;
        }

        WorldDatabase.Execute(
            "INSERT INTO wm_bridge_event ("
            "EventFamily, EventType, Source, PlayerGUID, AccountID, SubjectType, SubjectGUID, SubjectEntry, "
            "ObjectType, ObjectGUID, ObjectEntry, MapID, ZoneID, AreaID, PayloadJSON"
            ") VALUES ({}, {}, 'native_bridge', {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})",
            SqlString(row.eventFamily),
            SqlString(row.eventType),
            SqlUIntOrNull(row.playerGuid),
            SqlUIntOrNull(row.accountId),
            SqlStringOrNull(row.subjectType),
            SqlStringOrNull(row.subjectGuid),
            SqlUIntOrNull(row.subjectEntry),
            SqlStringOrNull(row.objectType),
            SqlStringOrNull(row.objectGuid),
            SqlUIntOrNull(row.objectEntry),
            SqlUIntOrNull(row.mapId),
            SqlUIntOrNull(row.zoneId),
            SqlUIntOrNull(row.areaId),
            SqlString(row.payloadJson));
    }

    std::string LookupAreaName(uint32 areaId)
    {
        if (AreaTableEntry const* areaEntry = GetAreaEntryByAreaID(areaId))
        {
            if (areaEntry->area_name[0] != nullptr)
            {
                return areaEntry->area_name[0];
            }
        }

        return "";
    }

    void JsonBegin(std::string& json, bool& firstField)
    {
        json = "{";
        firstField = true;
    }

    void JsonEnd(std::string& json)
    {
        json += "}";
    }

    void JsonAppendString(std::string& json, bool& firstField, std::string const& key, std::string const& value)
    {
        if (value.empty())
        {
            return;
        }

        if (!firstField)
        {
            json += ",";
        }

        firstField = false;
        json += "\"" + EscapeForJson(key) + "\":\"" + EscapeForJson(value) + "\"";
    }

    void JsonAppendNumber(std::string& json, bool& firstField, std::string const& key, long long value)
    {
        if (!firstField)
        {
            json += ",";
        }

        firstField = false;
        json += "\"" + EscapeForJson(key) + "\":" + std::to_string(value);
    }
}
