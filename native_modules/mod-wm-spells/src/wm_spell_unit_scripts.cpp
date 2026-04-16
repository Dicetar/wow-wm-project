#include "ScriptMgr.h"
#include "Creature.h"
#include "Player.h"
#include "Unit.h"
#include "UnitScript.h"
#include "wm_spell_runtime.h"

class wm_spells_unit_script : public UnitScript
{
public:
    wm_spells_unit_script() : UnitScript(
        "wm_spells_unit_script",
        true,
        {UNITHOOK_MODIFY_MELEE_DAMAGE, UNITHOOK_ON_UNIT_DEATH})
    {
    }

    void ModifyMeleeDamage(Unit* target, Unit* attacker, uint32& damage) override
    {
        WmSpells::HandleBoneboundMeleeDamage(attacker, target, damage);
    }

    void OnUnitDeath(Unit* unit, Unit* killer) override
    {
        Creature* killed = unit ? unit->ToCreature() : nullptr;
        if (!killed || !killer)
            return;

        Player* owner = killer->GetCharmerOrOwnerPlayerOrPlayerItself();
        if (!owner)
            return;

        // Player and real pet/totem kills already arrive through PlayerScript hooks.
        if (killer->ToPlayer() || killer->IsPet() || killer->IsTotem())
            return;

        WmSpells::HandleNightWatchersLensKill(owner, killed, killer);
    }
};

void AddSC_mod_wm_spells_unit_scripts()
{
    new wm_spells_unit_script();
}
