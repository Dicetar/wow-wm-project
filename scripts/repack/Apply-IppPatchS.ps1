param(
    [string]$OptionalRoot = "D:\WOW\wm-project\optional",
    [string]$RepackDbcRoot = "D:\WOW\Azerothcore_WoTLK_Repack\data\dbc",
    [string]$RebuildDbcRoot = "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc",
    [string]$ClientDataRoot = "D:\WOW\world of warcraft 3.3.5a hd\data"
)

$ErrorActionPreference = "Stop"

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Backup-IfExists {
    param(
        [string]$SourcePath,
        [string]$BackupDirectory
    )

    if (Test-Path -LiteralPath $SourcePath) {
        Ensure-Directory -Path $BackupDirectory
        Copy-Item -LiteralPath $SourcePath -Destination (Join-Path $BackupDirectory (Split-Path -Leaf $SourcePath)) -Force
    }
}

function Copy-WithBackup {
    param(
        [string]$SourcePath,
        [string]$DestinationPath,
        [string]$BackupDirectory
    )

    Backup-IfExists -SourcePath $DestinationPath -BackupDirectory $BackupDirectory
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
}

function Write-HashSummary {
    param(
        [string]$Label,
        [string]$Path
    )

    $item = Get-Item -LiteralPath $Path
    $hash = Get-FileHash -LiteralPath $Path
    Write-Host ("{0}: {1} [{2}] {3}" -f $Label, $item.FullName, $item.Length, $hash.Hash)
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

$repackBackup = Join-Path $RepackDbcRoot "_backup_ipp_patchs_$stamp"
$rebuildBackup = Join-Path $RebuildDbcRoot "_backup_ipp_patchs_$stamp"
$clientBackup = Join-Path $ClientDataRoot "_backup_ipp_patchs_$stamp"

$skillFiles = @(
    "SkillLine.dbc",
    "SkillLineAbility.dbc",
    "SkillRaceClassInfo.dbc"
)

foreach ($file in $skillFiles) {
    $source = Join-Path $OptionalRoot $file
    Copy-WithBackup -SourcePath $source -DestinationPath (Join-Path $RepackDbcRoot $file) -BackupDirectory $repackBackup
    Copy-WithBackup -SourcePath $source -DestinationPath (Join-Path $RebuildDbcRoot $file) -BackupDirectory $rebuildBackup
}

$patchSSpell = Join-Path $OptionalRoot "patch-S\Spell.dbc"
Copy-WithBackup -SourcePath $patchSSpell -DestinationPath (Join-Path $RepackDbcRoot "Spell.dbc") -BackupDirectory $repackBackup
Copy-WithBackup -SourcePath $patchSSpell -DestinationPath (Join-Path $RebuildDbcRoot "Spell.dbc") -BackupDirectory $rebuildBackup

$clientPatchS = Join-Path $ClientDataRoot "patch-S.mpq"
$clientPatchLowerS = Join-Path $ClientDataRoot "patch-s.mpq"
$clientPatchV = Join-Path $ClientDataRoot "patch-V.mpq"

Backup-IfExists -SourcePath $clientPatchS -BackupDirectory $clientBackup
Backup-IfExists -SourcePath $clientPatchLowerS -BackupDirectory $clientBackup
Backup-IfExists -SourcePath $clientPatchV -BackupDirectory $clientBackup

if (Test-Path -LiteralPath $clientPatchLowerS) {
    Remove-Item -LiteralPath $clientPatchLowerS -Force
}
if (Test-Path -LiteralPath $clientPatchV) {
    Remove-Item -LiteralPath $clientPatchV -Force
}

Copy-Item -LiteralPath (Join-Path $OptionalRoot "patch-S\patch-S.mpq") -Destination $clientPatchS -Force

Write-Host "Applied IPP optional Patch-S payload with backups:"
Write-Host "  Repack backup:  $repackBackup"
Write-Host "  Rebuild backup: $rebuildBackup"
Write-Host "  Client backup:  $clientBackup"
Write-Host ""
Write-HashSummary -Label "Repack Spell.dbc" -Path (Join-Path $RepackDbcRoot "Spell.dbc")
Write-HashSummary -Label "Rebuild Spell.dbc" -Path (Join-Path $RebuildDbcRoot "Spell.dbc")
Write-HashSummary -Label "Client patch-S.mpq" -Path $clientPatchS
