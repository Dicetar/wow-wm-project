#pragma once

#include "Common.h"

#include <mutex>
#include <string>
#include <unordered_map>

namespace WmBridge
{
    struct WMActiveEffect
    {
        uint32 sourcePlayerGuid = 0;
        uint32 targetGuid       = 0;
        bool   targetIsPlayer   = false;
        uint32 auraSpellId      = 0;
        std::string effectKind;
        std::string paramsJson;
        uint32 appliedAtSec     = 0;    // Unix timestamp
        uint32 expiresAtSec     = 0;    // 0 = permanent
    };

    class WMEffectRegistry
    {
    public:
        static WMEffectRegistry& Instance();

        // Call after AddAura() succeeds. durationSec=0 means permanent.
        void Register(uint32 sourcePlayerGuid,
                      uint32 targetGuid, bool targetIsPlayer,
                      uint32 auraSpellId,
                      std::string const& effectKind,
                      std::string const& paramsJson,
                      uint32 durationSec);

        // Call from OnAuraRemove so the registry stays in sync with the aura timeline.
        void Unregister(uint32 targetGuid, bool targetIsPlayer, uint32 auraSpellId);

        // Tick gate — O(1) lookup. Returns false when no active registered effect.
        bool IsActive(uint32 targetGuid, bool targetIsPlayer, uint32 auraSpellId) const;

        // Sweep overdue timed effects. Returns count of entries removed.
        // Call from OnUpdate; no DB I/O — pure in-process expiry.
        uint32 ExpireOverdue();

    private:
        static uint64 MakeKey(uint32 targetGuid, uint32 auraSpellId);

        mutable std::mutex m_mutex;
        std::unordered_map<uint64, WMActiveEffect> m_playerEffects;
        std::unordered_map<uint64, WMActiveEffect> m_creatureEffects;
    };

} // namespace WmBridge
