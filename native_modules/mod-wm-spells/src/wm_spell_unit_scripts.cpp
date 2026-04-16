#include "ScriptMgr.h"
#include "Unit.h"
#include "UnitScript.h"
#include "wm_spell_runtime.h"

class wm_spells_unit_script : public UnitScript
{
public:
    wm_spells_unit_script() : UnitScript(
        "wm_spells_unit_script",
        true,
        {
            UNITHOOK_ON_DAMAGE,
            UNITHOOK_MODIFY_MELEE_DAMAGE,
            UNITHOOK_ON_BEFORE_ROLL_MELEE_OUTCOME_AGAINST
        })
    {
    }

    void OnDamage(Unit* attacker, Unit* victim, uint32& damage) override
    {
        WmSpells::HandleNightWatchersLensDamage(attacker, victim, damage);
    }

    void ModifyMeleeDamage(Unit* target, Unit* attacker, uint32& damage) override
    {
        WmSpells::HandleBoneboundMeleeDamage(attacker, target, damage);
    }

    void OnBeforeRollMeleeOutcomeAgainst(
        Unit const* attacker,
        Unit const* victim,
        WeaponAttackType attType,
        int32& attackerMaxSkillValueForLevel,
        int32& victimMaxSkillValueForLevel,
        int32& attackerWeaponSkill,
        int32& victimDefenseSkill,
        int32& crit_chance,
        int32& miss_chance,
        int32& dodge_chance,
        int32& parry_chance,
        int32& block_chance) override
    {
        WmSpells::HandleNightWatchersLensDefenseBypass(
            attacker,
            victim,
            attType,
            attackerMaxSkillValueForLevel,
            victimMaxSkillValueForLevel,
            attackerWeaponSkill,
            victimDefenseSkill,
            crit_chance,
            miss_chance,
            dodge_chance,
            parry_chance,
            block_chance);
    }
};

void AddSC_mod_wm_spells_unit_scripts()
{
    new wm_spells_unit_script();
}
