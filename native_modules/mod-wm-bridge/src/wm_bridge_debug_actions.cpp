// Phase 0D: debug-domain native WM action handlers. Bodies moved
// verbatim from wm_bridge_action_queue.cpp; shared infra lives in
// wm_bridge_action_support.h (WmBridge::detail). Registered via
// RegisterWmBridgeDebugActions from the queue bootstrap.

#include "wm_bridge_action_registry.h"
#include "wm_bridge_action_support.h"
#include "wm_bridge_common.h"
#include "wm_bridge_json.h"

#include <string>

namespace
{
    using WmBridge::EscapeForJson;
    using namespace WmBridge::detail;

    bool ExecuteDebugPing(uint64 requestId, uint32 /*playerGuid*/, std::string const& actionKind, std::string const& /*payloadJson*/)
    {
        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "pong"));
        return true;
    }

    bool ExecuteDebugEcho(uint64 requestId, uint32 /*playerGuid*/, std::string const& actionKind, std::string const& payloadJson)
    {
        std::string result = "{\"ok\":true,\"action_kind\":\"debug_echo\",\"payload_json\":\"" + EscapeForJson(payloadJson) + "\"}";
        CompleteAction(requestId, "done", actionKind, result);
        return true;
    }

    bool ExecuteDebugFail(uint64 requestId, uint32 /*playerGuid*/, std::string const& actionKind, std::string const& /*payloadJson*/)
    {
        CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "debug_fail_requested"), "debug_fail_requested");
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgeDebugActions(ActionRegistry& registry)
    {
        registry.Register("debug_ping", &ExecuteDebugPing);
        registry.Register("debug_echo", &ExecuteDebugEcho);
        registry.Register("debug_fail", &ExecuteDebugFail);
    }
}
