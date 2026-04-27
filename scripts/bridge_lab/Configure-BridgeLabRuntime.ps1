param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [int]$LabMySqlPort = 33307,
    [int]$WorldServerPort = 8095,
    [int]$SoapPort = 7879,
    [string]$DataDir = "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data",
    [string]$WmSpellsPlayerGuidAllowList = "5406",
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

Set-ConfigValue -Path $authConfig -Key "LoginDatabaseInfo" -Value $loginDb
Set-ConfigValue -Path $worldConfig -Key "LoginDatabaseInfo" -Value $loginDb
Set-ConfigValue -Path $worldConfig -Key "WorldDatabaseInfo" -Value $worldDb
Set-ConfigValue -Path $worldConfig -Key "CharacterDatabaseInfo" -Value $charactersDb
Set-ConfigValue -Path $worldConfig -Key "DataDir" -Value """$DataDir"""
Set-ConfigValue -Path $worldConfig -Key "WorldServerPort" -Value $WorldServerPort
Set-ConfigValue -Path $worldConfig -Key "SOAP.Port" -Value $SoapPort

if ($UpdatePlayerbotsDatabaseInfo.IsPresent -and (Test-Path $playerbotsConfig)) {
    Set-ConfigValue -Path $playerbotsConfig -Key "PlayerbotsDatabaseInfo" -Value $playerbotsDb
}

Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.Enable" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.PlayerGuidAllowList" -Value """"""
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.DbControl.Enable" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.ActionQueue.Enable" -Value "1"
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
