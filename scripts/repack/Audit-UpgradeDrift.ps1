param(
    [string]$ManifestPath = "data/repack/live-repack-manifest.json",
    [string]$SourceRoot = "D:\WOW\Azerothcore_WoTLK_Rebuild\source\azerothcore",
    [string]$Output = "data/repack/upgrade-drift-report.md"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if (-not [System.IO.Path]::IsPathRooted($ManifestPath)) {
    $ManifestPath = Join-Path $repoRoot $ManifestPath
}
if (-not [System.IO.Path]::IsPathRooted($SourceRoot)) {
    $SourceRoot = Join-Path $repoRoot $SourceRoot
}
if (-not [System.IO.Path]::IsPathRooted($Output)) {
    $Output = Join-Path $repoRoot $Output
}

& $python -m wm.repack.audit_upgrade --manifest $ManifestPath --source-root $SourceRoot --output $Output --summary
