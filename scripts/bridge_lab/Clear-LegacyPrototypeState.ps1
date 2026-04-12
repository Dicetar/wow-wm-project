param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 33307,
    [string]$User = "acore",
    [string]$Password = "acore",
    [string]$CharactersDatabase = "acore_characters",
    [string]$WorldDatabase = "acore_world"
)

$ErrorActionPreference = "Stop"

$mysqlBin = Join-Path $WorkspaceRoot "deps\mysql\bin\mysql.exe"
if (-not (Test-Path -LiteralPath $mysqlBin)) {
    throw "mysql.exe was not found at $mysqlBin"
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$characterSqlPath = Join-Path $repoRoot "sql\dev\clear_jecia_legacy_summon_state_characters.sql"
$worldSqlPath = Join-Path $repoRoot "sql\dev\clear_jecia_legacy_summon_state_world.sql"

foreach ($required in @($characterSqlPath, $worldSqlPath)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required SQL file was not found: $required"
    }
}

function Invoke-MySqlScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Database,
        [Parameter(Mandatory = $true)]
        [string]$SqlPath
    )

    $sql = Get-Content -LiteralPath $SqlPath -Raw
    if ([string]::IsNullOrWhiteSpace($sql)) {
        throw "SQL file is empty: $SqlPath"
    }

    $args = @(
        "--host=$HostName",
        "--port=$Port",
        "--user=$User",
        "--database=$Database",
        "--batch",
        "--raw",
        "--execute=$sql"
    )

    $previousPassword = $env:MYSQL_PWD
    try {
        $env:MYSQL_PWD = $Password
        $output = & $mysqlBin @args 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "mysql execution failed for $Database using $SqlPath`n$output"
        }
        return ($output | Out-String).Trim()
    } finally {
        if ($null -eq $previousPassword) {
            Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
        } else {
            $env:MYSQL_PWD = $previousPassword
        }
    }
}

$characterOutput = Invoke-MySqlScript -Database $CharactersDatabase -SqlPath $characterSqlPath
$worldOutput = Invoke-MySqlScript -Database $WorldDatabase -SqlPath $worldSqlPath

Write-Host "legacy_cleanup_characters_db=$CharactersDatabase"
if ($characterOutput) {
    Write-Host $characterOutput
}

Write-Host "legacy_cleanup_world_db=$WorldDatabase"
if ($worldOutput) {
    Write-Host $worldOutput
}
