param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [ValidateRange(1, 1000)]
    [int]$BinlogsToKeep = 5,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$mysqlRoot = Join-Path $WorkspaceRoot "deps\mysql"
$mysqldPath = Join-Path $mysqlRoot "bin\mysqld.exe"
$dataDir = Join-Path $mysqlRoot "data"
$indexPath = Join-Path $dataDir "binlog.index"

if (-not (Test-Path -LiteralPath $mysqldPath)) {
    throw "Lab mysqld.exe was not found: $mysqldPath"
}
if (-not (Test-Path -LiteralPath $dataDir)) {
    throw "Lab MySQL data directory was not found: $dataDir"
}
if (-not (Test-Path -LiteralPath $indexPath)) {
    throw "Lab MySQL binlog index was not found: $indexPath"
}

$running = @(Get-Process mysqld -ErrorAction SilentlyContinue |
    Where-Object {
        try {
            $_.Path -ieq $mysqldPath
        } catch {
            $false
        }
    })

if ($running.Count -gt 0) {
    $pids = ($running | ForEach-Object { $_.Id }) -join ","
    throw "Refusing offline binlog prune while lab MySQL is running. Stop it first. pids=$pids"
}

$rawLines = @(Get-Content -LiteralPath $indexPath | Where-Object { $_.Trim().Length -gt 0 })
$entries = @()
foreach ($line in $rawLines) {
    $trimmed = $line.Trim()
    $name = Split-Path -Leaf $trimmed
    if ($name -notmatch "^binlog\.\d+$") {
        throw "Unexpected binlog index entry: $trimmed"
    }
    $entries += [pscustomobject]@{
        Line = $trimmed
        Name = $name
        Path = Join-Path $dataDir $name
    }
}

if ($entries.Count -le $BinlogsToKeep) {
    Write-Host "lab_mysql_binlogs_pruned=false reason=within_limit count=$($entries.Count) keep=$BinlogsToKeep"
    return
}

$removeCount = $entries.Count - $BinlogsToKeep
$remove = @($entries | Select-Object -First $removeCount)
$keep = @($entries | Select-Object -Skip $removeCount)

$bytes = 0L
foreach ($entry in $remove) {
    if (Test-Path -LiteralPath $entry.Path) {
        $bytes += [int64](Get-Item -LiteralPath $entry.Path).Length
    }
}

if (-not $Apply.IsPresent) {
    Write-Host "dry_run=true lab_mysql_binlogs_to_remove=$($remove.Count) keep=$BinlogsToKeep reclaim_mb=$([math]::Round($bytes / 1MB, 2))"
    Write-Host "first_removed=$($remove[0].Name) last_removed=$($remove[-1].Name) first_kept=$($keep[0].Name)"
    return
}

foreach ($entry in $remove) {
    if (Test-Path -LiteralPath $entry.Path) {
        Remove-Item -LiteralPath $entry.Path -Force
    }
}

Set-Content -LiteralPath $indexPath -Value ($keep | ForEach-Object { $_.Line }) -Encoding ASCII
Write-Host "lab_mysql_binlogs_pruned=true removed=$($remove.Count) keep=$BinlogsToKeep reclaimed_mb=$([math]::Round($bytes / 1MB, 2)) first_kept=$($keep[0].Name)"
