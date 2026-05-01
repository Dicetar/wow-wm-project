param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [int]$LabMySqlPort = 33307,
    [int]$WorldServerPort = 8095,
    [int]$SoapPort = 7879,
    [string]$DataDir = "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data",
    [string]$WmSpellsPlayerGuidAllowList = "5406,5405",
    [switch]$UpdatePlayerbotsDatabaseInfo
)

$ErrorActionPreference = "Stop"

function Set-ConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if (-not (Test-Path $Path)) {
        throw "Config file not found: $Path"
    }

    $content = Read-ConfigText -Path $Path
    $escapedKey = [regex]::Escape($Key)
    $line = "$Key = $Value"
    $pattern = "(?m)^\s*$escapedKey\s*=.*$"
    $regex = [regex]::new($pattern)
    $originalContent = $content

    if ($regex.IsMatch($content)) {
        $content = $regex.Replace($content, $line, 1)
    } else {
        $content = $content.TrimEnd() + "`r`n" + $line + "`r`n"
    }

    if ($content -ne $originalContent) {
        $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
        [System.IO.File]::WriteAllText($Path, $content, $utf8NoBom)
    }
}

function Read-ConfigText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $utf8Strict = [System.Text.UTF8Encoding]::new($false, $true)
    try {
        return $utf8Strict.GetString($bytes)
    } catch {
        return [System.Text.Encoding]::Default.GetString($bytes)
    }
}

function Ensure-ConfigFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [string]$DistPath = ""
    )

    if (Test-Path -LiteralPath $Path) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($DistPath)) {
        $DistPath = $Path + ".dist"
    }

    if (-not (Test-Path -LiteralPath $distPath)) {
        throw "Config file was not found and no .dist template exists: $Path"
    }

    Copy-Item -LiteralPath $distPath -Destination $Path -Force
}

function Ensure-AhBotPlusConfigFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$DistPath
    )

    if (-not (Test-Path -LiteralPath $Path) -or -not (Test-Path -LiteralPath $DistPath)) {
        return
    }

    $distContent = Read-ConfigText -Path $DistPath
    if ($distContent -notmatch "AuctionHouseBot\.GUIDs" -or
        $distContent -notmatch "AuctionHouseBot\.ListProportion\.CategoryTradeGood\.QualityNormal") {
        return
    }

    $content = Read-ConfigText -Path $Path
    if ($content -match "AuctionHouseBot\.Buyer\.Enabled" -and
        $content -match "AuctionHouseBot\.ListProportion\.CategoryTradeGood\.QualityNormal") {
        return
    }

    $backupPath = "$Path.legacy.$(Get-Date -Format yyyyMMddHHmmss).bak"
    Copy-Item -LiteralPath $Path -Destination $backupPath -Force
    Copy-Item -LiteralPath $DistPath -Destination $Path -Force
    Write-Host "bridge_lab_ahbot_config_rebased=true backup=$backupPath dist=$DistPath"
}

$configRoot = Join-Path $WorkspaceRoot "run\configs"
$moduleConfigRoot = Join-Path $configRoot "modules"
$buildModuleConfigRoot = Join-Path $WorkspaceRoot "build\bin\RelWithDebInfo\configs\modules"
$authConfig = Join-Path $configRoot "authserver.conf"
$worldConfig = Join-Path $configRoot "worldserver.conf"
$playerbotsConfig = Join-Path $moduleConfigRoot "playerbots.conf"
$bridgeConfig = Join-Path $moduleConfigRoot "mod_wm_bridge.conf"
$spellsConfig = Join-Path $moduleConfigRoot "mod_wm_spells.conf"
$prototypeConfig = Join-Path $moduleConfigRoot "mod_wm_prototypes.conf"
$weatherVibeConfig = Join-Path $moduleConfigRoot "mod_weather_vibe.conf"
$ahbotConfig = Join-Path $moduleConfigRoot "mod_ahbot.conf"
$autoBalanceConfig = Join-Path $moduleConfigRoot "AutoBalance.conf"
$soloLfgConfig = Join-Path $moduleConfigRoot "SoloLfg.conf"
$dynamicLootRatesConfig = Join-Path $moduleConfigRoot "mod_dynamic_loot_rates.conf"

if (-not (Test-Path $DataDir)) {
    throw "DataDir was not found: $DataDir"
}

$loginDb = """127.0.0.1;$LabMySqlPort;acore;acore;acore_auth"""
$worldDb = """127.0.0.1;$LabMySqlPort;acore;acore;acore_world"""
$charactersDb = """127.0.0.1;$LabMySqlPort;acore;acore;acore_characters"""
$playerbotsDb = """127.0.0.1;$LabMySqlPort;acore;acore;acore_playerbots"""

foreach ($moduleConfig in @($bridgeConfig, $spellsConfig, $prototypeConfig, $weatherVibeConfig)) {
    Ensure-ConfigFile -Path $moduleConfig
}

Ensure-ConfigFile -Path $autoBalanceConfig -DistPath (Join-Path $buildModuleConfigRoot "AutoBalance.conf.dist")
Ensure-ConfigFile -Path $soloLfgConfig -DistPath (Join-Path $buildModuleConfigRoot "SoloLfg.conf.dist")
Ensure-ConfigFile -Path $dynamicLootRatesConfig -DistPath (Join-Path $buildModuleConfigRoot "mod_dynamic_loot_rates.conf.dist")
$ahbotDistConfig = Join-Path $buildModuleConfigRoot "mod_ahbot.conf.dist"
Ensure-ConfigFile -Path $ahbotConfig -DistPath $ahbotDistConfig
Ensure-AhBotPlusConfigFile -Path $ahbotConfig -DistPath $ahbotDistConfig

Set-ConfigValue -Path $authConfig -Key "LoginDatabaseInfo" -Value $loginDb
Set-ConfigValue -Path $worldConfig -Key "LoginDatabaseInfo" -Value $loginDb
Set-ConfigValue -Path $worldConfig -Key "WorldDatabaseInfo" -Value $worldDb
Set-ConfigValue -Path $worldConfig -Key "CharacterDatabaseInfo" -Value $charactersDb
Set-ConfigValue -Path $worldConfig -Key "DataDir" -Value """$DataDir"""
Set-ConfigValue -Path $worldConfig -Key "WorldServerPort" -Value $WorldServerPort
Set-ConfigValue -Path $worldConfig -Key "SOAP.Port" -Value $SoapPort
Set-ConfigValue -Path $worldConfig -Key "AllowTwoSide.Interaction.Auction" -Value "1"
Set-ConfigValue -Path $worldConfig -Key "Rate.Auction.Deposit" -Value "0.5"
Set-ConfigValue -Path $worldConfig -Key "Rate.Auction.Cut" -Value "0.5"

if ($UpdatePlayerbotsDatabaseInfo.IsPresent -and (Test-Path $playerbotsConfig)) {
    Set-ConfigValue -Path $playerbotsConfig -Key "PlayerbotsDatabaseInfo" -Value $playerbotsDb
}

Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.Enable" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.PlayerGuidAllowList" -Value """"""
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.DbControl.Enable" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.ActionQueue.Enable" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.Emit.Aura" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.Emit.AuraSpellAllowList" -Value """946602,132,687,770"""
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.AoeLoot.Enable" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.AoeLoot.Radius" -Value "35"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.AoeLoot.MaxCorpses" -Value "25"

if (Test-Path $spellsConfig) {
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.Enable" -Value "1"
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.PlayerGuidAllowList" -Value """$WmSpellsPlayerGuidAllowList"""
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.LabOnlyDebugInvokeEnable" -Value "1"
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.DebugPollIntervalMs" -Value "50"
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.BoneboundServant.Enable" -Value "1"
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.BoneboundServant.ShellSpellIds" -Value """940000,940001"""
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.BoneboundServant.CreatureEntry" -Value "920100"
}

if (Test-Path $prototypeConfig) {
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.Enable" -Value "0"
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.PlayerGuidAllowList" -Value """"""
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.TwinSkeleton.Enable" -Value "0"
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.TwinSkeleton.ShellSpellIds" -Value """"""
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.SkeletalPet.Enable" -Value "0"
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.SkeletalPet.ShellSpellIds" -Value """"""
}

if (Test-Path $weatherVibeConfig) {
    Set-ConfigValue -Path $weatherVibeConfig -Key "WeatherVibe.Debug" -Value "0"
}

if (Test-Path $ahbotConfig) {
    # Auction Bot Plus profile. These keys are used by the NathanHandley rewrite.
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DEBUG" -Value "false"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DEBUG_FILTERS" -Value "false"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.EnableSeller" -Value "true"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.Enabled" -Value "true"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.GUIDs" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.MinutesBetweenBuyCycle" -Value "1:3"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.MinutesBetweenSellCycle" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ItemsPerCycle" -Value "2000"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ReturnExpiredAuctionItemsToBot" -Value "false"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Alliance.MinItems" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Alliance.MaxItems" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Horde.MinItems" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Horde.MaxItems" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Neutral.MinItems" -Value "40000"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Neutral.MaxItems" -Value "40000"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.BuyoutVariationReducePercent" -Value "0.30"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.BuyoutVariationAddPercent" -Value "0.20"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.BidVariationHighReducePercent" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.BidVariationLowReducePercent" -Value "0.30"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.BuyCandidatesPerBuyCycle" -Value "25:75"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.AcceptablePriceModifier" -Value "1.20"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.AlwaysBidMaxCalculatedPrice" -Value "false"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.PreventOverpayingForVendorItems" -Value "true"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.BidAgainstPlayers" -Value "false"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.AdvancedListingRules.UseDropRates.Enabled" -Value "true"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.AdvancedListingRules.UseDropRates.MinDropRate" -Value "0.005"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisabledItemTextFilter" -Value "true"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisabledRecipeProducedItemFilterEnabled" -Value "false"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisabledCustomItemIDs" -Value "900000-999999"

    $ahBotCategories = @(
        "Consumable", "Container", "Weapon", "Gem", "Armor", "Reagent", "Projectile",
        "TradeGood", "Generic", "Recipe", "Quiver", "Quest", "Key", "Misc", "Glyph"
    )
    $ahBotQualities = @("Poor", "Normal", "Uncommon", "Rare", "Epic", "Legendary", "Artifact", "Heirloom")
    foreach ($category in $ahBotCategories) {
        foreach ($quality in $ahBotQualities) {
            Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ListProportion.Category$category.Quality$quality" -Value "0"
        }
    }

    $ahBotListingWeights = [ordered]@{
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
    foreach ($entry in $ahBotListingWeights.GetEnumerator()) {
        Set-ConfigValue -Path $ahbotConfig -Key $entry.Key -Value $entry.Value
    }

    # Legacy azerothcore/mod-ah-bot fallback. Kept tight so stale deployments do not sell junk.
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.EnableBuyer" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.UseBuyPriceForSeller" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.UseBuyPriceForBuyer" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.UseMarketPriceForSeller" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.MarketResetThreshold" -Value "10"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Account" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.GUID" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ConsiderOnlyBotAuctions" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DuplicatesCount" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DivisibleStacks" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ElapsingTimeClass" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.VendorItems" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.VendorTradeGoods" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.LootItems" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.LootTradeGoods" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.OtherItems" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.OtherTradeGoods" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ProfessionItems" -Value "0"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisableConjured" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisableMoney" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisableMoneyLoot" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisableLootable" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisableKeys" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisableDuration" -Value "1"
    Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisableBOP_Or_Quest_NoReqLevel" -Value "1"
}

# Solo 5-player dungeons: start from the original 5-man baseline, then apply explicit WM tuning.
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.Enable.Global" -Value "1"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.MinPlayers" -Value "1"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.MinPlayers.Heroic" -Value "1"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.InflectionPoint.CurveFloor" -Value "1.0"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.InflectionPoint.CurveCeiling" -Value "1.0"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.InflectionPointHeroic.CurveFloor" -Value "1.0"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.InflectionPointHeroic.CurveCeiling" -Value "1.0"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifier.Health" -Value "0.75"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifier.Damage" -Value "0.50"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifier.Boss.Health" -Value "0.75"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifier.Boss.Damage" -Value "0.50"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifierHeroic.Health" -Value "0.75"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifierHeroic.Damage" -Value "0.50"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifierHeroic.Boss.Health" -Value "0.75"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.StatModifierHeroic.Boss.Damage" -Value "0.50"
Set-ConfigValue -Path $autoBalanceConfig -Key "AutoBalance.RewardScaling.XP" -Value "0"

Set-ConfigValue -Path $soloLfgConfig -Key "SoloLFG.Enable" -Value "1"
Set-ConfigValue -Path $soloLfgConfig -Key "SoloLFG.FixedXP" -Value "1"
Set-ConfigValue -Path $soloLfgConfig -Key "SoloLFG.FixedXPRate" -Value "0.75"

Set-ConfigValue -Path $dynamicLootRatesConfig -Key "DynamicLootRates.Enable" -Value "1"
Set-ConfigValue -Path $dynamicLootRatesConfig -Key "DynamicLootRates.Dungeon.Rate.GroupAmount" -Value "2"
Set-ConfigValue -Path $dynamicLootRatesConfig -Key "DynamicLootRates.Dungeon.Rate.ReferencedAmount" -Value "2"

Write-Host "bridge_lab_configured=true workspace=$WorkspaceRoot mysql_port=$LabMySqlPort world_port=$WorldServerPort soap_port=$SoapPort data_dir=$DataDir"
