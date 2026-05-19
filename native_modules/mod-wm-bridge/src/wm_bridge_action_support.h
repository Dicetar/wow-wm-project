#pragma once

#include "Common.h"

#include <initializer_list>
#include <string>
#include <utility>

// Phase 0D: shared action-queue infrastructure. Extracted verbatim from
// wm_bridge_action_queue.cpp's anonymous namespace so the per-domain
// handler files (player/creature/quest/inventory/environment/debug) and
// the slimmed dispatcher can all share one definition. Behavior-preserving:
// these are byte-identical moves, only linkage changed (internal -> external
// in WmBridge::detail). The seam (action bus, result JSON shapes) is
// unchanged.

class Player;

namespace WmBridge
{
    namespace detail
    {
        std::string EscapeForSql(std::string value);
        std::string SqlString(std::string const& value);

        std::string ExtractJsonStringField(std::string const& json, std::string const& key);
        bool TryExtractJsonUInt32Field(std::string const& json, std::string const& key, uint32& value);
        bool TryExtractJsonInt32Field(std::string const& json, std::string const& key, int32& value);
        bool TryExtractJsonFloatField(std::string const& json, std::string const& key, float& value);
        bool TryExtractJsonBoolField(std::string const& json, std::string const& key, bool& value);
        bool TryExtractAnyUInt32Field(std::string const& json, std::initializer_list<char const*> keys, uint32& value);
        bool TryExtractAnyInt32Field(std::string const& json, std::initializer_list<char const*> keys, int32& value);
        bool TryExtractAnyFloatField(std::string const& json, std::initializer_list<char const*> keys, float& value);
        bool TryExtractAnyBoolField(std::string const& json, std::initializer_list<char const*> keys, bool& value);

        int RiskRank(std::string risk);

        std::string ResultJson(std::string const& status, std::string const& actionKind, std::string const& message = "");
        std::string FloatString(float value);

        void JsonAppendComma(std::string& json, bool& firstField);
        void JsonAppendStringField(std::string& json, bool& firstField, std::string const& key, std::string const& value);
        void JsonAppendNumberField(std::string& json, bool& firstField, std::string const& key, long long value);
        void JsonAppendFloatField(std::string& json, bool& firstField, std::string const& key, float value);
        void JsonAppendBoolField(std::string& json, bool& firstField, std::string const& key, bool value);
        void JsonAppendRawField(std::string& json, bool& firstField, std::string const& key, std::string const& rawJson);

        std::string ActionResultJson(std::string const& status, std::string const& actionKind, std::string const& message = "");
        std::string ActionResultJson(
            std::string const& status,
            std::string const& actionKind,
            std::string const& message,
            std::initializer_list<std::pair<std::string, std::string>> stringFields,
            std::initializer_list<std::pair<std::string, long long>> numberFields = {});
        std::string ActionResultJson(
            std::string const& status,
            std::string const& actionKind,
            std::string const& message,
            std::initializer_list<std::pair<std::string, std::string>> stringFields,
            std::initializer_list<std::pair<std::string, long long>> numberFields,
            std::initializer_list<std::pair<std::string, float>> floatFields);

        void CompleteAction(uint64 requestId, std::string const& status, std::string const& actionKind, std::string const& resultJson, std::string const& errorText = "");

        bool ResolveScopedOnlinePlayer(
            uint64 requestId,
            uint32 playerGuid,
            std::string const& actionKind,
            std::string const& payloadJson,
            Player*& player);

        std::string NormalizedJsonToken(std::string value);
        bool ResolveTriggeredCastFlag(std::string const& payloadJson);

        bool ActionPolicyAllows(
            uint64 requestId,
            uint32 playerGuid,
            std::string const& actionKind,
            std::string const& riskLevel,
            std::string const& createdBy,
            std::string& rejectReason);
    }
}
