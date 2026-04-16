param(
    [string]$WorkspaceRoot = "D:\WOW\wm-project",
    [string]$BridgeLabRoot = "D:\WOW\WM_BridgeLab",
    [string]$TemplatePath = "",
    [string]$TemplateKey = "defias_bandits_guard_thomas",
    [int]$PlayerGuid = 5406,
    [ValidateSet("apply", "dry-run")]
    [string]$Mode = "apply",
    [int]$LabMySqlPort = 33307,
    [int]$SoapPort = 7879
)

$ErrorActionPreference = "Stop"

$pythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
$bridgeConfig = Join-Path $BridgeLabRoot "run\configs\modules\mod_wm_bridge.conf"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python executable was not found: $pythonExe"
}
if ($TemplatePath -and -not (Test-Path -LiteralPath $TemplatePath)) {
    throw "Reactive bounty template was not found: $TemplatePath"
}
if (-not (Test-Path -LiteralPath $bridgeConfig)) {
    throw "Bridge config was not found: $bridgeConfig"
}

$env:PYTHONPATH = "src"
$env:WM_WORLD_DB_PORT = [string]$LabMySqlPort
$env:WM_CHAR_DB_PORT = [string]$LabMySqlPort
$env:WM_SOAP_PORT = [string]$SoapPort
$env:WM_BRIDGE_CONFIG_PATH = $bridgeConfig

Set-Location -LiteralPath $WorkspaceRoot
$installArgs = @(
    "-m",
    "wm.reactive.install_bounty",
    "--player-guid",
    ([string]$PlayerGuid),
    "--mode",
    $Mode,
    "--summary"
)
if ($TemplatePath) {
    $installArgs += @("--template", $TemplatePath)
} else {
    $installArgs += @("--template-key", $TemplateKey)
}
& $pythonExe @installArgs
