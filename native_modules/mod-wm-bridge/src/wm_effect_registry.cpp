#include "wm_effect_registry.h"

#include <ctime>
#include <vector>

namespace WmBridge
{
    // static
    WMEffectRegistry& WMEffectRegistry::Instance()
    {
        static WMEffectRegistry sInstance;
        return sInstance;
    }

    // static
    uint64 WMEffectRegistry::MakeKey(uint32 targetGuid, uint32 auraSpellId)
    {
        return (static_cast<uint64>(targetGuid) << 32) | static_cast<uint64>(auraSpellId);
    }

    void WMEffectRegistry::Register(uint32 sourcePlayerGuid,
                                    uint32 targetGuid, bool targetIsPlayer,
                                    uint32 auraSpellId,
                                    std::string const& effectKind,
                                    std::string const& paramsJson,
                                    uint32 durationSec)
    {
        WMActiveEffect effect;
        effect.sourcePlayerGuid = sourcePlayerGuid;
        effect.targetGuid       = targetGuid;
        effect.targetIsPlayer   = targetIsPlayer;
        effect.auraSpellId      = auraSpellId;
        effect.effectKind       = effectKind;
        effect.paramsJson       = paramsJson;
        effect.appliedAtSec     = static_cast<uint32>(std::time(nullptr));
        effect.expiresAtSec     = durationSec > 0
            ? (effect.appliedAtSec + durationSec)
            : 0;

        uint64 key = MakeKey(targetGuid, auraSpellId);
        std::lock_guard<std::mutex> lock(m_mutex);
        auto& map = targetIsPlayer ? m_playerEffects : m_creatureEffects;
        map[key] = std::move(effect);
    }

    void WMEffectRegistry::Unregister(uint32 targetGuid, bool targetIsPlayer, uint32 auraSpellId)
    {
        uint64 key = MakeKey(targetGuid, auraSpellId);
        std::lock_guard<std::mutex> lock(m_mutex);
        auto& map = targetIsPlayer ? m_playerEffects : m_creatureEffects;
        map.erase(key);
    }

    bool WMEffectRegistry::IsActive(uint32 targetGuid, bool targetIsPlayer, uint32 auraSpellId) const
    {
        uint64 key = MakeKey(targetGuid, auraSpellId);
        std::lock_guard<std::mutex> lock(m_mutex);
        auto const& map = targetIsPlayer ? m_playerEffects : m_creatureEffects;
        auto it = map.find(key);
        if (it == map.end())
            return false;
        // If timed: confirm not yet expired
        if (it->second.expiresAtSec > 0)
        {
            uint32 nowSec = static_cast<uint32>(std::time(nullptr));
            return nowSec < it->second.expiresAtSec;
        }
        return true;
    }

    uint32 WMEffectRegistry::ExpireOverdue()
    {
        uint32 nowSec = static_cast<uint32>(std::time(nullptr));
        uint32 removed = 0;

        std::lock_guard<std::mutex> lock(m_mutex);

        auto sweep = [&](std::unordered_map<uint64, WMActiveEffect>& map)
        {
            for (auto it = map.begin(); it != map.end();)
            {
                if (it->second.expiresAtSec > 0 && nowSec >= it->second.expiresAtSec)
                {
                    it = map.erase(it);
                    ++removed;
                }
                else
                {
                    ++it;
                }
            }
        };

        sweep(m_playerEffects);
        sweep(m_creatureEffects);
        return removed;
    }

} // namespace WmBridge
