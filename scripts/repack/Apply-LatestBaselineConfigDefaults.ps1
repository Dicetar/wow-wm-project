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

    $content = Get-Content -LiteralPath $Path -Raw
    $newline = if ($content -match "`r`n") { "`r`n" } else { "`n" }
    $line = "$Key = $Value"
    $pattern = "(?m)^\s*" + [regex]::Escape($Key) + "\s*=.*$"

    if ([regex]::IsMatch($content, $pattern)) {
        $updated = [regex]::Replace(
            $content,
            $pattern,
            [System.Text.RegularExpressions.MatchEvaluator] { param($m) $line },
            1
        )
    }
    else {
        if ($content.Length -gt 0 -and -not $content.EndsWith($newline)) {
            $content += $newline
        }

        $updated = $content + $line + $newline
    }

    if ($updated -ne $content) {
        $encoding = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($Path, $updated, $encoding)
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
    "AuctionHouseBot.EnableBuyer"                     = "0"
    "AuctionHouseBot.UseBuyPriceForSeller"            = "0"
    "AuctionHouseBot.UseBuyPriceForBuyer"             = "0"
    "AuctionHouseBot.UseMarketPriceForSeller"         = "0"
    "AuctionHouseBot.MarketResetThreshold"            = "25"
    "AuctionHouseBot.ConsiderOnlyBotAuctions"         = "0"
    "AuctionHouseBot.DuplicatesCount"                 = "0"
    "AuctionHouseBot.DivisibleStacks"                 = "0"
    "AuctionHouseBot.ElapsingTimeClass"               = "1"
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
    "AuctionHouseBot.DisableConjured"                 = "0"
    "AuctionHouseBot.DisableGems"                     = "0"
    "AuctionHouseBot.DisableMoney"                    = "0"
    "AuctionHouseBot.DisableMoneyLoot"                = "0"
    "AuctionHouseBot.DisableLootable"                 = "0"
    "AuctionHouseBot.DisableKeys"                     = "0"
    "AuctionHouseBot.DisableDuration"                 = "0"
    "AuctionHouseBot.DisableBOP_Or_Quest_NoReqLevel"  = "0"
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

foreach ($entry in $dungeonMasterSettings.GetEnumerator()) {
    Set-OrAddConfigValue -Path $dungeonMasterConfig -Key $entry.Key -Value $entry.Value
}

[pscustomobject]@{
    RunRoot      = $RunRoot
    AhbotAccount = $AhbotAccount
    AhbotGuid    = $AhbotGuid
    BackupStamp  = if ($NoBackup) { "<disabled>" } else { $stamp }
} | Format-List
