param(
    [string]$WorkspaceRoot = "D:\WOW\wm-project",
    [string]$BridgeLabRoot = "D:\WOW\WM_BridgeLab",
    [int]$PlayerGuid = 5406,
    [ValidateSet("apply", "dry-run")]
    [string]$Mode = "apply",
    [double]$IntervalSeconds = 1.0,
    [int]$LabMySqlPort = 33307,
    [int]$SoapPort = 7879,
    [ValidateSet("auto", "native", "soap")]
    [string]$QuestGrantTransport = "auto",
    [switch]$ArmFromEnd,
    [switch]$PrintIdle
)

$ErrorActionPreference = "Stop"

function Convert-ToPsLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-WatchPaths {
    param([Parameter(Mandatory = $true)][string]$WorkspaceRoot)

    $root = Join-Path $WorkspaceRoot "artifacts\bridge_lab_native_watch"
    return @{
        Root = $root
        Runner = Join-Path $root "run-native-watch.ps1"
        Pid = Join-Path $root "native_bridge_watch.pid"
        Metadata = Join-Path $root "native_bridge_watch.json"
        Stdout = Join-Path $root "native_bridge_watch.stdout.log"
        Stderr = Join-Path $root "native_bridge_watch.stderr.log"
    }
}

function Get-ExistingWatchProcess {
    param([Parameter(Mandatory = $true)][string]$PidPath)

    if (-not (Test-Path -LiteralPath $PidPath)) {
        return $null
    }

    $rawPid = (Get-Content -LiteralPath $PidPath -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($rawPid)) {
        return $null
    }

    try {
        return Get-Process -Id ([int]$rawPid) -ErrorAction Stop
    } catch {
        return $null
    }
}

$paths = Get-WatchPaths -WorkspaceRoot $WorkspaceRoot
New-Item -ItemType Directory -Force -Path $paths.Root | Out-Null

$existing = Get-ExistingWatchProcess -PidPath $paths.Pid
if ($null -ne $existing) {
    Write-Host "bridge_lab_native_watch_running=true pid=$($existing.Id) stdout=$($paths.Stdout) stderr=$($paths.Stderr)"
    return
}

$pythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
$bridgeConfig = Join-Path $BridgeLabRoot "run\configs\modules\mod_wm_bridge.conf"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python executable was not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $bridgeConfig)) {
    throw "Bridge config was not found: $bridgeConfig"
}

$argumentsLiteral = @(
    "'-u'",
    "'-m'",
    "'wm.events.watch'",
    "'--adapter'",
    "'native_bridge'",
    "'--mode'",
    (Convert-ToPsLiteral $Mode),
    "'--player-guid'",
    (Convert-ToPsLiteral ([string]$PlayerGuid)),
    "'--summary'",
    "'--interval-seconds'",
    (Convert-ToPsLiteral ([string]$IntervalSeconds))
)
if ($Mode -eq "apply") {
    $argumentsLiteral += "'--confirm-live-apply'"
}
if ($ArmFromEnd.IsPresent) {
    $argumentsLiteral += "'--arm-from-end'"
}
if ($PrintIdle.IsPresent) {
    $argumentsLiteral += "'--print-idle'"
}

$runnerLines = @(
    '$ErrorActionPreference = "Stop"',
    ('$env:PYTHONPATH = ' + (Convert-ToPsLiteral 'src')),
    ('$env:WM_WORLD_DB_PORT = ' + (Convert-ToPsLiteral ([string]$LabMySqlPort))),
    ('$env:WM_CHAR_DB_PORT = ' + (Convert-ToPsLiteral ([string]$LabMySqlPort))),
    ('$env:WM_SOAP_PORT = ' + (Convert-ToPsLiteral ([string]$SoapPort))),
    ('$env:WM_BRIDGE_CONFIG_PATH = ' + (Convert-ToPsLiteral $bridgeConfig)),
    ('$env:WM_QUEST_GRANT_TRANSPORT = ' + (Convert-ToPsLiteral $QuestGrantTransport)),
    ('Set-Location ' + (Convert-ToPsLiteral $WorkspaceRoot)),
    ('$arguments = @(' + ($argumentsLiteral -join ', ') + ')'),
    ('& ' + (Convert-ToPsLiteral $pythonExe) + ' @arguments 1>> ' + (Convert-ToPsLiteral $paths.Stdout) + ' 2>> ' + (Convert-ToPsLiteral $paths.Stderr))
)

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllLines($paths.Runner, $runnerLines, $utf8NoBom)

$powershellExe = Join-Path $PSHOME "powershell.exe"
$quotedRunner = '"' + $paths.Runner.Replace('"', '""') + '"'
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $powershellExe
$startInfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -File $quotedRunner"
$startInfo.WorkingDirectory = $WorkspaceRoot
# UseShellExecute keeps the long-running watcher from inheriting the Codex shell
# process tree/stdio lifetime. Environment setup stays inside the runner script.
$startInfo.UseShellExecute = $true
$startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

$process = [System.Diagnostics.Process]::Start($startInfo)
if ($null -eq $process) {
    throw "Failed to start the bridge-lab native watcher."
}

Start-Sleep -Seconds 2
if ($process.HasExited) {
    $stderrTail = ""
    if (Test-Path -LiteralPath $paths.Stderr) {
        $stderrTail = (Get-Content -LiteralPath $paths.Stderr -Tail 20) -join [Environment]::NewLine
    }
    throw ("Bridge-lab native watcher exited during startup." + $(if ($stderrTail) { "`n$stderrTail" } else { "" }))
}

[System.IO.File]::WriteAllText($paths.Pid, [string]$process.Id, $utf8NoBom)
$metadata = @{
    pid = $process.Id
    started_at = (Get-Date).ToString("s")
    workspace_root = $WorkspaceRoot
    bridge_lab_root = $BridgeLabRoot
    player_guid = $PlayerGuid
    mode = $Mode
    interval_seconds = $IntervalSeconds
    arm_from_end = [bool]$ArmFromEnd.IsPresent
    print_idle = [bool]$PrintIdle.IsPresent
    quest_grant_transport = $QuestGrantTransport
    stdout_log = $paths.Stdout
    stderr_log = $paths.Stderr
    runner_script = $paths.Runner
}
[System.IO.File]::WriteAllText($paths.Metadata, ($metadata | ConvertTo-Json -Depth 4), $utf8NoBom)

Write-Host "bridge_lab_native_watch_started=true pid=$($process.Id) stdout=$($paths.Stdout) stderr=$($paths.Stderr)"
