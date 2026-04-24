param(
    [string]$SourceSpellDbc = "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc",
    [string]$TargetSpellDbc = "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc",
    [ValidateSet("named", "all")]
    [string]$Include = "named",
    [ValidateSet("learnable", "castable")]
    [string]$SeedProfile = "learnable",
    [int[]]$SpellId
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$stateRoot = Join-Path $repoRoot ".wm-bootstrap\state\client-patches\wm_spell_shell_bank\server-spell-dbc"
$outputSpellDbc = Join-Path $stateRoot "Spell.dbc"
$backupRoot = Join-Path $stateRoot "backups"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

if (-not (Test-Path -LiteralPath $SourceSpellDbc)) {
    throw "Source Spell.dbc was not found: $SourceSpellDbc"
}

if (-not (Test-Path -LiteralPath (Split-Path -Parent $TargetSpellDbc))) {
    throw "Target Spell.dbc directory was not found: $(Split-Path -Parent $TargetSpellDbc)"
}

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

Push-Location $repoRoot
try {
    $materializeArgs = @(
        "-m",
        "wm.spells.server_dbc",
        "materialize",
        "--source-dbc",
        $SourceSpellDbc,
        "--out",
        $outputSpellDbc,
        "--include",
        $Include,
        "--seed-profile",
        $SeedProfile,
        "--summary"
    )
    foreach ($id in $SpellId) {
        $materializeArgs += @("--spell-id", [string]$id)
    }

    $materializeJson = & python @materializeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "wm.spells.server_dbc materialize failed."
    }
    $result = $materializeJson | ConvertFrom-Json

    if (Test-Path -LiteralPath $TargetSpellDbc) {
        $backupPath = Join-Path $backupRoot ("Spell-{0}.dbc" -f $timestamp)
        Copy-Item -LiteralPath $TargetSpellDbc -Destination $backupPath -Force
    } else {
        $backupPath = $null
    }

    Copy-Item -LiteralPath $outputSpellDbc -Destination $TargetSpellDbc -Force

    $inspectArgs = @(
        "-m",
        "wm.spells.server_dbc",
        "inspect",
        "--spell-dbc",
        $TargetSpellDbc,
        "--summary"
    )
    foreach ($selectedId in $result.selected_spell_ids) {
        $inspectArgs += @("--spell-id", [string]$selectedId)
    }
    $inspectionJson = & python @inspectArgs
    if ($LASTEXITCODE -ne 0) {
        throw "wm.spells.server_dbc inspect failed after staging."
    }
    $inspection = $inspectionJson | ConvertFrom-Json
}
finally {
    Pop-Location
}

$backupLabel = ""
if ($backupPath) {
    $backupLabel = $backupPath
}

Write-Host (
    "bridge_lab_server_spell_dbc_staged=true target={0} include={1} seed_profile={2} selected={3} appended={4} replaced={5} backup={6}" -f
    $TargetSpellDbc,
    $Include,
    $SeedProfile,
    (($result.selected_spell_ids | ForEach-Object { [string]$_ }) -join ","),
    $result.appended_count,
    $result.replaced_count,
    $backupLabel
)
Write-Host ("inspection_checked_ids={0}" -f (($inspection.checked_ids.PSObject.Properties | ForEach-Object { "" + $_.Name + "=" + $_.Value }) -join ","))
