#include "ScriptMgr.h"
#include "wm_bridge_action_queue.h"
#include "wm_bridge_common.h"

class wm_bridge_worldscript : public WorldScript
{
public:
    wm_bridge_worldscript() : WorldScript("wm_bridge_worldscript")
    {
    }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        WmBridge::LoadConfig();
    }

    void OnUpdate(uint32 diff) override
    {
        WmBridge::RefreshRuntimeControls(diff);
        WmBridge::PollActionQueue(diff);
    }
};

void AddSC_mod_wm_bridge_worldscript()
{
    new wm_bridge_worldscript();
}
