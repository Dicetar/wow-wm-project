local ADDON_NAME = ...
local CHANNEL_NAME = "WMBridgePrivate"
local USER_CHANNEL_NAME = "WM"
local PREFIX = "WMBRIDGE"
local MARKER = "WMB1"
local CHAT_TRIGGER = "towm"

local bridge = CreateFrame("Frame", "WMBridgeFrame")
local channelId = 0
local userChannelId = 0
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

local function trim(value)
  value = tostring(value or "")
  value = string.gsub(value, "^%s+", "")
  value = string.gsub(value, "%s+$", "")
  return value
end

local function stripRealm(name)
  if not name then
    return nil
  end
  name = tostring(name)
  local short = string.match(name, "^([^-]+)")
  return short or name
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

local function sendTowm(message, sourceChat)
  local playerName = UnitName("player")
  local playerGuid = lowGuid(UnitGUID("player"))
  if not playerName or not playerGuid or not message or message == "" then
    return false
  end
  return sendPayload(payload({
    MARKER,
    "type=TOWM",
    "player=" .. sanitize(playerName),
    "player_guid=" .. sanitize(playerGuid),
    "message=" .. sanitize(message),
    "source_chat=" .. sanitize(sourceChat or ""),
    "channel=" .. sanitize(CHANNEL_NAME),
    "transport=" .. sanitize(activeTransport),
    "ts=" .. nowMillis(),
  }))
end

local function extractTowmMessage(message)
  local text = trim(message)
  local lowered = string.lower(text)
  local trigger = CHAT_TRIGGER .. " "
  if lowered == CHAT_TRIGGER then
    return ""
  end
  if string.sub(lowered, 1, string.len(trigger)) == trigger then
    return trim(string.sub(text, string.len(trigger) + 1))
  end
  return nil
end

local function channelArgsContainWmChannel(...)
  for index = 1, select("#", ...) do
    local value = select(index, ...)
    if type(value) == "string" then
      local lowered = string.lower(value)
      if lowered == "wm" or lowered == "worldmaster" or lowered == "world master" then
        return true
      end
    end
  end
  return false
end

local function ensureUserChannel()
  local existingId = GetChannelName(USER_CHANNEL_NAME)
  if type(existingId) == "number" and existingId > 0 then
    userChannelId = existingId
    return true
  end

  if JoinTemporaryChannel then
    JoinTemporaryChannel(USER_CHANNEL_NAME)
  elseif JoinChannelByName then
    JoinChannelByName(USER_CHANNEL_NAME)
  end

  local joinedId = GetChannelName(USER_CHANNEL_NAME)
  if type(joinedId) == "number" and joinedId > 0 then
    userChannelId = joinedId
    return true
  end
  userChannelId = 0
  return false
end

local function handlePlayerChat(event, message, author, ...)
  local playerName = UnitName("player")
  if not playerName or stripRealm(author) ~= playerName then
    return
  end

  local text = extractTowmMessage(message)
  if text == nil and event == "CHAT_MSG_CHANNEL" and channelArgsContainWmChannel(...) then
    text = trim(message)
  end
  if text == nil then
    return
  end
  if text == "" then
    DEFAULT_CHAT_FRAME:AddMessage("WMBridge: type 'towm <message>' in chat.")
    return
  end

  ensureChannel()
  if sendTowm(text, event) then
    DEFAULT_CHAT_FRAME:AddMessage("WMBridge: chat sent to WM")
  else
    DEFAULT_CHAT_FRAME:AddMessage("WMBridge: failed to send chat to WM")
  end
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
    ensureUserChannel()
    armHello()
    return
  end
  if event == "PLAYER_ENTERING_WORLD" then
    ensureChannel()
    ensureUserChannel()
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
  if event == "CHAT_MSG_SAY"
      or event == "CHAT_MSG_YELL"
      or event == "CHAT_MSG_PARTY"
      or event == "CHAT_MSG_RAID"
      or event == "CHAT_MSG_GUILD"
      or event == "CHAT_MSG_OFFICER"
      or event == "CHAT_MSG_WHISPER"
      or event == "CHAT_MSG_CHANNEL" then
    handlePlayerChat(event, ...)
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
bridge:RegisterEvent("CHAT_MSG_SAY")
bridge:RegisterEvent("CHAT_MSG_YELL")
bridge:RegisterEvent("CHAT_MSG_PARTY")
bridge:RegisterEvent("CHAT_MSG_RAID")
bridge:RegisterEvent("CHAT_MSG_GUILD")
bridge:RegisterEvent("CHAT_MSG_OFFICER")
bridge:RegisterEvent("CHAT_MSG_WHISPER")
bridge:RegisterEvent("CHAT_MSG_CHANNEL")

ChatFrame_AddMessageEventFilter("CHAT_MSG_CHANNEL_NOTICE", filterChannelNoise)
ChatFrame_AddMessageEventFilter("CHAT_MSG_CHANNEL_NOTICE_USER", filterChannelNoise)
ChatFrame_AddMessageEventFilter("CHAT_MSG_SYSTEM", filterChannelNoise)
ChatFrame_AddMessageEventFilter("CHAT_MSG_ADDON", filterAddonNoise)

SLASH_WMBRIDGE1 = "/wmbridge"
SlashCmdList["WMBRIDGE"] = function(msg)
  local raw = string.gsub(msg or "", "^%s+", "")
  local command = string.lower(raw)
  if command == "test" then
    ensureChannel()
    if sendHello() then
      DEFAULT_CHAT_FRAME:AddMessage("WMBridge: test HELLO sent via " .. activeTransport)
    else
      DEFAULT_CHAT_FRAME:AddMessage("WMBridge: failed to send test HELLO")
    end
    return
  end
  if string.sub(command, 1, 5) == "towm " then
    local text = string.gsub(string.sub(raw, 6), "^%s+", "")
    ensureChannel()
    if sendTowm(text, "SLASH_WMBRIDGE") then
      DEFAULT_CHAT_FRAME:AddMessage("WMBridge: sent to WM")
    else
      DEFAULT_CHAT_FRAME:AddMessage("WMBridge: failed to send to WM")
    end
    return
  end
  DEFAULT_CHAT_FRAME:AddMessage("WMBridge commands: /wmbridge test. Chat trigger: towm <message>")
end

SLASH_TOWM1 = "/towm"
SlashCmdList["TOWM"] = function(msg)
  local text = string.gsub(msg or "", "^%s+", "")
  if text == "" then
    DEFAULT_CHAT_FRAME:AddMessage("Usage: /towm <message>")
    return
  end
  ensureChannel()
  if sendTowm(text, "SLASH_TOWM") then
    DEFAULT_CHAT_FRAME:AddMessage("WMBridge: sent to WM")
  else
    DEFAULT_CHAT_FRAME:AddMessage("WMBridge: failed to send to WM")
  end
end

SLASH_WM1 = "/wm"
SlashCmdList["WM"] = function(msg)
  local text = trim(msg or "")
  if text == "" then
    DEFAULT_CHAT_FRAME:AddMessage("Usage: /wm <message> or /join WM and type in that channel.")
    return
  end
  if not ensureUserChannel() or userChannelId == 0 then
    DEFAULT_CHAT_FRAME:AddMessage("WMBridge: could not join WM channel. Use /join WM and try again.")
    return
  end
  local ok = pcall(SendChatMessage, text, "CHANNEL", nil, userChannelId)
  if not ok then
    DEFAULT_CHAT_FRAME:AddMessage("WMBridge: failed to send to WM channel")
  end
end
