param(
    [string]$WorkspaceRoot = "D:\WOW\wm-project",
    [int]$WaitSeconds = 5
)

$ErrorActionPreference = "Stop"

$root = Join-Path $WorkspaceRoot "artifacts\bridge_lab_native_watch"
$pidPath = Join-Path $root "native_bridge_watch.pid"
$metadataPath = Join-Path $root "native_bridge_watch.json"

if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Host "bridge_lab_native_watch_stopped=false reason=no_pid_file"
    return
}

$rawPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($rawPid)) {
    Remove-Item -LiteralPath $pidPath -Force
    Write-Host "bridge_lab_native_watch_stopped=false reason=empty_pid_file"
    return
}

$watchPid = [int]$rawPid
$process = $null
try {
    $process = Get-Process -Id $watchPid -ErrorAction Stop
} catch {
    $process = $null
}

if ($null -eq $process) {
    Remove-Item -LiteralPath $pidPath -Force
    if (Test-Path -LiteralPath $metadataPath) {
        Remove-Item -LiteralPath $metadataPath -Force
    }
    Write-Host "bridge_lab_native_watch_stopped=true pid=$watchPid already_exited=true"
    return
}

Stop-Process -Id $watchPid -Force
Start-Sleep -Seconds ([Math]::Max(1, $WaitSeconds))

Remove-Item -LiteralPath $pidPath -Force
if (Test-Path -LiteralPath $metadataPath) {
    Remove-Item -LiteralPath $metadataPath -Force
}

Write-Host "bridge_lab_native_watch_stopped=true pid=$watchPid"
