#include "ScriptMgr.h"
#include "wm_bridge_action_queue.h"
#include "wm_bridge_common.h"
#include "wm_effect_registry.h"

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
        WmBridge::RefreshPlayerPresence(diff);
        WmBridge::RefreshPlayerPerception(diff);
        WmBridge::PollActionQueue(diff);
        WmBridge::WMEffectRegistry::Instance().ExpireOverdue();
    }
};

void AddSC_mod_wm_bridge_worldscript()
{
    new wm_bridge_worldscript();
}
