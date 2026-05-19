#pragma once

#include "Common.h"

#include <optional>
#include <string>
#include <vector>

// Phase 0E.3: SHARED engine-independent helpers extracted verbatim from
// wm_spell_runtime.cpp's anonymous namespace so every per-family TU
// (bonebound/proficiency/broug/night_watchers_lens/lanathel) and the
// dispatcher can share one definition. These JSON config extractors are
// the only cross-family-shared logic (used by Bonebound, Broug, Core,
// Lanathel, Proficiency config builders). Behavior-preserving: byte-
// identical bodies, internal -> external linkage in WmSpells::detail.

namespace WmSpells
{
    namespace detail
    {
        std::optional<std::string> ExtractJsonString(std::string const& json, std::string const& key);
        std::optional<uint32> ExtractJsonUInt(std::string const& json, std::string const& key);
        std::optional<float> ExtractJsonFloat(std::string const& json, std::string const& key);
        std::optional<bool> ExtractJsonBool(std::string const& json, std::string const& key);
        std::optional<std::vector<uint32>> ExtractJsonUIntArray(std::string const& json, std::string const& key);
    }
}
