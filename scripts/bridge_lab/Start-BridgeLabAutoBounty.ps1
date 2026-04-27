param(
    [string]$WorkspaceRoot = "D:\WOW\wm-project",
    [string]$BridgeLabRoot = "D:\WOW\WM_BridgeLab",
    [int]$PlayerGuid = 5406,
    [ValidateSet("apply", "dry-run")]
    [string]$Mode = "apply",
    [double]$IntervalSeconds = 1.0,
    [int]$BatchSize = 1,
    [int]$ReactiveAutoBountyMaxEventAgeSeconds = 3600,
    [bool]$ReactiveAutoBountySingleOpenPerPlayer = $true,
    [int]$LabMySqlPort = 33307,
    [int]$SoapPort = 7879,
    [ValidateSet("auto", "native", "soap")]
    [string]$QuestGrantTransport = "auto",
    [switch]$EnableRandomEnchantOnKill,
    [double]$RandomEnchantOnKillChancePct = 7.0,
    [double]$RandomEnchantPreserveExistingChancePct = 15.0,
    [int]$RandomEnchantMaxEnchants = 3,
    [string]$RandomEnchantSelector = "random_equipped",
    [int]$RandomEnchantConsumableItemEntry = 910007,
    [int]$RandomEnchantConsumableCount = 1,
    [bool]$RandomEnchantFocusedOnKillEnabled = $true,
    [double]$RandomEnchantFocusedOnKillChancePct = 3.5,
    [int]$RandomEnchantFocusedConsumableItemEntry = 910008,
    [int]$RandomEnchantFocusedConsumableCount = 1,
    [int]$QuestSlotSeedStart = 910000,
    [int]$QuestSlotSeedEnd = 910999,
    [switch]$SkipQuestSlotSeed,
    [switch]$KeepExistingBountyRules,
    [switch]$KeepExistingEventBacklog,
    [switch]$PrintIdle,
    [switch]$DoNotArmFromEnd
)

$ErrorActionPreference = "Stop"

$pythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
$bridgeConfig = Join-Path $BridgeLabRoot "run\configs\modules\mod_wm_bridge.conf"
$stopWatchScript = Join-Path $WorkspaceRoot "scripts\bridge_lab\Stop-BridgeLabNativeWatch.ps1"
$startWatchScript = Join-Path $WorkspaceRoot "scripts\bridge_lab\Start-BridgeLabNativeWatch.ps1"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python executable was not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $bridgeConfig)) {
    throw "Bridge config was not found: $bridgeConfig"
}
if (-not (Test-Path -LiteralPath $stopWatchScript)) {
    throw "Stop watcher helper was not found: $stopWatchScript"
}
if (-not (Test-Path -LiteralPath $startWatchScript)) {
    throw "Start watcher helper was not found: $startWatchScript"
}

$env:PYTHONPATH = "src"
$env:WM_WORLD_DB_PORT = [string]$LabMySqlPort
$env:WM_CHAR_DB_PORT = [string]$LabMySqlPort
$env:WM_SOAP_PORT = [string]$SoapPort
$env:WM_BRIDGE_CONFIG_PATH = $bridgeConfig

Set-Location -LiteralPath $WorkspaceRoot

if (-not $SkipQuestSlotSeed.IsPresent) {
    $seedArgs = @(
        "-m",
        "wm.reserved.seed",
        "--entity-type",
        "quest",
        "--start-id",
        ([string]$QuestSlotSeedStart),
        "--end-id",
        ([string]$QuestSlotSeedEnd),
        "--mode",
        "apply",
        "--summary"
    )
    & $pythonExe @seedArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& $stopWatchScript -WorkspaceRoot $WorkspaceRoot

$autoArgs = @(
    "-m",
    "wm.reactive.auto_bounty",
    "--player-guid",
    ([string]$PlayerGuid),
    "--summary"
)
if (-not $KeepExistingBountyRules.IsPresent) {
    $autoArgs += "--deactivate-existing-bounty-rules"
}

& $pythonExe @autoArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$watchArgs = @{
    WorkspaceRoot = $WorkspaceRoot
    BridgeLabRoot = $BridgeLabRoot
    PlayerGuid = $PlayerGuid
    Mode = $Mode
    IntervalSeconds = $IntervalSeconds
    BatchSize = $BatchSize
    ReactiveAutoBountyMaxEventAgeSeconds = $ReactiveAutoBountyMaxEventAgeSeconds
    ReactiveAutoBountySingleOpenPerPlayer = $ReactiveAutoBountySingleOpenPerPlayer
    LabMySqlPort = $LabMySqlPort
    SoapPort = $SoapPort
    QuestGrantTransport = $QuestGrantTransport
    RandomEnchantOnKillChancePct = $RandomEnchantOnKillChancePct
    RandomEnchantPreserveExistingChancePct = $RandomEnchantPreserveExistingChancePct
    RandomEnchantMaxEnchants = $RandomEnchantMaxEnchants
    RandomEnchantSelector = $RandomEnchantSelector
    RandomEnchantConsumableItemEntry = $RandomEnchantConsumableItemEntry
    RandomEnchantConsumableCount = $RandomEnchantConsumableCount
    RandomEnchantFocusedOnKillEnabled = $RandomEnchantFocusedOnKillEnabled
    RandomEnchantFocusedOnKillChancePct = $RandomEnchantFocusedOnKillChancePct
    RandomEnchantFocusedConsumableItemEntry = $RandomEnchantFocusedConsumableItemEntry
    RandomEnchantFocusedConsumableCount = $RandomEnchantFocusedConsumableCount
    EnableReactiveAutoBounty = $true
}
if ($EnableRandomEnchantOnKill.IsPresent) {
    $watchArgs["EnableRandomEnchantOnKill"] = $true
}
if (-not $DoNotArmFromEnd.IsPresent) {
    $watchArgs["ArmFromEnd"] = $true
    if (-not $KeepExistingEventBacklog.IsPresent) {
        $watchArgs["MarkExistingEvaluatedOnArm"] = $true
    }
}
if ($PrintIdle.IsPresent) {
    $watchArgs["PrintIdle"] = $true
}

& $startWatchScript @watchArgs
exit $LASTEXITCODE
