#pragma once

#include "Common.h"

#include <string>
#include <unordered_map>
#include <vector>

// Phase 0C: table-driven action dispatch. Replaces the 26-branch
// if (actionKind == "...") chain in ExecuteClaimedAction with an O(1)
// lookup. Handlers share one uniform signature; the pre-checks
// (scoping + policy) and the not-implemented fallback stay in the
// caller — only the selection mechanism changes.

namespace WmBridge
{
    using ActionHandler = bool (*)(uint64 requestId,
                                   uint32 playerGuid,
                                   std::string const& actionKind,
                                   std::string const& payloadJson);

    class ActionRegistry
    {
    public:
        // Last registration for a kind wins (deterministic; lets later
        // domain files override if ever needed). Null fn is ignored.
        void Register(std::string const& kind, ActionHandler fn);

        // Returns nullptr when the kind has no handler.
        ActionHandler Find(std::string const& kind) const;

        bool Has(std::string const& kind) const;
        std::vector<std::string> Kinds() const;
        std::size_t Size() const;

    private:
        std::unordered_map<std::string, ActionHandler> m_handlers;
    };
}
