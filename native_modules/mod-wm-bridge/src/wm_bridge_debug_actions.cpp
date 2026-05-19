// Phase 0D: debug-domain native WM action handlers. Bodies moved
// verbatim from wm_bridge_action_queue.cpp; shared infra lives in
// wm_bridge_action_support.h (WmBridge::detail). Registered via
// RegisterWmBridgeDebugActions from the queue bootstrap.

#include "Configuration/Config.h"
#include "DatabaseEnv.h"
#include "Cell.h"
#include "CellImpl.h"
#include "Creature.h"
#include "DBCStores.h"
#include "GameObject.h"
#include "GridNotifiers.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QueryResult.h"
#include "Random.h"
#include "ReputationMgr.h"
#include "SpellMgr.h"
#include "TemporarySummon.h"
#include "Unit.h"
#include "WorldSession.h"
#include "wm_bridge_action_registry.h"
#include "wm_bridge_action_support.h"
#include "wm_bridge_common.h"
#include "wm_bridge_json.h"
#include "wm_bridge_random_enchant.h"
#include "wm_effect_registry.h"

#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <initializer_list>
#include <limits>
#include <list>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

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
