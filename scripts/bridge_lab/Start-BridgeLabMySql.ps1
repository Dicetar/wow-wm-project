param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [int]$Port = 33307,
    [ValidateRange(1, 1000)]
    [int]$BinlogsToKeep = 5,
    [string]$MaintenanceUser = $env:WM_BRIDGELAB_MYSQL_MAINT_USER,
    [string]$MaintenancePassword = $env:WM_BRIDGELAB_MYSQL_MAINT_PASSWORD
)

$ErrorActionPreference = "Stop"
$mysqlRoot = Join-Path $WorkspaceRoot "deps\mysql"
$mysqldPath = Join-Path $mysqlRoot "bin\mysqld.exe"
$mysqlAdminPath = Join-Path $mysqlRoot "bin\mysqladmin.exe"
$mysqlPath = Join-Path $mysqlRoot "bin\mysql.exe"
$dataDir = Join-Path $mysqlRoot "data"
$logRoot = Join-Path $WorkspaceRoot "logs"
$pidPath = Join-Path $logRoot "mysql-lab.pid"
$errorLogPath = Join-Path $logRoot "mysql-lab.err"

if ([string]::IsNullOrWhiteSpace($MaintenanceUser)) {
    $MaintenanceUser = "acore"
}
if ([string]::IsNullOrWhiteSpace($MaintenancePassword) -and $MaintenanceUser -ieq "acore") {
    $MaintenancePassword = "acore"
}

if (-not (Test-Path $mysqldPath)) {
    throw "Lab mysqld.exe was not found: $mysqldPath"
}
if (-not (Test-Path $dataDir)) {
    throw "Lab MySQL data directory was not found: $dataDir"
}
if (-not (Test-Path $mysqlAdminPath)) {
    throw "Lab mysqladmin.exe was not found: $mysqlAdminPath"
}
if (-not (Test-Path $mysqlPath)) {
    throw "Lab mysql.exe was not found: $mysqlPath"
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

function Invoke-LabMySqlQuery {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Sql
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $mysqlPath
    $escapedSql = $Sql.Replace('"', '\"')
    $passwordArg = if ([string]::IsNullOrEmpty($MaintenancePassword)) { "" } else { " --password=$MaintenancePassword" }
    $startInfo.Arguments = "--host=127.0.0.1 --port=$Port --user=$MaintenanceUser$passwordArg --batch --skip-column-names --execute=`"$escapedSql`""
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $query = [System.Diagnostics.Process]::Start($startInfo)
    $stdout = $query.StandardOutput.ReadToEnd()
    $stderr = $query.StandardError.ReadToEnd()
    $query.WaitForExit()

    if ($query.ExitCode -ne 0) {
        throw "Lab MySQL query failed with exit code $($query.ExitCode): $stderr"
    }

    return $stdout -split "`r?`n" | Where-Object { $_.Trim().Length -gt 0 }
}

function Sync-LabMySqlBinlogs {
    $rows = @(Invoke-LabMySqlQuery -Sql "SHOW BINARY LOGS")
    if ($rows.Count -le $BinlogsToKeep) {
        Write-Host "lab_mysql_binlogs_pruned=false reason=within_limit count=$($rows.Count) keep=$BinlogsToKeep"
        return
    }

    $logs = @()
    foreach ($row in $rows) {
        $name = ($row -split "`t")[0].Trim()
        if ($name.Length -gt 0) {
            $logs += $name
        }
    }

    if ($logs.Count -le $BinlogsToKeep) {
        Write-Host "lab_mysql_binlogs_pruned=false reason=within_limit count=$($logs.Count) keep=$BinlogsToKeep"
        return
    }

    $purgeTo = $logs[$logs.Count - $BinlogsToKeep]
    Invoke-LabMySqlQuery -Sql "PURGE BINARY LOGS TO '$purgeTo'" | Out-Null
    Write-Host "lab_mysql_binlogs_pruned=true before=$($logs.Count) keep=$BinlogsToKeep purge_to=$purgeTo"
}

function Try-SyncLabMySqlBinlogs {
    try {
        Sync-LabMySqlBinlogs
    } catch {
        Write-Warning "lab_mysql_binlogs_pruned=false reason=maintenance_query_failed user=$MaintenanceUser message=$($_.Exception.Message)"
    }
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$existing = Get-Process mysqld -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -ieq $mysqldPath } |
    Select-Object -First 1

if ($existing) {
    if (Wait-LabMySqlReady -TimeoutSeconds 30) {
        Write-Host "lab_mysql_started=true already_running=true pid=$($existing.Id) port=$Port"
        Try-SyncLabMySqlBinlogs
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
Try-SyncLabMySqlBinlogs
