param(
    [string]$RunRoot = "D:\WOW\Azerothcore_WoTLK_Rebuild\run",
    [int]$AhbotAccount = 1,
    [int]$AhbotGuid = 1,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"

function Backup-ConfigFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Stamp
    )

    if ($NoBackup) {
        return
    }

    $backupPath = "$Path.bak.$Stamp"
    if (-not (Test-Path -LiteralPath $backupPath)) {
        Copy-Item -LiteralPath $Path -Destination $backupPath -Force
    }
}

function Set-OrAddConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Config file not found: $Path"
    }

    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($lineText in [System.IO.File]::ReadAllLines($Path)) {
        [void]$lines.Add($lineText)
    }
    $line = "$Key = $Value"
    $pattern = '^\s*' + [regex]::Escape($Key) + '\s*=.*$'
    $updated = $false

    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match $pattern) {
            if ($lines[$index] -ne $line) {
                $lines[$index] = $line
                $updated = $true
            }
            break
        }
    }

    if (-not ($lines -match $pattern)) {
        [void]$lines.Add($line)
        $updated = $true
    }

    if ($updated) {
        $encoding = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllLines($Path, $lines, $encoding)
    }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

$worldConfig = Join-Path $RunRoot "configs\worldserver.conf"
$ahbotConfig = Join-Path $RunRoot "configs\modules\mod_ahbot.conf"
$playerbotConfig = Join-Path $RunRoot "configs\modules\playerbots.conf"
$weatherVibeConfig = Join-Path $RunRoot "configs\modules\mod_weather_vibe.conf"
$dungeonMasterConfig = Join-Path $RunRoot "configs\modules\mod_dungeon_master.conf"

$targets = @(
    $worldConfig,
    $ahbotConfig,
    $playerbotConfig,
    $weatherVibeConfig,
    $dungeonMasterConfig
)

foreach ($target in $targets) {
    Backup-ConfigFile -Path $target -Stamp $stamp
}

$worldSettings = [ordered]@{
    "ActivateWeather"                  = "0"
    "Wintergrasp.SkipBattleSessionCount" = "3500"
}

$weatherVibeSettings = [ordered]@{
    "WeatherVibe.Announce"            = "1"
    "WeatherVibe.Profile.Enable"      = "1"
    "WeatherVibe.Profile.ReApply.PerSec" = "10"
}

$playerbotSettings = [ordered]@{
    "AiPlayerbot.LootNeedRollLevel"   = "1"
    "AiPlayerbot.LootGreedRollLevel"  = "0"
    "AiPlayerbot.LootRollRecipe"      = "0"
    "AiPlayerbot.LootRollDisenchant"  = "0"
}

$ahbotSettings = [ordered]@{
    "AuctionHouseBot.Account"                         = "$AhbotAccount"
    "AuctionHouseBot.GUID"                            = "$AhbotGuid"
    "AuctionHouseBot.GUIDs"                           = "$AhbotGuid"
    "AuctionHouseBot.EnableSeller"                    = "true"
    "AuctionHouseBot.EnableBuyer"                     = "1"
    "AuctionHouseBot.Buyer.Enabled"                   = "true"
    "AuctionHouseBot.MinutesBetweenBuyCycle"          = "1:3"
    "AuctionHouseBot.MinutesBetweenSellCycle"         = "1"
    "AuctionHouseBot.ItemsPerCycle"                   = "2000"
    "AuctionHouseBot.UseBuyPriceForSeller"            = "1"
    "AuctionHouseBot.UseBuyPriceForBuyer"             = "0"
    "AuctionHouseBot.UseMarketPriceForSeller"         = "1"
    "AuctionHouseBot.MarketResetThreshold"            = "10"
    "AuctionHouseBot.ConsiderOnlyBotAuctions"         = "1"
    "AuctionHouseBot.DuplicatesCount"                 = "0"
    "AuctionHouseBot.DivisibleStacks"                 = "1"
    "AuctionHouseBot.ElapsingTimeClass"               = "0"
    "AuctionHouseBot.ReturnExpiredAuctionItemsToBot"  = "false"
    "AuctionHouseBot.Alliance.MinItems"               = "0"
    "AuctionHouseBot.Alliance.MaxItems"               = "0"
    "AuctionHouseBot.Horde.MinItems"                  = "0"
    "AuctionHouseBot.Horde.MaxItems"                  = "0"
    "AuctionHouseBot.Neutral.MinItems"                = "40000"
    "AuctionHouseBot.Neutral.MaxItems"                = "40000"
    "AuctionHouseBot.BuyoutVariationReducePercent"    = "0.30"
    "AuctionHouseBot.BuyoutVariationAddPercent"       = "0.20"
    "AuctionHouseBot.BidVariationHighReducePercent"   = "0"
    "AuctionHouseBot.BidVariationLowReducePercent"    = "0.30"
    "AuctionHouseBot.Buyer.BuyCandidatesPerBuyCycle"  = "25:75"
    "AuctionHouseBot.Buyer.AcceptablePriceModifier"   = "1.20"
    "AuctionHouseBot.Buyer.AlwaysBidMaxCalculatedPrice" = "false"
    "AuctionHouseBot.Buyer.PreventOverpayingForVendorItems" = "true"
    "AuctionHouseBot.Buyer.BidAgainstPlayers"         = "false"
    "AuctionHouseBot.AdvancedListingRules.UseDropRates.Enabled" = "true"
    "AuctionHouseBot.AdvancedListingRules.UseDropRates.MinDropRate" = "0.005"
    "AuctionHouseBot.DisabledItemTextFilter"          = "true"
    "AuctionHouseBot.DisabledRecipeProducedItemFilterEnabled" = "false"
    "AuctionHouseBot.DisabledCustomItemIDs"           = "900000-999999"
    "AuctionHouseBot.VendorItems"                     = "0"
    "AuctionHouseBot.VendorTradeGoods"                = "0"
    "AuctionHouseBot.LootItems"                       = "1"
    "AuctionHouseBot.LootTradeGoods"                  = "1"
    "AuctionHouseBot.OtherItems"                      = "0"
    "AuctionHouseBot.OtherTradeGoods"                 = "0"
    "AuctionHouseBot.ProfessionItems"                 = "0"
    "AuctionHouseBot.No_Bind"                         = "1"
    "AuctionHouseBot.Bind_When_Picked_Up"             = "0"
    "AuctionHouseBot.Bind_When_Equipped"              = "1"
    "AuctionHouseBot.Bind_When_Use"                   = "1"
    "AuctionHouseBot.Bind_Quest_Item"                 = "0"
    "AuctionHouseBot.DisableConjured"                 = "1"
    "AuctionHouseBot.DisableGems"                     = "0"
    "AuctionHouseBot.DisableMoney"                    = "1"
    "AuctionHouseBot.DisableMoneyLoot"                = "1"
    "AuctionHouseBot.DisableLootable"                 = "1"
    "AuctionHouseBot.DisableKeys"                     = "1"
    "AuctionHouseBot.DisableDuration"                 = "1"
    "AuctionHouseBot.DisableBOP_Or_Quest_NoReqLevel"  = "1"
    "AuctionHouseBot.DisableWarriorItems"             = "0"
    "AuctionHouseBot.DisablePaladinItems"             = "0"
    "AuctionHouseBot.DisableHunterItems"              = "0"
    "AuctionHouseBot.DisableRogueItems"               = "0"
    "AuctionHouseBot.DisablePriestItems"              = "0"
    "AuctionHouseBot.DisableDKItems"                  = "0"
    "AuctionHouseBot.DisableShamanItems"              = "0"
    "AuctionHouseBot.DisableMageItems"                = "0"
    "AuctionHouseBot.DisableWarlockItems"             = "0"
    "AuctionHouseBot.DisableUnusedClassItems"         = "0"
    "AuctionHouseBot.DisableDruidItems"               = "0"
    "AuctionHouseBot.DisableItemsBelowLevel"          = "0"
    "AuctionHouseBot.DisableItemsAboveLevel"          = "0"
    "AuctionHouseBot.DisableItemsBelowGUID"           = "0"
    "AuctionHouseBot.DisableItemsAboveGUID"           = "0"
    "AuctionHouseBot.DisableItemsBelowReqLevel"       = "0"
    "AuctionHouseBot.DisableItemsAboveReqLevel"       = "0"
    "AuctionHouseBot.DisableItemsBelowReqSkillRank"   = "0"
    "AuctionHouseBot.DisableItemsAboveReqSkillRank"   = "0"
    "AuctionHouseBot.DisableTGsBelowLevel"            = "0"
    "AuctionHouseBot.DisableTGsAboveLevel"            = "0"
    "AuctionHouseBot.DisableTGsBelowGUID"             = "0"
    "AuctionHouseBot.DisableTGsAboveGUID"             = "0"
    "AuctionHouseBot.DisableTGsBelowReqLevel"         = "0"
    "AuctionHouseBot.DisableTGsAboveReqLevel"         = "0"
    "AuctionHouseBot.DisableTGsBelowReqSkillRank"     = "0"
    "AuctionHouseBot.DisableTGsAboveReqSkillRank"     = "0"
    "AuctionHouseBot.SellerWhiteList"                 = '""'
    "AuctionHouseBot.DEBUG_CONFIG"                    = "0"
    "AuctionHouseBot.DEBUG_BUYER"                     = "0"
    "AuctionHouseBot.DEBUG_SELLER"                    = "0"
    "AuctionHouseBot.TRACE_BUYER"                     = "0"
    "AuctionHouseBot.TRACE_SELLER"                    = "0"
}

$ahBotPlusCategories = @(
    "Consumable", "Container", "Weapon", "Gem", "Armor", "Reagent", "Projectile",
    "TradeGood", "Generic", "Recipe", "Quiver", "Quest", "Key", "Misc", "Glyph"
)
$ahBotPlusQualities = @("Poor", "Normal", "Uncommon", "Rare", "Epic", "Legendary", "Artifact", "Heirloom")
$ahBotPlusListingWeights = [ordered]@{
    "AuctionHouseBot.ListProportion.CategoryConsumable.QualityNormal" = "12"
    "AuctionHouseBot.ListProportion.CategoryConsumable.QualityUncommon" = "8"
    "AuctionHouseBot.ListProportion.CategoryConsumable.QualityRare" = "3"
    "AuctionHouseBot.ListProportion.CategoryConsumable.QualityEpic" = "1"
    "AuctionHouseBot.ListProportion.CategoryContainer.QualityNormal" = "3"
    "AuctionHouseBot.ListProportion.CategoryContainer.QualityUncommon" = "2"
    "AuctionHouseBot.ListProportion.CategoryContainer.QualityRare" = "1"
    "AuctionHouseBot.ListProportion.CategoryWeapon.QualityUncommon" = "18"
    "AuctionHouseBot.ListProportion.CategoryWeapon.QualityRare" = "8"
    "AuctionHouseBot.ListProportion.CategoryWeapon.QualityEpic" = "2"
    "AuctionHouseBot.ListProportion.CategoryGem.QualityUncommon" = "8"
    "AuctionHouseBot.ListProportion.CategoryGem.QualityRare" = "4"
    "AuctionHouseBot.ListProportion.CategoryGem.QualityEpic" = "1"
    "AuctionHouseBot.ListProportion.CategoryArmor.QualityUncommon" = "24"
    "AuctionHouseBot.ListProportion.CategoryArmor.QualityRare" = "10"
    "AuctionHouseBot.ListProportion.CategoryArmor.QualityEpic" = "3"
    "AuctionHouseBot.ListProportion.CategoryReagent.QualityNormal" = "6"
    "AuctionHouseBot.ListProportion.CategoryProjectile.QualityNormal" = "4"
    "AuctionHouseBot.ListProportion.CategoryTradeGood.QualityNormal" = "35"
    "AuctionHouseBot.ListProportion.CategoryTradeGood.QualityUncommon" = "12"
    "AuctionHouseBot.ListProportion.CategoryTradeGood.QualityRare" = "4"
    "AuctionHouseBot.ListProportion.CategoryTradeGood.QualityEpic" = "1"
    "AuctionHouseBot.ListProportion.CategoryRecipe.QualityNormal" = "8"
    "AuctionHouseBot.ListProportion.CategoryRecipe.QualityUncommon" = "10"
    "AuctionHouseBot.ListProportion.CategoryRecipe.QualityRare" = "4"
    "AuctionHouseBot.ListProportion.CategoryRecipe.QualityEpic" = "1"
    "AuctionHouseBot.ListProportion.CategoryGlyph.QualityNormal" = "12"
}

$dungeonMasterSettings = [ordered]@{
    "DungeonMaster.Roguelike.Buff.1"  = '"15366,Songflower Serenade,100"'
    "DungeonMaster.Roguelike.Buff.2"  = '"22888,Rallying Cry,80"'
    "DungeonMaster.Roguelike.Buff.3"  = '"24425,Spirit of Zandalar,80"'
    "DungeonMaster.Roguelike.Buff.4"  = '"16609,Warchief''s Blessing,80"'
    "DungeonMaster.Roguelike.Buff.5"  = '"23768,Fortune of Damage,60"'
    "DungeonMaster.Roguelike.Buff.6"  = '"20217,Blessing of Kings,90"'
    "DungeonMaster.Roguelike.Buff.7"  = '"48161,Power Word: Fortitude,100"'
    "DungeonMaster.Roguelike.Buff.8"  = '"48469,Gift of the Wild,100"'
    "DungeonMaster.Roguelike.Buff.9"  = '"19506,Trueshot Aura,70"'
    "DungeonMaster.Roguelike.Buff.10" = '"24932,Leader of the Pack,70"'
    "DungeonMaster.Roguelike.Buff.11" = '"27127,Arcane Brilliance,80"'
}

foreach ($entry in $worldSettings.GetEnumerator()) {
    Set-OrAddConfigValue -Path $worldConfig -Key $entry.Key -Value $entry.Value
}

foreach ($entry in $weatherVibeSettings.GetEnumerator()) {
    Set-OrAddConfigValue -Path $weatherVibeConfig -Key $entry.Key -Value $entry.Value
}

foreach ($entry in $playerbotSettings.GetEnumerator()) {
    Set-OrAddConfigValue -Path $playerbotConfig -Key $entry.Key -Value $entry.Value
}

foreach ($entry in $ahbotSettings.GetEnumerator()) {
    Set-OrAddConfigValue -Path $ahbotConfig -Key $entry.Key -Value $entry.Value
}

foreach ($category in $ahBotPlusCategories) {
    foreach ($quality in $ahBotPlusQualities) {
        Set-OrAddConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ListProportion.Category$category.Quality$quality" -Value "0"
    }
}

foreach ($entry in $ahBotPlusListingWeights.GetEnumerator()) {
    Set-OrAddConfigValue -Path $ahbotConfig -Key $entry.Key -Value $entry.Value
}

foreach ($entry in $dungeonMasterSettings.GetEnumerator()) {
    Set-OrAddConfigValue -Path $dungeonMasterConfig -Key $entry.Key -Value $entry.Value
}

[pscustomobject]@{
    RunRoot      = $RunRoot
    AhbotAccount = $AhbotAccount
    AhbotGuid    = $AhbotGuid
    BackupStamp  = if ($NoBackup) { "<disabled>" } else { $stamp }
} | Format-List
