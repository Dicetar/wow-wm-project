param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [int]$GracefulWaitSeconds = 20,
    [int]$ForceAfterSeconds = 5
)

$ErrorActionPreference = "Stop"

$runDir = Join-Path $WorkspaceRoot "run"
$worldExe = Join-Path $runDir "bin\worldserver.exe"

if (-not (Test-Path -LiteralPath $worldExe)) {
    throw "Lab worldserver binary was not found: $worldExe"
}

function Get-LabWorldProcess {
    param([string]$ExecutablePath)
    return Get-Process worldserver -ErrorAction SilentlyContinue | Where-Object { $_.Path -ieq $ExecutablePath } | Select-Object -First 1
}

$existing = Get-LabWorldProcess -ExecutablePath $worldExe
if ($null -ne $existing) {
    $gracefulRequested = $false
    if ($existing.MainWindowHandle -ne 0) {
        try {
            $gracefulRequested = $existing.CloseMainWindow()
        } catch {
            $gracefulRequested = $false
        }
    }

    if ($gracefulRequested) {
        Write-Host "bridge_lab_worldserver_shutdown=graceful_requested pid=$($existing.Id)"
        $deadline = (Get-Date).AddSeconds([Math]::Max(1, $GracefulWaitSeconds))
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 500
            if (-not (Get-LabWorldProcess -ExecutablePath $worldExe)) {
                break
            }
        }
    }

    $existing = Get-LabWorldProcess -ExecutablePath $worldExe
    if ($null -ne $existing) {
        Write-Host "bridge_lab_worldserver_shutdown=force pid=$($existing.Id)"
        Stop-Process -Id $existing.Id -Force
        Start-Sleep -Seconds ([Math]::Max(1, $ForceAfterSeconds))
    }
}

$started = Start-Process -FilePath $worldExe -WorkingDirectory $runDir -ArgumentList "-c", "configs\worldserver.conf" -PassThru
Start-Sleep -Seconds 2

Write-Host "bridge_lab_worldserver_started=true pid=$($started.Id) exe=$worldExe"
