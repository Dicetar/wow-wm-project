param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab"
)

$ErrorActionPreference = "Stop"
$mysqldPath = Join-Path $WorkspaceRoot "deps\mysql\bin\mysqld.exe"

$processes = @(Get-Process mysqld -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -ieq $mysqldPath })

if (-not $processes) {
    Write-Host "lab_mysql_stopped=true already_stopped=true"
    return
}

foreach ($process in $processes) {
    Stop-Process -Id $process.Id -Force
    Write-Host "lab_mysql_stopped=true pid=$($process.Id)"
}
