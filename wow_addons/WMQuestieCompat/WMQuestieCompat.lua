local ADDON_NAME = ...

local function shouldSuppress(message)
    if type(message) ~= "string" then
        return false, nil
    end

    local questId = message:match("^Missing quest (%d+),%d+ during tracker update$")
    if not questId then
        return false, nil
    end

    local numericQuestId = tonumber(questId)
    if not numericQuestId or numericQuestId < 900000 then
        return false, nil
    end

    return true, numericQuestId
end

local function markQuestieCustomQuestIgnored(questId)
    if not Questie or not Questie.db or not Questie.db.char then
        return
    end

    if Questie.db.char.TrackedQuests then
        Questie.db.char.TrackedQuests[questId] = nil
    end

    if Questie.db.char.AutoUntrackedQuests then
        Questie.db.char.AutoUntrackedQuests[questId] = true
    end
end

local function patchQuestie()
    if not Questie or type(Questie.Error) ~= "function" or Questie._wmQuestieCompatPatched then
        return
    end

    local originalError = Questie.Error
    Questie.Error = function(self, ...)
        local parts = {...}
        local message = table.concat(parts, " ")
        local suppress, questId = shouldSuppress(message)
        if suppress then
            markQuestieCustomQuestIgnored(questId)
            return
        end

        return originalError(self, ...)
    end

    Questie._wmQuestieCompatPatched = true
end

local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_LOGIN")
frame:SetScript("OnEvent", function(_, event, arg1)
    if event == "ADDON_LOADED" and arg1 ~= "Questie-335" and arg1 ~= ADDON_NAME then
        return
    end

    patchQuestie()
end)

patchQuestie()
