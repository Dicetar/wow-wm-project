#include "wm_spell_internal.h"

#include <regex>

// Phase 0E.3: bodies moved verbatim from wm_spell_runtime.cpp. Pure
// std::regex JSON extraction — no engine dependency. Behavior-identical.

namespace WmSpells
{
    namespace detail
    {
    std::optional<std::string> ExtractJsonString(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
        std::smatch match;
        if (std::regex_search(json, match, pattern) && match.size() > 1)
            return match[1].str();
        return std::nullopt;
    }

    std::optional<uint32> ExtractJsonUInt(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*(-?\\d+)");
        std::smatch match;
        if (std::regex_search(json, match, pattern) && match.size() > 1)
        {
            long long value = std::stoll(match[1].str());
            if (value < 0)
                return 0u;
            return static_cast<uint32>(value);
        }
        return std::nullopt;
    }

    std::optional<float> ExtractJsonFloat(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)");
        std::smatch match;
        if (std::regex_search(json, match, pattern) && match.size() > 1)
            return std::stof(match[1].str());
        return std::nullopt;
    }

    std::optional<bool> ExtractJsonBool(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*(true|false)");
        std::smatch match;
        if (std::regex_search(json, match, pattern) && match.size() > 1)
            return match[1].str() == "true";
        return std::nullopt;
    }

    std::optional<std::vector<uint32>> ExtractJsonUIntArray(std::string const& json, std::string const& key)
    {
        std::regex pattern("\"" + key + "\"\\s*:\\s*\\[([^\\]]*)\\]");
        std::smatch match;
        if (!std::regex_search(json, match, pattern) || match.size() <= 1)
            return std::nullopt;

        std::vector<uint32> values;
        std::string raw = match[1].str();
        std::regex numberPattern("(\\d+)");
        for (std::sregex_iterator it(raw.begin(), raw.end(), numberPattern), end; it != end; ++it)
            values.push_back(static_cast<uint32>(std::stoul((*it)[1].str())));

        return values;
    }
    }
}
