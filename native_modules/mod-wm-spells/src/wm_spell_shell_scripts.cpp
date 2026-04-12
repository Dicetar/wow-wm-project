#include "ScriptMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "wm_spell_runtime.h"

class spell_wm_bonebound_servant_shell : public SpellScript
{
    PrepareSpellScript(spell_wm_bonebound_servant_shell);

    SpellCastResult CheckCast()
    {
        Unit* caster = GetCaster();
        Player* player = caster ? caster->ToPlayer() : nullptr;
        return WmSpells::CheckBoneboundCorpseTarget(player);
    }

    void HandleDummy(SpellEffIndex /*effIndex*/)
    {
        Unit* caster = GetCaster();
        Player* player = caster ? caster->ToPlayer() : nullptr;
        if (!player)
            return;

        WmSpells::ExecuteBoneboundServant(player, GetSpellInfo()->Id, true);
    }

    void Register() override
    {
        OnCheckCast += SpellCheckCastFn(spell_wm_bonebound_servant_shell::CheckCast);
        OnEffectHit += SpellEffectFn(spell_wm_bonebound_servant_shell::HandleDummy, EFFECT_0, SPELL_EFFECT_DUMMY);
    }
};

class spell_wm_bonebound_servant_shell_loader : public SpellScriptLoader
{
public:
    spell_wm_bonebound_servant_shell_loader() : SpellScriptLoader("spell_wm_bonebound_servant_shell")
    {
    }

    SpellScript* GetSpellScript() const override
    {
        return new spell_wm_bonebound_servant_shell();
    }
};

void AddSC_mod_wm_spells_spell_scripts()
{
    new spell_wm_bonebound_servant_shell_loader();
}
