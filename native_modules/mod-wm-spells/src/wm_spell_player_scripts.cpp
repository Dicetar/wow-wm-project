#include "ScriptMgr.h"
#include "Player.h"
#include "wm_spell_runtime.h"

#include <unordered_map>

namespace
{
    constexpr uint32 BONEBOUND_MAINTENANCE_INTERVAL_MS = 1000;
    std::unordered_map<uint32, uint32> gBoneboundMaintenanceTimers;
}

class wm_spells_player_script : public PlayerScript
{
public:
    wm_spells_player_script() : PlayerScript("wm_spells_player_script")
    {
    }

    void OnPlayerLogin(Player* player) override
    {
        if (!player)
            return;

        gBoneboundMaintenanceTimers[static_cast<uint32>(player->GetGUID().GetCounter())] = 0;
        WmSpells::MaintainBoneboundSummons(player);
    }

    void OnPlayerAfterUpdate(Player* player, uint32 diff) override
    {
        if (!player || !WmSpells::IsPlayerAllowed(player))
            return;

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        uint32& timer = gBoneboundMaintenanceTimers[ownerGuid];
        if (timer > diff)
        {
            timer -= diff;
            return;
        }

        timer = BONEBOUND_MAINTENANCE_INTERVAL_MS;
        WmSpells::MaintainBoneboundSummons(player);
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        if (!player)
            return;

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        gBoneboundMaintenanceTimers.erase(ownerGuid);
        WmSpells::ForgetBoneboundCompanions(player);
    }
};

void AddSC_mod_wm_spells_player_scripts()
{
    new wm_spells_player_script();
}
