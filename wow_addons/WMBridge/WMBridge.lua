local ADDON_NAME = ...
local CHANNEL_NAME = "WMBridgePrivate"
local USER_CHANNEL_NAME = "WM"
local PREFIX = "WMBRIDGE"
local MARKER = "WMB1"
local CHAT_TRIGGER = "towm"
local ENCHANTING_STONE_ITEM_ENTRY = 910015

local bridge = CreateFrame("Frame", "WMBridgeFrame")
local channelId = 0
local userChannelId = 0
local helloPending = false
local helloElapsed = 0
local helloAttempts = 0
local activeTransport = "NONE"
local stoneFrame = nil
local stoneSlot = nil
local stoneStatus = nil
local stoneSelectedTarget = nil
local stonePendingPickup = nil
local stoneSuppressPickup = false

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

local function sendPrivatePayload(rawPayload)
  local playerName = UnitName("player")
  if not playerName or playerName == "" then
    return false
  end
  local ok = pcall(SendAddonMessage, PREFIX, rawPayload, "WHISPER", playerName)
  return ok and true or false
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

local function parseBridgePayload(rawPayload)
  local text = tostring(rawPayload or "")
  local prefixed = PREFIX .. "\t"
  if string.sub(text, 1, string.len(prefixed)) == prefixed then
    text = string.sub(text, string.len(prefixed) + 1)
  end
  local marker = MARKER .. "|"
  if string.sub(text, 1, string.len(marker)) ~= marker then
    return nil
  end

  local fields = {}
  for field in string.gmatch(string.sub(text, string.len(marker) + 1), "([^|]+)") do
    local key, value = string.match(field, "^([^=]+)=(.*)$")
    if key then
      fields[key] = value or ""
    end
  end
  return fields
end

local function stoneTargetLabel(target)
  if not target then
    return "Empty"
  end
  return target.link or "Selected item"
end

local function stoneTargetTexture(target)
  if not target then
    return "Interface\\Icons\\INV_Misc_QuestionMark"
  end
  if target.loc == "BAG" then
    local texture = GetContainerItemInfo(target.bag, target.slot)
    return texture or "Interface\\Icons\\INV_Misc_QuestionMark"
  end
  if target.loc == "EQUIP" then
    return GetInventoryItemTexture("player", target.clientSlot) or "Interface\\Icons\\INV_Misc_QuestionMark"
  end
  return "Interface\\Icons\\INV_Misc_QuestionMark"
end

local function updateStoneSlot()
  if not stoneSlot then
    return
  end
  stoneSlot.icon:SetTexture(stoneTargetTexture(stoneSelectedTarget))
  stoneSlot.label:SetText(stoneTargetLabel(stoneSelectedTarget))
end

local function restoreCursorFromStonePickup()
  if not stonePendingPickup then
    ClearCursor()
    return
  end

  stoneSuppressPickup = true
  if stonePendingPickup.loc == "BAG" then
    PickupContainerItem(stonePendingPickup.bag, stonePendingPickup.slot)
  elseif stonePendingPickup.loc == "EQUIP" then
    PickupInventoryItem(stonePendingPickup.clientSlot)
  end
  stoneSuppressPickup = false
  ClearCursor()
end

local function selectStoneTargetFromPending()
  if not stonePendingPickup then
    if stoneStatus then
      stoneStatus:SetText("No item selected.")
    end
    ClearCursor()
    return
  end

  local target = {
    loc = stonePendingPickup.loc,
    bag = stonePendingPickup.bag or 0,
    slot = stonePendingPickup.slot,
    clientSlot = stonePendingPickup.clientSlot,
  }

  if target.loc == "BAG" then
    target.link = GetContainerItemLink(target.bag, target.slot)
  elseif target.loc == "EQUIP" then
    target.link = GetInventoryItemLink("player", target.clientSlot)
  end

  stoneSelectedTarget = target
  restoreCursorFromStonePickup()
  stonePendingPickup = nil
  updateStoneSlot()
  if stoneStatus then
    stoneStatus:SetText("Ready.")
  end
end

local function ensureStoneFrame()
  if stoneFrame then
    return stoneFrame
  end

  stoneFrame = CreateFrame("Frame", "WMEnchantingStoneFrame", UIParent)
  stoneFrame:SetWidth(300)
  stoneFrame:SetHeight(190)
  stoneFrame:SetPoint("CENTER")
  stoneFrame:SetFrameStrata("DIALOG")
  stoneFrame:SetMovable(true)
  stoneFrame:EnableMouse(true)
  stoneFrame:RegisterForDrag("LeftButton")
  stoneFrame:SetScript("OnDragStart", function(self) self:StartMoving() end)
  stoneFrame:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() end)
  stoneFrame:SetBackdrop({
    bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
    edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
    tile = true,
    tileSize = 32,
    edgeSize = 32,
    insets = { left = 11, right = 12, top = 12, bottom = 11 },
  })

  local title = stoneFrame:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  title:SetPoint("TOP", 0, -18)
  title:SetText("Enchanting Stone")

  stoneSlot = CreateFrame("Button", "WMEnchantingStoneItemSlot", stoneFrame)
  stoneSlot:SetWidth(58)
  stoneSlot:SetHeight(58)
  stoneSlot:SetPoint("TOP", 0, -54)
  stoneSlot:RegisterForClicks("LeftButtonUp", "RightButtonUp")
  stoneSlot:RegisterForDrag("LeftButton")
  stoneSlot:SetNormalTexture("Interface\\Buttons\\UI-Quickslot2")
  stoneSlot:SetPushedTexture("Interface\\Buttons\\UI-Quickslot-Depress")
  stoneSlot:SetHighlightTexture("Interface\\Buttons\\ButtonHilight-Square")
  stoneSlot.icon = stoneSlot:CreateTexture(nil, "ARTWORK")
  stoneSlot.icon:SetWidth(42)
  stoneSlot.icon:SetHeight(42)
  stoneSlot.icon:SetPoint("CENTER")
  stoneSlot.label = stoneFrame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  stoneSlot.label:SetPoint("TOP", stoneSlot, "BOTTOM", 0, -7)
  stoneSlot.label:SetWidth(250)
  stoneSlot.label:SetJustifyH("CENTER")
  stoneSlot.label:SetText("Empty")
  stoneSlot:SetScript("OnReceiveDrag", selectStoneTargetFromPending)
  stoneSlot:SetScript("OnClick", function()
    if CursorHasItem and CursorHasItem() then
      selectStoneTargetFromPending()
    end
  end)
  stoneSlot:SetScript("OnEnter", function(self)
    if stoneSelectedTarget and stoneSelectedTarget.link then
      GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
      GameTooltip:SetHyperlink(stoneSelectedTarget.link)
      GameTooltip:Show()
    end
  end)
  stoneSlot:SetScript("OnLeave", function()
    GameTooltip:Hide()
  end)

  local upgrade = CreateFrame("Button", "WMEnchantingStoneUpgradeButton", stoneFrame, "UIPanelButtonTemplate")
  upgrade:SetWidth(92)
  upgrade:SetHeight(24)
  upgrade:SetPoint("BOTTOMLEFT", 52, 26)
  upgrade:SetText("Upgrade")
  upgrade:SetScript("OnClick", function()
    if not stoneSelectedTarget then
      stoneStatus:SetText("No item selected.")
      return
    end
    local sent = sendPrivatePayload(payload({
      MARKER,
      "type=STONE_UPGRADE",
      "loc=" .. sanitize(stoneSelectedTarget.loc),
      "bag=" .. sanitize(stoneSelectedTarget.bag or 0),
      "slot=" .. sanitize(stoneSelectedTarget.slot or 0),
      "entry=" .. ENCHANTING_STONE_ITEM_ENTRY,
      "ts=" .. nowMillis(),
    }))
    if sent then
      stoneStatus:SetText("Upgrading...")
    else
      stoneStatus:SetText("Upgrade command failed.")
    end
  end)

  local cancel = CreateFrame("Button", "WMEnchantingStoneCancelButton", stoneFrame, "UIPanelButtonTemplate")
  cancel:SetWidth(92)
  cancel:SetHeight(24)
  cancel:SetPoint("BOTTOMRIGHT", -52, 26)
  cancel:SetText("Cancel")
  cancel:SetScript("OnClick", function()
    stoneFrame:Hide()
  end)

  stoneStatus = stoneFrame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  stoneStatus:SetPoint("BOTTOM", 0, 58)
  stoneStatus:SetWidth(250)
  stoneStatus:SetJustifyH("CENTER")
  stoneStatus:SetText("Ready.")

  updateStoneSlot()
  stoneFrame:Hide()
  return stoneFrame
end

local function openStoneFrame()
  ensureStoneFrame()
  stoneSelectedTarget = nil
  stonePendingPickup = nil
  updateStoneSlot()
  stoneStatus:SetText("Ready.")
  stoneFrame:Show()
end

local function handleStoneResult(fields)
  ensureStoneFrame()
  stoneStatus:SetText(fields.message or "Done.")
  stoneFrame:Show()
end

local function handleAddonPayload(prefix, rawPayload)
  if prefix ~= PREFIX then
    return
  end
  local fields = parseBridgePayload(rawPayload)
  if not fields or not fields.type then
    return
  end
  if fields.type == "STONE_OPEN" then
    openStoneFrame()
    return
  end
  if fields.type == "STONE_RESULT" then
    handleStoneResult(fields)
    return
  end
end

hooksecurefunc("PickupContainerItem", function(bag, slot)
  if stoneSuppressPickup or not stoneFrame or not stoneFrame:IsShown() then
    return
  end
  stonePendingPickup = {
    loc = "BAG",
    bag = bag,
    slot = slot,
  }
end)

hooksecurefunc("PickupInventoryItem", function(slot)
  if stoneSuppressPickup or not stoneFrame or not stoneFrame:IsShown() then
    return
  end
  stonePendingPickup = {
    loc = "EQUIP",
    slot = slot - 1,
    clientSlot = slot,
  }
end)

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
  if event == "CHAT_MSG_ADDON" then
    handleAddonPayload(...)
    return
  end
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
bridge:RegisterEvent("CHAT_MSG_ADDON")

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
  if command == "stone" then
    openStoneFrame()
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
  DEFAULT_CHAT_FRAME:AddMessage("WMBridge commands: /wmbridge test, /wmbridge stone. Chat trigger: towm <message>")
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
