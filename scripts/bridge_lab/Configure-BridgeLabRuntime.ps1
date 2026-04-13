param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [int]$LabMySqlPort = 33307,
    [int]$WorldServerPort = 8095,
    [int]$SoapPort = 7879,
    [string]$DataDir = "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data"
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

    $content = Get-Content -Path $Path -Raw
    $escapedKey = [regex]::Escape($Key)
    $line = "$Key = $Value"
    $pattern = "(?m)^\s*$escapedKey\s*=.*$"
    $regex = [regex]::new($pattern)

    if ($regex.IsMatch($content)) {
        $content = $regex.Replace($content, $line, 1)
    } else {
        $content = $content.TrimEnd() + "`r`n" + $line + "`r`n"
    }

    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $content, $utf8NoBom)
}

function Ensure-ConfigFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (Test-Path -LiteralPath $Path) {
        return
    }

    $distPath = $Path + ".dist"
    if (-not (Test-Path -LiteralPath $distPath)) {
        throw "Config file was not found and no .dist template exists: $Path"
    }

    Copy-Item -LiteralPath $distPath -Destination $Path -Force
}

$configRoot = Join-Path $WorkspaceRoot "run\configs"
$moduleConfigRoot = Join-Path $configRoot "modules"
$authConfig = Join-Path $configRoot "authserver.conf"
$worldConfig = Join-Path $configRoot "worldserver.conf"
$playerbotsConfig = Join-Path $moduleConfigRoot "playerbots.conf"
$bridgeConfig = Join-Path $moduleConfigRoot "mod_wm_bridge.conf"
$spellsConfig = Join-Path $moduleConfigRoot "mod_wm_spells.conf"
$prototypeConfig = Join-Path $moduleConfigRoot "mod_wm_prototypes.conf"
$weatherVibeConfig = Join-Path $moduleConfigRoot "mod_weather_vibe.conf"

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

Set-ConfigValue -Path $authConfig -Key "LoginDatabaseInfo" -Value $loginDb
Set-ConfigValue -Path $worldConfig -Key "LoginDatabaseInfo" -Value $loginDb
Set-ConfigValue -Path $worldConfig -Key "WorldDatabaseInfo" -Value $worldDb
Set-ConfigValue -Path $worldConfig -Key "CharacterDatabaseInfo" -Value $charactersDb
Set-ConfigValue -Path $worldConfig -Key "DataDir" -Value """$DataDir"""
Set-ConfigValue -Path $worldConfig -Key "WorldServerPort" -Value $WorldServerPort
Set-ConfigValue -Path $worldConfig -Key "SOAP.Port" -Value $SoapPort

if (Test-Path $playerbotsConfig) {
    Set-ConfigValue -Path $playerbotsConfig -Key "PlayerbotsDatabaseInfo" -Value $playerbotsDb
}

Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.Enable" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.PlayerGuidAllowList" -Value """"""
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.DbControl.Enable" -Value "1"
Set-ConfigValue -Path $bridgeConfig -Key "WmBridge.ActionQueue.Enable" -Value "1"

if (Test-Path $spellsConfig) {
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.Enable" -Value "1"
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.PlayerGuidAllowList" -Value """"""
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.LabOnlyDebugInvokeEnable" -Value "1"
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.BoneboundServant.Enable" -Value "1"
    Set-ConfigValue -Path $spellsConfig -Key "WmSpells.BoneboundServant.ShellSpellIds" -Value """940000,940001,49126"""
}

if (Test-Path $prototypeConfig) {
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.Enable" -Value "0"
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.PlayerGuidAllowList" -Value """"""
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.TwinSkeleton.Enable" -Value "0"
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.SkeletalPet.Enable" -Value "0"
    Set-ConfigValue -Path $prototypeConfig -Key "WmPrototypes.SkeletalPet.ShellSpellIds" -Value """"""
}

if (Test-Path $weatherVibeConfig) {
    Set-ConfigValue -Path $weatherVibeConfig -Key "WeatherVibe.Debug" -Value "0"
}

Write-Host "bridge_lab_configured=true workspace=$WorkspaceRoot mysql_port=$LabMySqlPort world_port=$WorldServerPort soap_port=$SoapPort data_dir=$DataDir"
