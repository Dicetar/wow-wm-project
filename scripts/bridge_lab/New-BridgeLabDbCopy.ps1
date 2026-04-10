param(
    [string]$MysqlBin = $env:WM_MYSQL_BIN_PATH,
    [string]$MysqlDumpBin,
    [string]$HostName = $(if ($env:WM_WORLD_DB_HOST) { $env:WM_WORLD_DB_HOST } else { "127.0.0.1" }),
    [int]$Port = $(if ($env:WM_WORLD_DB_PORT) { [int]$env:WM_WORLD_DB_PORT } else { 3306 }),
    [string]$User = $(if ($env:WM_WORLD_DB_USER) { $env:WM_WORLD_DB_USER } else { "root" }),
    [string]$Password = $env:WM_WORLD_DB_PASSWORD,
    [string]$SourceAuthDb = "acore_auth",
    [string]$SourceWorldDb = "acore_world",
    [string]$SourceCharactersDb = "acore_characters",
    [string]$SourcePlayerbotsDb = "acore_playerbots",
    [string]$LabPrefix = "wm_lab",
    [string]$DumpRoot = "D:\WOW\WM_BridgeLab\db-dumps",
    [switch]$ConfirmCreateLabDbCopy
)

$ErrorActionPreference = "Stop"

if (-not $ConfirmCreateLabDbCopy) {
    throw "Refusing to create or overwrite lab DBs. Re-run with -ConfirmCreateLabDbCopy."
}

if (-not $MysqlBin) {
    $MysqlBin = "mysql"
}
if (-not $MysqlDumpBin) {
    $MysqlDumpBin = "mysqldump"
}

New-Item -ItemType Directory -Force -Path $DumpRoot | Out-Null

$dbMap = @(
    @{ Source = $SourceAuthDb; Target = "${LabPrefix}_auth" },
    @{ Source = $SourceWorldDb; Target = "${LabPrefix}_world" },
    @{ Source = $SourceCharactersDb; Target = "${LabPrefix}_characters" },
    @{ Source = $SourcePlayerbotsDb; Target = "${LabPrefix}_playerbots" }
)

foreach ($db in $dbMap) {
    $dumpFile = Join-Path $DumpRoot ($db.Source + ".sql")
    Write-Host "Dumping $($db.Source) -> $dumpFile"
    & $MysqlDumpBin "--host=$HostName" "--port=$Port" "--user=$User" "--password=$Password" --single-transaction --routines --triggers $db.Source | Set-Content -Encoding UTF8 -Path $dumpFile
    if (-not $?) {
        throw "mysqldump failed for $($db.Source)"
    }

    Write-Host "Recreating $($db.Target)"
    & $MysqlBin "--host=$HostName" "--port=$Port" "--user=$User" "--password=$Password" "--execute=DROP DATABASE IF EXISTS $($db.Target); CREATE DATABASE $($db.Target) DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;"
    if (-not $?) {
        throw "mysql create database failed for $($db.Target)"
    }

    Write-Host "Importing $dumpFile -> $($db.Target)"
    Get-Content -Path $dumpFile | & $MysqlBin "--host=$HostName" "--port=$Port" "--user=$User" "--password=$Password" "--database=$($db.Target)"
    if (-not $?) {
        throw "mysql import failed for $($db.Target)"
    }
}

Write-Host "Lab DB copy complete."
Write-Host "Use lab DB names: ${LabPrefix}_auth, ${LabPrefix}_world, ${LabPrefix}_characters, ${LabPrefix}_playerbots"
