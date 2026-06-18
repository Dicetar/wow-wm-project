#include "Player.h"
#include "ScriptedGossip.h"
#include "wm_bridge_action_registry.h"
#include "wm_bridge_action_support.h"

namespace
{
    using namespace WmBridge::detail;

    bool ExecutePlayerCloseGossip(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        CloseGossipMenuFor(player);
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "gossip_closed", {}, {{"player_guid", playerGuid}}));
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgeGossipActions(ActionRegistry& registry)
    {
        registry.Register("player_close_gossip", &ExecutePlayerCloseGossip);
    }
}
