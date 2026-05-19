// Phase 0D: player-domain native WM action handlers. Bodies moved
// verbatim from wm_bridge_action_queue.cpp; shared infra lives in
// wm_bridge_action_support.h (WmBridge::detail). Registered via
// RegisterWmBridgePlayerActions from the queue bootstrap.

#include "Configuration/Config.h"
#include "DatabaseEnv.h"
#include "Cell.h"
#include "CellImpl.h"
#include "Creature.h"
#include "DBCStores.h"
#include "GameObject.h"
#include "GridNotifiers.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QueryResult.h"
#include "Random.h"
#include "ReputationMgr.h"
#include "SpellMgr.h"
#include "TemporarySummon.h"
#include "Unit.h"
#include "WorldSession.h"
#include "wm_bridge_action_registry.h"
#include "wm_bridge_action_support.h"
#include "wm_bridge_common.h"
#include "wm_bridge_json.h"
#include "wm_bridge_random_enchant.h"
#include "wm_effect_registry.h"

#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <initializer_list>
#include <limits>
#include <list>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace
{
    using WmBridge::EscapeForJson;
    using namespace WmBridge::detail;

    bool ResolvePowerType(std::string const& payloadJson, Player* player, Powers& power, std::string& errorText)
    {
        power = player ? player->getPowerType() : POWER_MANA;

        uint32 numericPower = 0;
        if (TryExtractAnyUInt32Field(payloadJson, {"power_type", "powerType"}, numericPower))
        {
            if (numericPower >= MAX_POWERS)
            {
                errorText = "invalid_power_type";
                return false;
            }
            power = static_cast<Powers>(numericPower);
            return true;
        }

        std::string rawPower = ExtractJsonStringField(payloadJson, "power_type");
        if (rawPower.empty())
        {
            rawPower = ExtractJsonStringField(payloadJson, "powerType");
        }
        std::transform(rawPower.begin(), rawPower.end(), rawPower.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });

        if (rawPower.empty() || rawPower == "active" || rawPower == "current")
        {
            return true;
        }
        if (rawPower == "mana")
        {
            power = POWER_MANA;
            return true;
        }
        if (rawPower == "rage")
        {
            power = POWER_RAGE;
            return true;
        }
        if (rawPower == "focus")
        {
            power = POWER_FOCUS;
            return true;
        }
        if (rawPower == "energy")
        {
            power = POWER_ENERGY;
            return true;
        }
        if (rawPower == "runic_power" || rawPower == "runic")
        {
            power = POWER_RUNIC_POWER;
            return true;
        }

        errorText = "invalid_power_type";
        return false;
    }

    uint32 ResolveRestoreAmount(
        std::string const& payloadJson,
        std::initializer_list<char const*> amountKeys,
        std::initializer_list<char const*> percentKeys,
        uint32 maximum)
    {
        uint32 amount = 0;
        if (TryExtractAnyUInt32Field(payloadJson, amountKeys, amount))
        {
            return amount;
        }

        uint32 percent = 0;
        if (TryExtractAnyUInt32Field(payloadJson, percentKeys, percent))
        {
            percent = std::clamp<uint32>(percent, 0, 100);
            return static_cast<uint32>((static_cast<uint64>(maximum) * percent) / 100);
        }

        return 0;
    }

    Unit* ResolvePlayerCastTarget(Player* player, std::string const& payloadJson, std::string& errorText)
    {
        std::string target = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "target"));
        if (target.empty())
        {
            target = NormalizedJsonToken(ExtractJsonStringField(payloadJson, "target_kind"));
        }

        if (target.empty() || target == "self" || target == "player")
        {
            return player;
        }

        if (target == "selected" || target == "selection" || target == "target" || target == "player_target")
        {
            Unit* selected = ObjectAccessor::GetUnit(*player, player->GetTarget());
            if (!selected)
            {
                errorText = "target_not_found";
                return nullptr;
            }
            return selected;
        }

        errorText = "unsupported_target";
        return nullptr;
    }

    bool ExecutePlayerApplyAura(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"spell_id", "spellId"}, spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }
        if (!sSpellMgr->GetSpellInfo(spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_spell", {}, {{"spell_id", spellId}}), "invalid_spell");
            return true;
        }

        Aura* aura = player->AddAura(spellId, player);
        if (!aura)
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "aura_not_applied", {}, {{"spell_id", spellId}, {"player_guid", playerGuid}}), "aura_not_applied");
            return true;
        }

        {
            std::string effectKind = ExtractJsonStringField(payloadJson, "effect_kind");
            uint32 durationSec = 0;
            TryExtractJsonUInt32Field(payloadJson, "duration_sec", durationSec);
            WmBridge::WMEffectRegistry::Instance().Register(
                playerGuid, playerGuid, /*targetIsPlayer=*/true,
                spellId, effectKind, "{}", durationSec);
        }

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "aura_applied", {}, {{"spell_id", spellId}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecutePlayerRemoveAura(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"spell_id", "spellId"}, spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }

        player->RemoveAurasDueToSpell(spellId);
        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "aura_removed", {}, {{"spell_id", spellId}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecutePlayerRestoreHealthPower(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }
        if (!player->IsAlive())
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "player_dead", {}, {{"player_guid", playerGuid}}), "player_dead");
            return true;
        }

        Powers power = POWER_MANA;
        std::string powerError;
        if (!ResolvePowerType(payloadJson, player, power, powerError))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, powerError), powerError);
            return true;
        }

        uint32 healthRestore = ResolveRestoreAmount(payloadJson, {"health", "health_amount", "healthAmount"}, {"health_percent", "healthPercent"}, player->GetMaxHealth());
        uint32 powerRestore = ResolveRestoreAmount(payloadJson, {"power", "power_amount", "powerAmount", "mana", "mana_amount", "manaAmount"}, {"power_percent", "powerPercent", "mana_percent", "manaPercent"}, player->GetMaxPower(power));
        if (healthRestore == 0 && powerRestore == 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_restore_amount"), "missing_restore_amount");
            return true;
        }

        uint32 healthBefore = player->GetHealth();
        uint32 powerBefore = player->GetPower(power);
        uint32 healthAfter = std::min<uint32>(player->GetMaxHealth(), healthBefore + healthRestore);
        uint32 powerAfter = std::min<uint32>(player->GetMaxPower(power), powerBefore + powerRestore);
        player->SetHealth(healthAfter);
        player->SetPower(power, powerAfter);

        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "health_power_restored",
                {},
                {
                    {"player_guid", playerGuid},
                    {"health_before", healthBefore},
                    {"health_after", healthAfter},
                    {"power_type", static_cast<long long>(power)},
                    {"power_before", powerBefore},
                    {"power_after", powerAfter},
                }));
        return true;
    }

    bool ExecutePlayerAddMoney(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        int32 copper = 0;
        if (!TryExtractAnyInt32Field(payloadJson, {"copper", "amount", "money"}, copper) || copper <= 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_positive_copper"), "missing_positive_copper");
            return true;
        }
        if (!player->ModifyMoney(copper))
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "money_not_added", {}, {{"copper", copper}, {"player_guid", playerGuid}}), "money_not_added");
            return true;
        }

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "money_added", {}, {{"copper", copper}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecutePlayerAddReputation(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 factionId = 0;
        int32 value = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"faction_id", "factionId"}, factionId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_faction_id"), "missing_faction_id");
            return true;
        }
        if (!TryExtractAnyInt32Field(payloadJson, {"value", "amount", "reputation"}, value) || value == 0)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_reputation_value"), "missing_reputation_value");
            return true;
        }

        FactionEntry const* faction = sFactionStore.LookupEntry(factionId);
        if (!faction)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_faction", {}, {{"faction_id", factionId}}), "invalid_faction");
            return true;
        }

        bool noSpillover = true;
        TryExtractAnyBoolField(payloadJson, {"no_spillover", "noSpillover"}, noSpillover);
        if (!player->GetReputationMgr().ModifyReputation(faction, static_cast<float>(value), noSpillover))
        {
            CompleteAction(requestId, "failed", actionKind, ActionResultJson("failed", actionKind, "reputation_not_added", {}, {{"faction_id", factionId}, {"value", value}}), "reputation_not_added");
            return true;
        }

        CompleteAction(requestId, "done", actionKind, ActionResultJson("done", actionKind, "reputation_added", {}, {{"faction_id", factionId}, {"value", value}, {"player_guid", playerGuid}}));
        return true;
    }

    bool ExecutePlayerCastSpell(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, actionKind, payloadJson, player))
        {
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractAnyUInt32Field(payloadJson, {"spell_id", "spellId"}, spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }
        if (!sSpellMgr->GetSpellInfo(spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, "invalid_spell", {}, {{"spell_id", spellId}}), "invalid_spell");
            return true;
        }

        std::string targetError;
        Unit* target = ResolvePlayerCastTarget(player, payloadJson, targetError);
        if (!target)
        {
            CompleteAction(requestId, "rejected", actionKind, ActionResultJson("rejected", actionKind, targetError), targetError);
            return true;
        }

        bool triggered = ResolveTriggeredCastFlag(payloadJson);
        player->CastSpell(target, spellId, triggered);
        CompleteAction(
            requestId,
            "done",
            actionKind,
            ActionResultJson(
                "done",
                actionKind,
                "spell_cast",
                {{"target_guid", target->GetGUID().ToString()}},
                {{"spell_id", spellId}, {"player_guid", playerGuid}},
                {{"target_distance", player->GetDistance(target)}}));
        return true;
    }

    bool ExecutePlayerLearnSpell(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (!player)
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractJsonUInt32Field(payloadJson, "spell_id", spellId) &&
            !TryExtractJsonUInt32Field(payloadJson, "spellId", spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }

        if (!sSpellMgr->GetSpellInfo(spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "invalid_spell"), "invalid_spell");
            return true;
        }

        if (player->HasSpell(spellId))
        {
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "already_known"));
            return true;
        }

        player->learnSpell(spellId, false, false);
        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "spell_learned"));
        return true;
    }

    bool ExecutePlayerUnlearnSpell(uint64 requestId, uint32 playerGuid, std::string const& actionKind, std::string const& payloadJson)
    {
        Player* player = ObjectAccessor::FindPlayerByLowGUID(playerGuid);
        if (!player)
        {
            CompleteAction(requestId, "failed", actionKind, ResultJson("failed", actionKind, "player_not_online"), "player_not_online");
            return true;
        }

        uint32 spellId = 0;
        if (!TryExtractJsonUInt32Field(payloadJson, "spell_id", spellId) &&
            !TryExtractJsonUInt32Field(payloadJson, "spellId", spellId))
        {
            CompleteAction(requestId, "rejected", actionKind, ResultJson("rejected", actionKind, "missing_spell_id"), "missing_spell_id");
            return true;
        }

        if (!player->HasSpell(spellId))
        {
            CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "already_absent"));
            return true;
        }

        player->removeSpell(spellId, SPEC_MASK_ALL, false);
        CompleteAction(requestId, "done", actionKind, ResultJson("done", actionKind, "spell_unlearned"));
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgePlayerActions(ActionRegistry& registry)
    {
        registry.Register("player_apply_aura", &ExecutePlayerApplyAura);
        registry.Register("player_remove_aura", &ExecutePlayerRemoveAura);
        registry.Register("player_restore_health_power", &ExecutePlayerRestoreHealthPower);
        registry.Register("player_add_money", &ExecutePlayerAddMoney);
        registry.Register("player_add_reputation", &ExecutePlayerAddReputation);
        registry.Register("player_cast_spell", &ExecutePlayerCastSpell);
        registry.Register("player_learn_spell", &ExecutePlayerLearnSpell);
        registry.Register("player_unlearn_spell", &ExecutePlayerUnlearnSpell);
    }
}
