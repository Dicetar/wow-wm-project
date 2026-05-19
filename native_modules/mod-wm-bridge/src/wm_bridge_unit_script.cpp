#include "Creature.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "Unit.h"
#include "UnitScript.h"
#include "wm_bridge_common.h"
#include "wm_effect_registry.h"

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

    void EmitPlayerAura(Player* player, Aura const* aura, char const* eventType, AuraRemoveMode removeMode = AURA_REMOVE_NONE)
    {
        if (!player || !aura || !WmBridge::GetConfig().emitAura)
        {
            return;
        }

        SpellInfo const* spellInfo = aura->GetSpellInfo();
        uint32 spellId = spellInfo ? spellInfo->Id : aura->GetId();
        if (!WmBridge::IsAuraSpellAllowed(spellId) || !WmBridge::IsPlayerAllowed(player))
        {
            return;
        }

        auto row = WmBridge::MakePlayerScopedEvent(player, "aura", eventType);
        row.subjectType = "spell";
        row.subjectEntry = spellId;

        std::string payload;
        bool firstField = true;
        WmBridge::JsonBegin(payload, firstField);
        WmBridge::JsonAppendString(payload, firstField, "player_name", player->GetName());
        WmBridge::JsonAppendNumber(payload, firstField, "player_guid", static_cast<long long>(player->GetGUID().GetCounter()));
        WmBridge::JsonAppendNumber(payload, firstField, "spell_id", static_cast<long long>(spellId));
        if (spellInfo)
        {
            WmBridge::JsonAppendString(payload, firstField, "spell_name", spellInfo->SpellName[0]);
            WmBridge::JsonAppendString(payload, firstField, "aura_name", spellInfo->SpellName[0]);
        }
        WmBridge::JsonAppendString(payload, firstField, "caster_guid", aura->GetCasterGUID().ToString());
        WmBridge::JsonAppendNumber(payload, firstField, "duration_ms", static_cast<long long>(aura->GetDuration()));
        WmBridge::JsonAppendNumber(payload, firstField, "max_duration_ms", static_cast<long long>(aura->GetMaxDuration()));
        if (removeMode != AURA_REMOVE_NONE)
        {
            WmBridge::JsonAppendNumber(payload, firstField, "remove_mode", static_cast<long long>(removeMode));
        }
        WmBridge::JsonEnd(payload);
        row.payloadJson = payload;

        WmBridge::EmitEvent(row);
    }
}

class wm_bridge_unit_script : public UnitScript
{
public:
    wm_bridge_unit_script() : UnitScript("wm_bridge_unit_script", true, {
        UNITHOOK_ON_UNIT_DEATH,
        UNITHOOK_ON_AURA_APPLY,
        UNITHOOK_ON_AURA_REMOVE
    })
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

    void OnAuraApply(Unit* unit, Aura* aura) override
    {
        Player* player = unit ? unit->ToPlayer() : nullptr;
        if (!player)
        {
            return;
        }

        EmitPlayerAura(player, aura, "applied");
    }

    void OnAuraRemove(Unit* unit, AuraApplication* aurApp, AuraRemoveMode mode) override
    {
        Player* player = unit ? unit->ToPlayer() : nullptr;
        Aura const* aura = aurApp ? aurApp->GetBase() : nullptr;
        if (!player || !aura)
        {
            return;
        }

        SpellInfo const* spellInfo = aura->GetSpellInfo();
        uint32 spellId = spellInfo ? spellInfo->Id : aura->GetId();
        WmBridge::WMEffectRegistry::Instance().Unregister(
            player->GetGUID().GetCounter(), /*targetIsPlayer=*/true, spellId);

        EmitPlayerAura(player, aura, "removed", mode);
    }
};

void AddSC_mod_wm_bridge_unit_script()
{
    new wm_bridge_unit_script();
}
