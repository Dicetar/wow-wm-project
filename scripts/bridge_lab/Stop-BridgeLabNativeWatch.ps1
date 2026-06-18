param(
    [string]$WorkspaceRoot = "D:\WOW\wm-project",
    [int]$WaitSeconds = 5
)

$ErrorActionPreference = "Stop"

$root = Join-Path $WorkspaceRoot "artifacts\bridge_lab_native_watch"
$pidPath = Join-Path $root "native_bridge_watch.pid"
$metadataPath = Join-Path $root "native_bridge_watch.json"
$runtimeRoot = Join-Path $WorkspaceRoot ".wm-bootstrap\state\runtime"

function Add-Pid {
    param(
        [System.Collections.Generic.List[int]]$Pids,
        [Parameter(Mandatory = $true)]$Value
    )

    try {
        $pidValue = [int]$Value
    } catch {
        return
    }
    if ($pidValue -gt 0 -and -not $Pids.Contains($pidValue)) {
        $Pids.Add($pidValue) | Out-Null
    }
}

function Get-CandidateWatchPids {
    param(
        [Parameter(Mandatory = $true)][string]$PidPath,
        [Parameter(Mandatory = $true)][string]$RuntimeRoot
    )

    $pids = [System.Collections.Generic.List[int]]::new()
    if (Test-Path -LiteralPath $PidPath) {
        $rawPid = (Get-Content -LiteralPath $PidPath -Raw).Trim()
        if (-not [string]::IsNullOrWhiteSpace($rawPid)) {
            Add-Pid -Pids $pids -Value $rawPid
        }
    }

    if (Test-Path -LiteralPath $RuntimeRoot) {
        foreach ($markerPath in Get-ChildItem -LiteralPath $RuntimeRoot -Filter "watcher-*.json" -File) {
            try {
                $marker = Get-Content -LiteralPath $markerPath.FullName -Raw | ConvertFrom-Json
            } catch {
                continue
            }
            if ([string]$marker.service -ne "watcher") {
                continue
            }
            $health = ([string]$marker.health).ToLowerInvariant()
            if (@("stopped", "not_running", "exited") -contains $health) {
                continue
            }
            Add-Pid -Pids $pids -Value $marker.pid
        }
    }

    return $pids
}

function Clear-WatcherRuntimeMarkers {
    param([Parameter(Mandatory = $true)][string]$RuntimeRoot)

    if (-not (Test-Path -LiteralPath $RuntimeRoot)) {
        return 0
    }

    $removed = 0
    foreach ($markerPath in Get-ChildItem -LiteralPath $RuntimeRoot -Filter "watcher-*.json" -File) {
        try {
            $marker = Get-Content -LiteralPath $markerPath.FullName -Raw | ConvertFrom-Json
        } catch {
            continue
        }
        if ([string]$marker.service -ne "watcher") {
            continue
        }
        Remove-Item -LiteralPath $markerPath.FullName -Force
        $removed += 1
    }
    return $removed
}

$candidatePids = Get-CandidateWatchPids -PidPath $pidPath -RuntimeRoot $runtimeRoot
if ($candidatePids.Count -eq 0) {
    if (Test-Path -LiteralPath $pidPath) {
        Remove-Item -LiteralPath $pidPath -Force
    }
    $markersRemoved = Clear-WatcherRuntimeMarkers -RuntimeRoot $runtimeRoot
    Write-Host "bridge_lab_native_watch_stopped=false reason=no_pid_or_runtime_marker markers_removed=$markersRemoved"
    return
}

$stopped = @()
$alreadyExited = @()
foreach ($watchPid in $candidatePids) {
    $process = $null
    try {
        $process = Get-Process -Id $watchPid -ErrorAction Stop
    } catch {
        $process = $null
    }

    if ($null -eq $process) {
        $alreadyExited += $watchPid
        continue
    }

    Stop-Process -Id $watchPid -Force
    $stopped += $watchPid
}

if ($stopped.Count -gt 0) {
    Start-Sleep -Seconds ([Math]::Max(1, $WaitSeconds))
}

if (Test-Path -LiteralPath $pidPath) {
    Remove-Item -LiteralPath $pidPath -Force
}
if (Test-Path -LiteralPath $metadataPath) {
    Remove-Item -LiteralPath $metadataPath -Force
}
$markersRemoved = Clear-WatcherRuntimeMarkers -RuntimeRoot $runtimeRoot

Write-Host "bridge_lab_native_watch_stopped=true stopped_pids=$($stopped -join ',') already_exited_pids=$($alreadyExited -join ',') markers_removed=$markersRemoved"
