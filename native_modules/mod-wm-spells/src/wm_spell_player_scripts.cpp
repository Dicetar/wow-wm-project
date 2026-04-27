#include "Chat.h"
#include "ScriptMgr.h"
#include "Item.h"
#include "Player.h"
#include "wm_spell_runtime.h"

#include <algorithm>
#include <cctype>
#include <optional>
#include <string>
#include <unordered_map>

namespace
{
    constexpr uint32 BONEBOUND_MAINTENANCE_INTERVAL_MS = 1000;
    std::unordered_map<uint32, uint32> gBoneboundMaintenanceTimers;

    struct EchoModeCommand
    {
        std::string mode;
        std::optional<float> huntRadius;
        bool rangeOnly = false;
        bool teleportOnly = false;
        std::string error;
    };

    std::string NormalizeEchoCommand(std::string value)
    {
        value.erase(
            value.begin(),
            std::find_if(value.begin(), value.end(), [](unsigned char ch) { return !std::isspace(ch); }));
        value.erase(
            std::find_if(value.rbegin(), value.rend(), [](unsigned char ch) { return !std::isspace(ch); }).base(),
            value.end());
        std::transform(
            value.begin(),
            value.end(),
            value.begin(),
            [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
        return value;
    }

    bool IsEchoModeAlias(std::string const& value)
    {
        return value == "seek"
            || value == "hunt"
            || value == "attack"
            || value == "aggressive"
            || value == "follow"
            || value == "close"
            || value == "guard"
            || value == "passive"
            || value == "teleport"
            || value == "tp"
            || value == "recall";
    }

    std::optional<float> TryParseEchoHuntRadius(std::string const& value)
    {
        std::string normalized = NormalizeEchoCommand(value);
        if (normalized.empty())
            return std::nullopt;

        size_t parsed = 0;
        try
        {
            float radius = std::stof(normalized, &parsed);
            if (parsed != normalized.size() || radius <= 0.0f)
                return std::nullopt;
            return std::clamp(radius, 5.0f, 100.0f);
        }
        catch (...)
        {
            return std::nullopt;
        }
    }

    bool TryParseEchoModeCommand(std::string const& rawMessage, EchoModeCommand& command)
    {
        std::string normalized = NormalizeEchoCommand(rawMessage);
        for (std::string const& prefix : {"#wm echo ", "wm echo ", "#wm echoes ", "wm echoes ", "echo "})
        {
            if (normalized.rfind(prefix, 0) == 0)
            {
                std::string body = NormalizeEchoCommand(normalized.substr(prefix.size()));
                size_t split = body.find(' ');
                std::string first = split == std::string::npos ? body : body.substr(0, split);
                std::string rest = split == std::string::npos ? "" : NormalizeEchoCommand(body.substr(split + 1));

                if (first == "range" || first == "radius")
                {
                    command.rangeOnly = true;
                    command.huntRadius = TryParseEchoHuntRadius(rest);
                    if (!command.huntRadius.has_value())
                        command.error = "invalid_echo_hunt_radius";
                    return true;
                }

                if (first == "teleport" || first == "tp" || first == "recall")
                {
                    command.teleportOnly = true;
                    command.mode = first;
                    return true;
                }

                if (!IsEchoModeAlias(first))
                    return false;

                command.mode = first;
                if (!rest.empty())
                {
                    command.huntRadius = TryParseEchoHuntRadius(rest);
                    if (!command.huntRadius.has_value())
                        command.error = "invalid_echo_hunt_radius";
                }
                return true;
            }
        }

        return false;
    }

    bool HandleEchoModeChatCommand(Player* player, std::string const& msg)
    {
        if (!player)
            return false;

        EchoModeCommand command;
        if (!TryParseEchoModeCommand(msg, command))
            return false;

        ChatHandler handler(player->GetSession());
        if (!command.error.empty())
        {
            handler.PSendSysMessage("WM Echoes: range must be a number from 5 to 100 yards.");
            return true;
        }

        WmSpells::BehaviorExecutionResult result = command.teleportOnly
            ? WmSpells::ExecuteBoneboundEchoTeleport(player)
            : (command.rangeOnly
                ? WmSpells::ExecuteBoneboundEchoSeekRange(player, *command.huntRadius)
                : WmSpells::ExecuteBoneboundEchoMode(player, command.mode, command.huntRadius));
        if (!result.ok)
        {
            handler.PSendSysMessage("WM Echoes: mode change failed ({})", result.message);
            return true;
        }

        if (command.teleportOnly)
            handler.PSendSysMessage("WM Echoes: teleported to your position.");
        else if (command.rangeOnly)
            handler.PSendSysMessage("WM Echoes: seek range set to {:.1f} yards.", *command.huntRadius);
        else if (result.message.rfind("bonebound_echo_mode_hunt", 0) == 0)
        {
            if (command.huntRadius.has_value())
                handler.PSendSysMessage("WM Echoes: seek mode enabled at {:.1f} yards.", *command.huntRadius);
            else
                handler.PSendSysMessage("WM Echoes: seek mode enabled. Echo Destroyers will attack the nearest eligible hostile in range.");
        }
        else
            handler.PSendSysMessage("WM Echoes: follow mode enabled. Echo Destroyers return to close guard behavior.");
        return true;
    }
}

class wm_spells_player_script : public PlayerScript
{
public:
    wm_spells_player_script() : PlayerScript("wm_spells_player_script")
    {
    }

    void OnPlayerLogin(Player* player) override
    {
        if (!player)
            return;

        gBoneboundMaintenanceTimers[static_cast<uint32>(player->GetGUID().GetCounter())] = 0;
        WmSpells::MaintainBoneboundSummons(player);
        WmSpells::MaintainIntellectBlockPassive(player);
        WmSpells::MaintainCombatProficiencies(player);
        WmSpells::MaintainNightWatchersLens(player, 0);
    }

    void OnPlayerAfterUpdate(Player* player, uint32 diff) override
    {
        if (!player)
            return;

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        uint32& timer = gBoneboundMaintenanceTimers[ownerGuid];
        if (timer > diff)
        {
            timer -= diff;
            return;
        }

        timer = BONEBOUND_MAINTENANCE_INTERVAL_MS;
        WmSpells::MaintainBoneboundSummons(player);
        WmSpells::MaintainIntellectBlockPassive(player);
        WmSpells::MaintainCombatProficiencies(player);
        WmSpells::MaintainNightWatchersLens(player, BONEBOUND_MAINTENANCE_INTERVAL_MS);
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        if (!player)
            return;

        uint32 ownerGuid = static_cast<uint32>(player->GetGUID().GetCounter());
        gBoneboundMaintenanceTimers.erase(ownerGuid);
        WmSpells::ForgetBoneboundCompanions(player);
        WmSpells::ForgetIntellectBlockPassive(player);
        WmSpells::ForgetNightWatchersLens(player);
    }

    void OnPlayerEquip(Player* player, Item* item, uint8 /*bag*/, uint8 /*slot*/, bool /*update*/) override
    {
        if (!item || !item->GetTemplate() || item->GetTemplate()->ItemId != 910006)
            return;

        WmSpells::MaintainNightWatchersLens(player, 0);
    }

    void OnPlayerUnequip(Player* player, Item* item) override
    {
        if (!item || !item->GetTemplate() || item->GetTemplate()->ItemId != 910006)
            return;

        WmSpells::ForgetNightWatchersLens(player);
    }

    bool OnPlayerCanUseChat(Player* player, uint32 /*type*/, uint32 /*language*/, std::string& msg) override
    {
        return !HandleEchoModeChatCommand(player, msg);
    }

    bool OnPlayerCanUseChat(Player* player, uint32 /*type*/, uint32 /*language*/, std::string& msg, Player* /*receiver*/) override
    {
        return !HandleEchoModeChatCommand(player, msg);
    }

    bool OnPlayerCanUseChat(Player* player, uint32 /*type*/, uint32 /*language*/, std::string& msg, Group* /*group*/) override
    {
        return !HandleEchoModeChatCommand(player, msg);
    }

    bool OnPlayerCanUseChat(Player* player, uint32 /*type*/, uint32 /*language*/, std::string& msg, Guild* /*guild*/) override
    {
        return !HandleEchoModeChatCommand(player, msg);
    }

    bool OnPlayerCanUseChat(Player* player, uint32 /*type*/, uint32 /*language*/, std::string& msg, Channel* /*channel*/) override
    {
        return !HandleEchoModeChatCommand(player, msg);
    }

};

void AddSC_mod_wm_spells_player_scripts()
{
    new wm_spells_player_script();
}
