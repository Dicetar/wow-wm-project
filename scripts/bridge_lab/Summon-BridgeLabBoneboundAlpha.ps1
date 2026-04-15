param(
    [int]$PlayerGuid = 5406,
    [int]$ShellSpellId = 940001,
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [switch]$Wait,
    [double]$TimeoutSeconds = 5.0
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$mysqlBin = Join-Path $WorkspaceRoot "deps\mysql\bin\mysql.exe"
if (-not (Test-Path -LiteralPath $mysqlBin)) {
    throw "mysql.exe was not found at $mysqlBin"
}

$env:WM_MYSQL_BIN_PATH = $mysqlBin
$env:WM_WORLD_DB_HOST = "127.0.0.1"
$env:WM_WORLD_DB_PORT = "33307"
$env:WM_WORLD_DB_USER = "acore"
$env:WM_WORLD_DB_PASSWORD = "acore"
$env:WM_WORLD_DB_NAME = "acore_world"

$pythonArgs = @(
    "-m", "wm.spells.summon_release",
    "--player-guid", "$PlayerGuid",
    "--shell-spell-id", "$ShellSpellId",
    "--mode", "apply"
)

if ($Wait) {
    $pythonArgs += @("--wait", "--timeout-seconds", "$TimeoutSeconds")
}

$pythonArgs += "--summary"

Push-Location $repoRoot
try {
    & python @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
