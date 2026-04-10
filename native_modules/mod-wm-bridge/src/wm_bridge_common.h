#pragma once

#include "Common.h"

#include <optional>
#include <string>
#include <unordered_set>

class Player;

namespace WmBridge
{
    struct BridgeConfig
    {
        bool enabled = true;
        bool emitKill = true;
        bool emitQuest = true;
        bool emitLoot = true;
        bool emitGossip = true;
        bool emitArea = true;
        bool allowAllPlayers = false;
        bool dbControlEnabled = false;
        uint32 dbControlRefreshIntervalMs = 5000;
        bool actionQueueEnabled = false;
        uint32 actionPollIntervalMs = 1000;
        std::unordered_set<uint32> playerGuidAllowList;
        std::unordered_set<uint32> dbPlayerGuidAllowList;
    };

    struct EventRow
    {
        std::string eventFamily;
        std::string eventType;
        std::optional<uint32> playerGuid;
        std::optional<uint32> accountId;
        std::optional<std::string> subjectType;
        std::optional<std::string> subjectGuid;
        std::optional<uint32> subjectEntry;
        std::optional<std::string> objectType;
        std::optional<std::string> objectGuid;
        std::optional<uint32> objectEntry;
        std::optional<uint32> mapId;
        std::optional<uint32> zoneId;
        std::optional<uint32> areaId;
        std::string payloadJson = "{}";
    };

    BridgeConfig const& GetConfig();
    void LoadConfig();
    bool IsPlayerGuidAllowed(uint32 playerGuid);
    bool IsPlayerAllowed(Player const* player);
    void RefreshRuntimeControls(uint32 diff);

    EventRow MakePlayerScopedEvent(Player const* player, std::string const& eventFamily, std::string const& eventType);
    void EmitEvent(EventRow const& row);

    std::string LookupAreaName(uint32 areaId);

    void JsonBegin(std::string& json, bool& firstField);
    void JsonEnd(std::string& json);
    void JsonAppendString(std::string& json, bool& firstField, std::string const& key, std::string const& value);
    void JsonAppendNumber(std::string& json, bool& firstField, std::string const& key, long long value);
}
