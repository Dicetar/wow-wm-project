#include "ScriptMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Chat.h"
#include "wm_spell_runtime.h"

class spell_wm_shell_dispatch : public SpellScript
{
    PrepareSpellScript(spell_wm_shell_dispatch);

    SpellCastResult CheckCast()
    {
        Unit* caster = GetCaster();
        Player* player = caster ? caster->ToPlayer() : nullptr;
        return WmSpells::CheckShellCast(player, GetSpellInfo()->Id, GetExplTargetUnit());
    }

    void PreventStockShellEffect(SpellEffIndex effIndex)
    {
        Unit* caster = GetCaster();
        Player const* player = caster ? caster->ToPlayer() : nullptr;
        if (WmSpells::ShouldAllowShellDefaultEffect(player, GetSpellInfo()->Id, static_cast<uint8>(effIndex)))
            return;

        PreventHitDefaultEffect(effIndex);
    }

    void HandleAfterCast()
    {
        Unit* caster = GetCaster();
        Player* player = caster ? caster->ToPlayer() : nullptr;
        if (!player)
            return;

        WmSpells::BehaviorExecutionResult result = WmSpells::ExecuteShellBehavior(player, GetSpellInfo()->Id, true, GetExplTargetUnit());
        if (!result.ok)
            ChatHandler(player->GetSession()).PSendSysMessage("WM shell {} failed: {}", GetSpellInfo()->Id, result.message);
        else if (GetSpellInfo()->Id == 946202)
            ChatHandler(player->GetSession()).PSendSysMessage("WM Broug: Cloud Step fired.");
    }

    void Register() override
    {
        OnCheckCast += SpellCheckCastFn(spell_wm_shell_dispatch::CheckCast);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_DUMMY);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_SCHOOL_DAMAGE);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_WEAPON_DAMAGE);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_WEAPON_DAMAGE_NOSCHOOL);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_WEAPON_PERCENT_DAMAGE);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_NORMALIZED_WEAPON_DMG);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_APPLY_AURA);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_SUMMON_PET);
        OnEffectLaunch += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_SUMMON);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_DUMMY);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_SCHOOL_DAMAGE);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_WEAPON_DAMAGE);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_WEAPON_DAMAGE_NOSCHOOL);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_WEAPON_PERCENT_DAMAGE);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_NORMALIZED_WEAPON_DMG);
        OnEffectHit += SpellEffectFn(spell_wm_shell_dispatch::PreventStockShellEffect, EFFECT_0, SPELL_EFFECT_APPLY_AURA);
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
