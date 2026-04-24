param(
    [string]$WorkspaceRoot = "D:\WOW\wm-project",
    [string]$BridgeLabRoot = "D:\WOW\WM_BridgeLab",
    [string]$DraftPath = "",
    [int]$SpellEntry = 947000,
    [int]$PlayerGuid = 5406,
    [ValidateSet("apply", "dry-run")]
    [string]$Mode = "apply",
    [switch]$AllRanks,
    [switch]$WaitForPlayerOnline,
    [double]$WaitTimeoutSeconds = 600.0,
    [double]$WaitPollSeconds = 2.0,
    [int]$LabMySqlPort = 33307,
    [int]$SoapPort = 7879
)

$ErrorActionPreference = "Stop"

$pythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
$mysqlBin = Join-Path $BridgeLabRoot "deps\mysql\bin\mysql.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python executable was not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $mysqlBin)) {
    throw "mysql.exe was not found: $mysqlBin"
}
if (-not [string]::IsNullOrWhiteSpace($DraftPath) -and -not (Test-Path -LiteralPath $DraftPath)) {
    throw "Managed spell draft was not found: $DraftPath"
}

$resolvedSpellEntry = [int]$SpellEntry
if (-not [string]::IsNullOrWhiteSpace($DraftPath)) {
    $rawDraft = Get-Content -LiteralPath $DraftPath -Raw | ConvertFrom-Json
    $draft = if ($null -ne $rawDraft.draft) { $rawDraft.draft } else { $rawDraft }
    if ($null -eq $draft -or $null -eq $draft.slot_kind -or $null -eq $draft.spell_entry) {
        throw "Managed spell draft is missing required fields: slot_kind / spell_entry."
    }
    if ([string]$draft.slot_kind -ne "visible_spell_slot") {
        throw "Draft slot_kind '$($draft.slot_kind)' is not directly learnable. Use a visible_spell_slot draft with base_visible_spell_id, not a helper/passive/item-trigger managed slot."
    }
    if ($null -eq $draft.base_visible_spell_id -or [int]$draft.base_visible_spell_id -le 0) {
        throw "Visible spell draft is missing base_visible_spell_id, so no learnable runtime spell can be resolved."
    }
    $resolvedSpellEntry = [int]$draft.base_visible_spell_id
}

$env:PYTHONPATH = "src"
$env:WM_MYSQL_BIN_PATH = $mysqlBin
$env:WM_WORLD_DB_HOST = "127.0.0.1"
$env:WM_WORLD_DB_PORT = [string]$LabMySqlPort
$env:WM_WORLD_DB_USER = "acore"
$env:WM_WORLD_DB_PASSWORD = "acore"
$env:WM_WORLD_DB_NAME = "acore_world"
$env:WM_CHAR_DB_HOST = "127.0.0.1"
$env:WM_CHAR_DB_PORT = [string]$LabMySqlPort
$env:WM_CHAR_DB_USER = "acore"
$env:WM_CHAR_DB_PASSWORD = "acore"
$env:WM_CHAR_DB_NAME = "acore_characters"
$env:WM_SOAP_PORT = [string]$SoapPort

Set-Location -LiteralPath $WorkspaceRoot
$grantArgs = @(
    "-m",
    "wm.content.workbench",
    "learn-spell",
    "--spell-entry",
    ([string]$resolvedSpellEntry),
    "--player-guid",
    ([string]$PlayerGuid),
    "--mode",
    $Mode
)
if ($AllRanks) {
    $grantArgs += "--all-ranks"
}
if ($WaitForPlayerOnline) {
    $grantArgs += @(
        "--wait-for-player-online",
        "--wait-timeout-seconds",
        ([string]$WaitTimeoutSeconds),
        "--wait-poll-seconds",
        ([string]$WaitPollSeconds)
    )
}

& $pythonExe @grantArgs
exit $LASTEXITCODE
