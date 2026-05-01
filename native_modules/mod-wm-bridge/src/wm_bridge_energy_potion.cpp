#include "DatabaseEnv.h"
#include "Item.h"
#include "ItemScript.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "Spell.h"
#include "SpellAuras.h"
#include "SpellMgr.h"
#include "WorldSession.h"
#include "wm_bridge_common.h"

#include <algorithm>
#include <sstream>
#include <unordered_map>

namespace
{
    constexpr uint32 WM_ENERGY_SURGE_POTION_ITEM_ENTRY = 910014;
    constexpr uint32 WM_ENERGY_SURGE_AURA_SPELL_ID = 946606;
    constexpr uint32 ENERGY_SURGE_DURATION_MS = 7200000;
    constexpr uint32 ENERGY_SURGE_TICK_MS = 1000;
    constexpr uint32 ENERGY_SURGE_ENERGY_PER_SECOND = 10;

    std::unordered_map<uint32, uint32> gEnergySurgeElapsedMsByPlayer;

    void SendPlayerMessage(Player* player, std::string const& message)
    {
        if (player && player->GetSession())
        {
            player->GetSession()->SendAreaTriggerMessage(message);
        }
    }

    uint32 PlayerLowGuid(Player const* player)
    {
        return player ? static_cast<uint32>(player->GetGUID().GetCounter()) : 0;
    }

    bool HasUsableEnergyBar(Player* player)
    {
        return player && player->getPowerType() == POWER_ENERGY && player->GetMaxPower(POWER_ENERGY) > 0;
    }

    Aura* ApplyEnergySurgeAura(Player* player)
    {
        if (!player || !sSpellMgr->GetSpellInfo(WM_ENERGY_SURGE_AURA_SPELL_ID))
        {
            return nullptr;
        }

        Aura* aura = player->GetAura(WM_ENERGY_SURGE_AURA_SPELL_ID, player->GetGUID());
        if (!aura)
        {
            aura = player->AddAura(WM_ENERGY_SURGE_AURA_SPELL_ID, player);
        }

        if (!aura)
        {
            return nullptr;
        }

        aura->SetMaxDuration(static_cast<int32>(ENERGY_SURGE_DURATION_MS));
        aura->SetDuration(static_cast<int32>(ENERGY_SURGE_DURATION_MS));
        return aura;
    }

    void ConsumePotion(Player* player, Item* item)
    {
        uint32 destroyCount = 1;
        player->DestroyItemCount(item, destroyCount, true);

        CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
        player->SaveInventoryAndGoldToDB(trans);
        CharacterDatabase.CommitTransaction(trans);
    }

    void TickEnergySurge(Player* player, uint32 diff)
    {
        if (!player)
        {
            return;
        }

        uint32 const playerGuid = PlayerLowGuid(player);
        if (!player->HasAura(WM_ENERGY_SURGE_AURA_SPELL_ID))
        {
            gEnergySurgeElapsedMsByPlayer.erase(playerGuid);
            return;
        }

        uint32& elapsedMs = gEnergySurgeElapsedMsByPlayer[playerGuid];
        elapsedMs += diff;
        uint32 const tickCount = elapsedMs / ENERGY_SURGE_TICK_MS;
        if (tickCount == 0)
        {
            return;
        }
        elapsedMs %= ENERGY_SURGE_TICK_MS;

        if (!HasUsableEnergyBar(player))
        {
            return;
        }

        uint32 const maxEnergy = player->GetMaxPower(POWER_ENERGY);
        uint32 const currentEnergy = player->GetPower(POWER_ENERGY);
        if (currentEnergy >= maxEnergy)
        {
            return;
        }

        uint32 const missingEnergy = maxEnergy - currentEnergy;
        uint32 const energyToRestore = std::min<uint32>(missingEnergy, tickCount * ENERGY_SURGE_ENERGY_PER_SECOND);
        if (energyToRestore > 0)
        {
            player->ModifyPower(POWER_ENERGY, static_cast<int32>(energyToRestore));
        }
    }
}

class wm_energy_surge_potion : public ItemScript
{
public:
    wm_energy_surge_potion() : ItemScript("wm_energy_surge_potion") { }

    bool OnUse(Player* player, Item* item, SpellCastTargets const& /*targets*/) override
    {
        if (!player || !item || item->GetEntry() != WM_ENERGY_SURGE_POTION_ITEM_ENTRY)
        {
            return true;
        }

        if (!WmBridge::IsPlayerAllowed(player))
        {
            SendPlayerMessage(player, "Energy Surge Potion is inactive for this character.");
            return true;
        }

        if (!HasUsableEnergyBar(player))
        {
            SendPlayerMessage(player, "Energy Surge Potion requires an active energy bar.");
            return true;
        }

        Aura* aura = ApplyEnergySurgeAura(player);
        if (!aura)
        {
            SendPlayerMessage(player, "Energy Surge is not staged on this server yet.");
            return true;
        }

        gEnergySurgeElapsedMsByPlayer[PlayerLowGuid(player)] = 0;
        ConsumePotion(player, item);

        std::ostringstream message;
        message << "Energy Surge active for 2 hours: +" << ENERGY_SURGE_ENERGY_PER_SECOND << " energy per second.";
        SendPlayerMessage(player, message.str());
        return true;
    }
};

class wm_energy_surge_player_script : public PlayerScript
{
public:
    wm_energy_surge_player_script() : PlayerScript("wm_energy_surge_player_script") { }

    void OnPlayerAfterUpdate(Player* player, uint32 diff) override
    {
        TickEnergySurge(player, diff);
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        gEnergySurgeElapsedMsByPlayer.erase(PlayerLowGuid(player));
    }
};

void AddSC_mod_wm_bridge_energy_potion()
{
    new wm_energy_surge_potion();
    new wm_energy_surge_player_script();
}
