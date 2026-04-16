#include "Creature.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "Unit.h"
#include "UnitScript.h"
#include "wm_bridge_common.h"

namespace
{
    void EmitOwnedUnitKill(Player* player, Creature* killed, Unit* killer)
    {
        if (!WmBridge::IsPlayerAllowed(player) || !killed || !killer)
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "combat", "kill");
        row.subjectType = "creature";
        row.subjectGuid = killed->GetGUID().ToString();
        row.subjectEntry = killed->GetEntry();

        if (Creature* killerCreature = killer->ToCreature())
        {
            row.objectType = "creature";
            row.objectGuid = killerCreature->GetGUID().ToString();
            row.objectEntry = killerCreature->GetEntry();
        }

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendString(payload, firstField, "subject_name", killed->GetName());
        WmBridge::JsonAppendString(payload, firstField, "kill_source", "owned_unit");
        WmBridge::JsonAppendNumber(payload, firstField, "player_guid", static_cast<long long>(player->GetGUID().GetCounter()));
        WmBridge::JsonAppendNumber(payload, firstField, "subject_entry", static_cast<long long>(killed->GetEntry()));
        if (Creature* killerCreature = killer->ToCreature())
        {
            WmBridge::JsonAppendString(payload, firstField, "killer_name", killerCreature->GetName());
            WmBridge::JsonAppendNumber(payload, firstField, "killer_entry", static_cast<long long>(killerCreature->GetEntry()));
        }
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }
}

class wm_bridge_unit_script : public UnitScript
{
public:
    wm_bridge_unit_script() : UnitScript("wm_bridge_unit_script", true, {UNITHOOK_ON_UNIT_DEATH})
    {
    }

    void OnUnitDeath(Unit* unit, Unit* killer) override
    {
        if (!WmBridge::GetConfig().emitKill || !unit || !killer)
        {
            return;
        }

        Creature* killed = unit->ToCreature();
        if (!killed)
        {
            return;
        }

        Player* owner = killer->GetCharmerOrOwnerPlayerOrPlayerItself();
        if (!owner || !WmBridge::IsPlayerAllowed(owner))
        {
            return;
        }

        // Player and real pet/totem kills already emit through PlayerScript hooks.
        if (killer->ToPlayer() || killer->IsPet() || killer->IsTotem())
        {
            return;
        }

        EmitOwnedUnitKill(owner, killed, killer);
    }
};

void AddSC_mod_wm_bridge_unit_script()
{
    new wm_bridge_unit_script();
}
