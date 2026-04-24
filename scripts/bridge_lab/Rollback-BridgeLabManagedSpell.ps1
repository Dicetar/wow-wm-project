param(
    [string]$WorkspaceRoot = "D:\WOW\wm-project",
    [string]$BridgeLabRoot = "D:\WOW\WM_BridgeLab",
    [int]$SpellEntry = 947000,
    [ValidateSet("apply", "dry-run")]
    [string]$Mode = "dry-run",
    [ValidateSet("auto", "off", "soap")]
    [string]$RuntimeSync = "off",
    [string[]]$SoapCommand = @(),
    [int]$LabMySqlPort = 33307,
    [int]$SoapPort = 7879
)

$ErrorActionPreference = "Stop"

$pythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
$mysqlBin = Join-Path $BridgeLabRoot "deps\mysql\bin\mysql.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python executable was not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $mysqlBin)) {
    throw "mysql.exe was not found: $mysqlBin"
}

$env:PYTHONPATH = "src"
$env:WM_MYSQL_BIN_PATH = $mysqlBin
$env:WM_WORLD_DB_HOST = "127.0.0.1"
$env:WM_WORLD_DB_PORT = [string]$LabMySqlPort
$env:WM_WORLD_DB_USER = "acore"
$env:WM_WORLD_DB_PASSWORD = "acore"
$env:WM_WORLD_DB_NAME = "acore_world"
$env:WM_SOAP_PORT = [string]$SoapPort

Set-Location -LiteralPath $WorkspaceRoot
$rollbackArgs = @(
    "-m",
    "wm.spells.rollback",
    "--spell-entry",
    ([string]$SpellEntry),
    "--mode",
    $Mode,
    "--runtime-sync",
    $RuntimeSync,
    "--summary"
)
foreach ($command in $SoapCommand) {
    $rollbackArgs += @("--soap-command", $command)
}

& $pythonExe @rollbackArgs
exit $LASTEXITCODE
