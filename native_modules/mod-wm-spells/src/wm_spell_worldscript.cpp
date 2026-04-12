#include "ScriptMgr.h"
#include "wm_spell_runtime.h"

class wm_spells_worldscript : public WorldScript
{
public:
    wm_spells_worldscript() : WorldScript("wm_spells_worldscript")
    {
    }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        WmSpells::LoadConfig();
    }

    void OnUpdate(uint32 diff) override
    {
        WmSpells::PollDebugRequests(diff);
    }
};

void AddSC_mod_wm_spells_worldscript()
{
    new wm_spells_worldscript();
}
