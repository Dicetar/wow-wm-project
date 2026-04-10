param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [int]$Port = 33307
)

$ErrorActionPreference = "Stop"
$mysqlRoot = Join-Path $WorkspaceRoot "deps\mysql"
$mysqldPath = Join-Path $mysqlRoot "bin\mysqld.exe"
$dataDir = Join-Path $mysqlRoot "data"
$logRoot = Join-Path $WorkspaceRoot "logs"
$pidPath = Join-Path $logRoot "mysql-lab.pid"
$errorLogPath = Join-Path $logRoot "mysql-lab.err"

if (-not (Test-Path $mysqldPath)) {
    throw "Lab mysqld.exe was not found: $mysqldPath"
}
if (-not (Test-Path $dataDir)) {
    throw "Lab MySQL data directory was not found: $dataDir"
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$existing = Get-Process mysqld -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -ieq $mysqldPath } |
    Select-Object -First 1

if ($existing) {
    Write-Host "lab_mysql_started=true already_running=true pid=$($existing.Id) port=$Port"
    return
}

$args = @(
    "--datadir=$dataDir",
    "--port=$Port",
    "--bind-address=127.0.0.1",
    "--mysqlx=0",
    "--pid-file=$pidPath",
    "--log-error=$errorLogPath"
)

$process = Start-Process -FilePath $mysqldPath -ArgumentList $args -WorkingDirectory $mysqlRoot -PassThru
Start-Sleep -Seconds 5

if ($process.HasExited) {
    Write-Host "lab_mysql_started=false exit=$($process.ExitCode)"
    if (Test-Path $errorLogPath) {
        Get-Content -Path $errorLogPath -Tail 80
    }
    exit 1
}

Write-Host "lab_mysql_started=true pid=$($process.Id) port=$Port"
