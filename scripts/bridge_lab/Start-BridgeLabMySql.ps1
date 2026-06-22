param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [int]$Port = 33307
)

$ErrorActionPreference = "Stop"
$mysqlRoot = Join-Path $WorkspaceRoot "deps\mysql"
$mysqldPath = Join-Path $mysqlRoot "bin\mysqld.exe"
$mysqlAdminPath = Join-Path $mysqlRoot "bin\mysqladmin.exe"
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
if (-not (Test-Path $mysqlAdminPath)) {
    throw "Lab mysqladmin.exe was not found: $mysqlAdminPath"
}

function Wait-LabMySqlReady {
    param(
        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = $mysqlAdminPath
        $startInfo.Arguments = "--host=127.0.0.1 --port=$Port --user=acore --password=acore ping"
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $probe = [System.Diagnostics.Process]::Start($startInfo)
        $probe.WaitForExit()
        if ($probe.ExitCode -eq 0) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)

    return $false
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$existing = Get-Process mysqld -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -ieq $mysqldPath } |
    Select-Object -First 1

if ($existing) {
    if (Wait-LabMySqlReady -TimeoutSeconds 30) {
        Write-Host "lab_mysql_started=true already_running=true pid=$($existing.Id) port=$Port"
        return
    }
    throw "Lab MySQL process $($existing.Id) exists but did not become ready on port $Port."
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
if (-not (Wait-LabMySqlReady -TimeoutSeconds 30)) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "lab_mysql_started=false pid=$($process.Id) port=$Port"
    if (Test-Path $errorLogPath) {
        Get-Content -Path $errorLogPath -Tail 80
    }
    throw "Lab MySQL did not become ready on port $Port within 30 seconds."
}

Write-Host "lab_mysql_started=true pid=$($process.Id) port=$Port"
