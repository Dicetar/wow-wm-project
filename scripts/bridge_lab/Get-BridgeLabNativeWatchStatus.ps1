param(
    [string]$WorkspaceRoot = "D:\WOW\wm-project",
    [int]$TailLines = 20
)

$ErrorActionPreference = "Stop"

$root = Join-Path $WorkspaceRoot "artifacts\bridge_lab_native_watch"
$pidPath = Join-Path $root "native_bridge_watch.pid"
$metadataPath = Join-Path $root "native_bridge_watch.json"
$stdoutPath = Join-Path $root "native_bridge_watch.stdout.log"
$stderrPath = Join-Path $root "native_bridge_watch.stderr.log"

$watchPid = $null
if (Test-Path -LiteralPath $pidPath) {
    $rawPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
    if (-not [string]::IsNullOrWhiteSpace($rawPid)) {
        $watchPid = [int]$rawPid
    }
}

$process = $null
if ($null -ne $watchPid) {
    try {
        $process = Get-Process -Id $watchPid -ErrorAction Stop
    } catch {
        $process = $null
    }
}

Write-Host "bridge_lab_native_watch_running=$([bool]($null -ne $process)) pid=$watchPid stdout=$stdoutPath stderr=$stderrPath"
if ($null -ne $process) {
    Write-Host "bridge_lab_native_watch_process_name=$($process.ProcessName) started_at=$($process.StartTime.ToString('s'))"
}
if (Test-Path -LiteralPath $metadataPath) {
    Write-Host "bridge_lab_native_watch_metadata=$metadataPath"
}

if ($TailLines -gt 0) {
    Write-Host "--- stdout ---"
    if (Test-Path -LiteralPath $stdoutPath) {
        Get-Content -LiteralPath $stdoutPath -Tail $TailLines
    }
    Write-Host "--- stderr ---"
    if (Test-Path -LiteralPath $stderrPath) {
        Get-Content -LiteralPath $stderrPath -Tail $TailLines
    }
}
