local ADDON_NAME = ...
local CHANNEL_NAME = "WMBridgePrivate"
local PREFIX = "WMBRIDGE"
local MARKER = "WMB1"

local bridge = CreateFrame("Frame", "WMBridgeFrame")
local channelId = 0
local helloPending = false
local helloElapsed = 0
local helloAttempts = 0
local activeTransport = "NONE"

local function nowMillis()
  local coarse = time() * 1000
  local fractional = math.floor((GetTime() - math.floor(GetTime())) * 1000)
  return tostring(coarse + fractional)
end

local function sanitize(value)
  if value == nil then
    return ""
  end
  value = tostring(value)
  value = string.gsub(value, "|", "/")
  value = string.gsub(value, "\r", " ")
  value = string.gsub(value, "\n", " ")
  return value
end

local function lowGuid(unitGuid)
  if not unitGuid or unitGuid == "" then
    return nil
  end
  local hex = string.gsub(unitGuid, "^0x", "")
  local trimmed = string.gsub(hex, "^0+", "")
  if trimmed == "" then
    trimmed = "0"
  end
  return tonumber(trimmed, 16)
end

local function payload(parts)
  return table.concat(parts, "|")
end

local function removeChannelFromFrames()
  for index = 1, NUM_CHAT_WINDOWS do
    local frame = _G["ChatFrame" .. index]
    if frame then
      ChatFrame_RemoveChannel(frame, CHANNEL_NAME)
    end
  end
end

local function channelNoticeMatches(...)
  for index = 1, select("#", ...) do
    local value = select(index, ...)
    if type(value) == "string" and string.find(string.lower(value), string.lower(CHANNEL_NAME), 1, true) then
      return true
    end
  end
  return false
end

local function filterChannelNoise(self, event, ...)
  if channelNoticeMatches(...) then
    return true
  end
  return false
end

local function filterAddonNoise(self, event, prefix, message, channel, sender, ...)
  if prefix == PREFIX then
    return true
  end
  if channelNoticeMatches(channel, sender, message, ...) then
    return true
  end
  return false
end

local function ensureChannel()
  local existingId = GetChannelName(CHANNEL_NAME)
  if type(existingId) == "number" and existingId > 0 then
    channelId = existingId
    activeTransport = "CHANNEL"
    removeChannelFromFrames()
    return true
  end

  if JoinTemporaryChannel then
    JoinTemporaryChannel(CHANNEL_NAME)
  elseif JoinChannelByName then
    JoinChannelByName(CHANNEL_NAME)
  end

  local joinedId = GetChannelName(CHANNEL_NAME)
  if type(joinedId) == "number" and joinedId > 0 then
    channelId = joinedId
    activeTransport = "CHANNEL"
    removeChannelFromFrames()
    return true
  end
  channelId = 0
  activeTransport = "NONE"
  return false
end

local function sendPayload(rawPayload)
  if channelId == 0 then
    ensureChannel()
  end

  if channelId > 0 then
    local ok = pcall(SendAddonMessage, PREFIX, rawPayload, "CHANNEL", channelId)
    if ok then
      activeTransport = "CHANNEL"
      return true
    end
  end

  local playerName = UnitName("player")
  if playerName and playerName ~= "" then
    local ok = pcall(SendAddonMessage, PREFIX, rawPayload, "WHISPER", playerName)
    if ok then
      activeTransport = "SELF_WHISPER"
      return true
    end
  end

  activeTransport = "NONE"
  return false
end

local function sendHello()
  local playerName = UnitName("player")
  local playerGuid = lowGuid(UnitGUID("player"))
  if not playerName or not playerGuid then
    return false
  end
  return sendPayload(payload({
    MARKER,
    "type=HELLO",
    "player=" .. sanitize(playerName),
    "player_guid=" .. sanitize(playerGuid),
    "channel=" .. sanitize(CHANNEL_NAME),
    "transport=" .. sanitize(activeTransport),
    "ts=" .. nowMillis(),
  }))
end

local function sendKill(targetName, targetGuid, subevent)
  local playerName = UnitName("player")
  local playerGuid = lowGuid(UnitGUID("player"))
  if not playerName or not playerGuid or not targetName then
    return
  end
  sendPayload(payload({
    MARKER,
    "type=KILL",
    "player=" .. sanitize(playerName),
    "player_guid=" .. sanitize(playerGuid),
    "target=" .. sanitize(targetName),
    "target_guid=" .. sanitize(targetGuid or ""),
    "subevent=" .. sanitize(subevent or "PARTY_KILL"),
    "channel=" .. sanitize(CHANNEL_NAME),
    "transport=" .. sanitize(activeTransport),
    "ts=" .. nowMillis(),
  }))
end

local function armHello()
  helloPending = true
  helloElapsed = 0
  helloAttempts = 0
end

local function handleCombatLog(...)
  local timestamp, subevent, sourceGuid, sourceName, sourceFlags, destGuid, destName, destFlags = ...
  if not subevent then
    return
  end
  if subevent ~= "PARTY_KILL" then
    return
  end
  local playerName = UnitName("player")
  if not playerName or sourceName ~= playerName then
    return
  end
  sendKill(destName, destGuid, subevent)
end

bridge:SetScript("OnEvent", function(self, event, ...)
  if event == "PLAYER_LOGIN" then
    ensureChannel()
    armHello()
    return
  end
  if event == "PLAYER_ENTERING_WORLD" then
    ensureChannel()
    armHello()
    return
  end
  if event == "CHAT_MSG_CHANNEL_NOTICE" or event == "CHAT_MSG_CHANNEL_NOTICE_USER" then
    ensureChannel()
    return
  end
  if event == "COMBAT_LOG_EVENT_UNFILTERED" then
    handleCombatLog(...)
    return
  end
end)

bridge:SetScript("OnUpdate", function(self, elapsed)
  if not helloPending then
    return
  end
  helloElapsed = helloElapsed + elapsed
  if helloElapsed < 0.5 then
    return
  end
  helloElapsed = 0
  helloAttempts = helloAttempts + 1
  if sendHello() then
    helloPending = false
    return
  end
  if helloAttempts >= 10 then
    helloPending = false
  end
end)

bridge:RegisterEvent("PLAYER_LOGIN")
bridge:RegisterEvent("PLAYER_ENTERING_WORLD")
bridge:RegisterEvent("CHAT_MSG_CHANNEL_NOTICE")
bridge:RegisterEvent("CHAT_MSG_CHANNEL_NOTICE_USER")
bridge:RegisterEvent("COMBAT_LOG_EVENT_UNFILTERED")

ChatFrame_AddMessageEventFilter("CHAT_MSG_CHANNEL_NOTICE", filterChannelNoise)
ChatFrame_AddMessageEventFilter("CHAT_MSG_CHANNEL_NOTICE_USER", filterChannelNoise)
ChatFrame_AddMessageEventFilter("CHAT_MSG_SYSTEM", filterChannelNoise)
ChatFrame_AddMessageEventFilter("CHAT_MSG_ADDON", filterAddonNoise)

SLASH_WMBRIDGE1 = "/wmbridge"
SlashCmdList["WMBRIDGE"] = function(msg)
  local command = string.lower(string.gsub(msg or "", "^%s+", ""))
  if command == "test" then
    ensureChannel()
    if sendHello() then
      DEFAULT_CHAT_FRAME:AddMessage("WMBridge: test HELLO sent via " .. activeTransport)
    else
      DEFAULT_CHAT_FRAME:AddMessage("WMBridge: failed to send test HELLO")
    end
    return
  end
  DEFAULT_CHAT_FRAME:AddMessage("WMBridge commands: /wmbridge test")
end
