#pragma once

#include "Common.h"

#include <string>

// Canonical JSON helpers for mod-wm-bridge. Before Phase 0B, EscapeForJson
// was defined twice (wm_bridge_common.cpp and wm_bridge_action_queue.cpp)
// with divergent, partly-buggy behavior. This is the single source of
// truth; both call sites delegate here.
//
// Escaping contract (the correct, common.cpp-derived behavior):
//   \\  "  \b  \f  \n  \r  \t      -> escaped
//   other byte < 0x20              -> single space
//   byte >= 0x20 (incl. UTF-8 >=0x80) -> passthrough unchanged
// Iterating as unsigned char is REQUIRED so multi-byte UTF-8 is not
// corrupted (the old action_queue version iterated signed char and
// replaced every byte >=0x80 with a space).

namespace WmBridge
{
    std::string EscapeForJson(std::string const& value);
}
