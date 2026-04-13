#include "ScriptMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "wm_spell_runtime.h"

class spell_wm_shell_dispatch : public SpellScript
{
    PrepareSpellScript(spell_wm_shell_dispatch);

    SpellCastResult CheckCast()
    {
        Unit* caster = GetCaster();
        Player* player = caster ? caster->ToPlayer() : nullptr;
        return WmSpells::CheckBoneboundCorpseTarget(player, GetSpellInfo()->Id);
    }

    void PreventStockShellEffect(SpellEffIndex effIndex)
    {
        PreventHitDefaultEffect(effIndex);
    }

    void HandleAfterCast()
    {
        Unit* caster = GetCaster();
        Player* player = caster ? caster->ToPlayer() : nullptr;
        if (!player)
            return;

        WmSpells::ExecuteShellBehavior(player, GetSpellInfo()->Id, true);
    }

    void Register() override
    {
        OnCheckCast += SpellCheckCastFn(spell_wm_shell_dispatch::CheckCast);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_DUMMY);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_SUMMON_PET);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_SUMMON);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_DUMMY);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_SUMMON_PET);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_SUMMON);
        AfterCast += SpellCastFn(spell_wm_shell_dispatch::HandleAfterCast);
    }
};

class spell_wm_shell_dispatch_loader : public SpellScriptLoader
{
public:
    spell_wm_shell_dispatch_loader() : SpellScriptLoader("spell_wm_shell_dispatch")
    {
    }

    SpellScript* GetSpellScript() const override
    {
        return new spell_wm_shell_dispatch();
    }
};

void AddSC_mod_wm_spells_spell_scripts()
{
    new spell_wm_shell_dispatch_loader();
}
