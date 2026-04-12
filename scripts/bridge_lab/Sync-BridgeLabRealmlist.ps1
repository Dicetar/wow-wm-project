param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [int]$MySqlPort = 33307,
    [string]$RealmAddress = "127.0.0.1",
    [string]$DbUser = "acore",
    [string]$DbPassword = "acore",
    [int]$GameBuild = 12340
)

$ErrorActionPreference = "Stop"

function Get-ConfigIntValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    if (-not (Test-Path $Path)) {
        throw "Config file not found: $Path"
    }

    $match = Select-String -Path $Path -Pattern ("^\s*" + [regex]::Escape($Key) + "\s*=\s*([0-9]+)\s*$") | Select-Object -First 1
    if (-not $match) {
        throw "Config key '$Key' was not found in $Path"
    }

    return [int]$match.Matches[0].Groups[1].Value
}

$mysqlPath = Join-Path $WorkspaceRoot "deps\mysql\bin\mysql.exe"
$worldConfig = Join-Path $WorkspaceRoot "run\configs\worldserver.conf"

if (-not (Test-Path $mysqlPath)) {
    throw "Lab mysql client was not found: $mysqlPath"
}

$realmId = Get-ConfigIntValue -Path $worldConfig -Key "RealmID"
$worldPort = Get-ConfigIntValue -Path $worldConfig -Key "WorldServerPort"

$sql = @"
SET @realm_id := $realmId;
SET @realm_name := COALESCE((SELECT name FROM realmlist WHERE id = @realm_id LIMIT 1), 'WM Bridge Lab');
INSERT INTO realmlist (id, name, address, port, gamebuild, flag, timezone)
SELECT @realm_id, @realm_name, '$RealmAddress', $worldPort, $GameBuild, 0, 1
WHERE NOT EXISTS (SELECT 1 FROM realmlist WHERE id = @realm_id);
UPDATE realmlist
SET address = '$RealmAddress',
    port = $worldPort,
    gamebuild = $GameBuild
WHERE id = @realm_id;
SELECT id, name, address, port, gamebuild
FROM realmlist
WHERE id = @realm_id;
"@

& $mysqlPath `
    --host=127.0.0.1 `
    --port=$MySqlPort `
    --user=$DbUser `
    --password=$DbPassword `
    --database=acore_auth `
    -N `
    -e $sql

if (-not $?) {
    throw "Failed to sync bridge-lab realmlist."
}

Write-Host "bridge_lab_realmlist_synced=true realm_id=$realmId world_port=$worldPort address=$RealmAddress"
