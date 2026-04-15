#include "ScriptMgr.h"
#include "Unit.h"
#include "UnitScript.h"
#include "wm_spell_runtime.h"

class wm_spells_unit_script : public UnitScript
{
public:
    wm_spells_unit_script() : UnitScript("wm_spells_unit_script")
    {
    }

    void ModifyMeleeDamage(Unit* target, Unit* attacker, uint32& damage) override
    {
        WmSpells::HandleBoneboundMeleeDamage(attacker, target, damage);
    }
};

void AddSC_mod_wm_spells_unit_scripts()
{
    new wm_spells_unit_script();
}
