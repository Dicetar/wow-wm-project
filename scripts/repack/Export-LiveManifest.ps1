param(
    [string]$RepackRoot = "D:\WOW\Azerothcore_WoTLK_Repack",
    [string]$OutputDir = "data/repack"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = Join-Path $repoRoot $OutputDir
}

& $python -m wm.repack.discovery --repack-root $RepackRoot --output-dir $OutputDir --summary
