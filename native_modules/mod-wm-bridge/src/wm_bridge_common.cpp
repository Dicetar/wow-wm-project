#include "wm_bridge_common.h"

#include "wm_bridge_json.h"
#include "Config.h"
#include "DBCStores.h"
#include "DatabaseEnv.h"
#include "ObjectAccessor.h"
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
    uint32 gPresenceRefreshTimer = 0;

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

    std::unordered_set<uint32> ParseUInt32AllowList(std::string const& rawValue, bool& allowAll)
    {
        std::unordered_set<uint32> result;
        allowAll = false;

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
                allowAll = true;
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

    // Phase 0B: local EscapeForJson removed — now the single canonical
    // WmBridge::EscapeForJson (wm_bridge_json.h). This file's logic was
    // already the correct one, so behavior here is unchanged.
    using WmBridge::EscapeForJson;
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
        gBridgeConfig.emitAura = sConfigMgr->GetOption<bool>("WmBridge.Emit.Aura", false);
        gBridgeConfig.emitLevelUp = sConfigMgr->GetOption<bool>("WmBridge.Emit.LevelUp", true);
        gBridgeConfig.emitDeath = sConfigMgr->GetOption<bool>("WmBridge.Emit.Death", true);
        gBridgeConfig.dbControlEnabled = sConfigMgr->GetOption<bool>("WmBridge.DbControl.Enable", false);
        gBridgeConfig.dbControlRefreshIntervalMs = sConfigMgr->GetOption<uint32>("WmBridge.DbControl.RefreshIntervalMS", 5000);
        gBridgeConfig.actionQueueEnabled = sConfigMgr->GetOption<bool>("WmBridge.ActionQueue.Enable", false);
        gBridgeConfig.actionPollIntervalMs = sConfigMgr->GetOption<uint32>("WmBridge.ActionQueue.PollIntervalMS", 1000);
        gBridgeConfig.presenceEnabled = sConfigMgr->GetOption<bool>("WmBridge.Presence.Enable", true);
        gBridgeConfig.presenceIntervalMs = sConfigMgr->GetOption<uint32>("WmBridge.Presence.IntervalMS", 3000);
        gBridgeConfig.perceptionEnabled = sConfigMgr->GetOption<bool>("WmBridge.Perception.Enable", true);
        gBridgeConfig.perceptionIntervalMs = sConfigMgr->GetOption<uint32>("WmBridge.Perception.IntervalMS", 150000);
        gBridgeConfig.perceptionRadius = sConfigMgr->GetOption<uint32>("WmBridge.Perception.Radius", 40);
        gBridgeConfig.aoeLootEnabled = sConfigMgr->GetOption<bool>("WmBridge.AoeLoot.Enable", false);
        gBridgeConfig.aoeLootRadius = sConfigMgr->GetOption<float>("WmBridge.AoeLoot.Radius", 35.0f);
        gBridgeConfig.aoeLootMaxCorpses = sConfigMgr->GetOption<uint32>("WmBridge.AoeLoot.MaxCorpses", 25);

        bool allowAllPlayers = false;
        gBridgeConfig.playerGuidAllowList = ParseUInt32AllowList(
            sConfigMgr->GetOption<std::string>("WmBridge.PlayerGuidAllowList", ""),
            allowAllPlayers);
        gBridgeConfig.allowAllPlayers = allowAllPlayers;

        bool allowAllAuraSpells = false;
        gBridgeConfig.auraSpellAllowList = ParseUInt32AllowList(
            sConfigMgr->GetOption<std::string>("WmBridge.Emit.AuraSpellAllowList", "946602,132,687,770"),
            allowAllAuraSpells);
        gBridgeConfig.allowAllAuraSpells = allowAllAuraSpells;
        if (!gBridgeConfig.dbControlEnabled)
        {
            gBridgeConfig.dbPlayerGuidAllowList.clear();
        }
        gDbControlRefreshTimer = 0;
        gPresenceRefreshTimer = 0;
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

    bool IsAuraSpellAllowed(uint32 spellId)
    {
        if (!gBridgeConfig.emitAura || spellId == 0)
        {
            return false;
        }

        return gBridgeConfig.allowAllAuraSpells
            || gBridgeConfig.auraSpellAllowList.find(spellId) != gBridgeConfig.auraSpellAllowList.end();
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

    void RefreshPlayerPresence(uint32 diff)
    {
        if (!gBridgeConfig.enabled || !gBridgeConfig.presenceEnabled)
        {
            return;
        }

        if (gPresenceRefreshTimer > diff)
        {
            gPresenceRefreshTimer -= diff;
            return;
        }

        gPresenceRefreshTimer = gBridgeConfig.presenceIntervalMs;

        std::unordered_set<uint32> onlineSeen;

        auto upsertOnline = [&](Player* player)
        {
            if (!player || !player->IsInWorld())
            {
                return;
            }

            uint32 const guid = static_cast<uint32>(player->GetGUID().GetCounter());
            onlineSeen.insert(guid);

            uint32 accountId = 0;
            if (WorldSession const* session = player->GetSession())
            {
                accountId = session->GetAccountId();
            }

            uint32 const zoneId = player->GetZoneId();
            uint32 const areaId = player->GetAreaId();
            uint32 const maxHealth = player->GetMaxHealth();
            uint32 const healthPct = maxHealth ? static_cast<uint32>((player->GetHealth() * 100) / maxHealth) : 0;

            WorldDatabase.Execute(
                "INSERT INTO wm_bridge_player_presence ("
                "PlayerGUID, AccountID, Online, MapID, ZoneID, AreaID, ZoneName, AreaName, "
                "PosX, PosY, PosZ, Orientation, Level, HealthPct, InCombat, UpdatedAt"
                ") VALUES ({}, {}, 1, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, NOW()) "
                "ON DUPLICATE KEY UPDATE "
                "AccountID = VALUES(AccountID), Online = 1, MapID = VALUES(MapID), "
                "ZoneID = VALUES(ZoneID), AreaID = VALUES(AreaID), ZoneName = VALUES(ZoneName), "
                "AreaName = VALUES(AreaName), PosX = VALUES(PosX), PosY = VALUES(PosY), "
                "PosZ = VALUES(PosZ), Orientation = VALUES(Orientation), Level = VALUES(Level), "
                "HealthPct = VALUES(HealthPct), InCombat = VALUES(InCombat), UpdatedAt = NOW()",
                guid,
                accountId,
                player->GetMapId(),
                zoneId,
                areaId,
                SqlString(LookupAreaName(zoneId)),
                SqlString(LookupAreaName(areaId)),
                player->GetPositionX(),
                player->GetPositionY(),
                player->GetPositionZ(),
                player->GetOrientation(),
                static_cast<uint32>(player->GetLevel()),
                healthPct,
                player->IsInCombat() ? 1 : 0);
        };

        auto markOffline = [&](uint32 guid)
        {
            if (onlineSeen.find(guid) != onlineSeen.end())
            {
                return;
            }

            WorldDatabase.Execute(
                "UPDATE wm_bridge_player_presence SET Online = 0, UpdatedAt = NOW() WHERE PlayerGUID = {}",
                guid);
        };

        if (gBridgeConfig.allowAllPlayers)
        {
            for (auto const& pair : ObjectAccessor::GetPlayers())
            {
                upsertOnline(pair.second);
            }
            return;
        }

        for (uint32 guid : gBridgeConfig.playerGuidAllowList)
        {
            upsertOnline(ObjectAccessor::FindPlayerByLowGUID(guid));
        }
        for (uint32 guid : gBridgeConfig.dbPlayerGuidAllowList)
        {
            upsertOnline(ObjectAccessor::FindPlayerByLowGUID(guid));
        }

        for (uint32 guid : gBridgeConfig.playerGuidAllowList)
        {
            markOffline(guid);
        }
        for (uint32 guid : gBridgeConfig.dbPlayerGuidAllowList)
        {
            markOffline(guid);
        }
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
        // GetZoneId()/GetAreaId() return AreaTable DBC record IDs, so look them
        // up directly. GetAreaEntryByAreaID resolves via the terrain exploreFlag
        // (a different field) and returns an unrelated area for plain zone IDs.
        if (AreaTableEntry const* areaEntry = sAreaTableStore.LookupEntry(areaId))
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
