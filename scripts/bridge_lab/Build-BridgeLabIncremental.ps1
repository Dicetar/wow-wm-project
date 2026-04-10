param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [string]$Target = "worldserver",
    [switch]$NoStageRuntime
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $repoRoot "scripts\bootstrap\Common.ps1")

$manifestEnvelope = Get-BootstrapManifest -ManifestPath (Join-Path $repoRoot "bootstrap\sources.lock.json")
$manifest = $manifestEnvelope.data
$paths = Get-WorkspacePaths -RepoRoot $repoRoot -Manifest $manifest -WorkspaceRoot $WorkspaceRoot
$solutionPath = Join-Path $paths.buildRoot "AzerothCore.sln"

if (-not (Test-Path $solutionPath)) {
    throw "Generated solution was not found: $solutionPath. Run build-bridge-lab.bat once before using incremental builds."
}

$localModuleCount = @($manifest.local_modules).Count
if ($localModuleCount -gt 0) {
    Sync-LocalModules -RepoRoot $repoRoot -WorkspaceRoot $paths.root -CoreRoot $paths.coreRoot -Manifest $manifest
    Write-Host "bridge_lab_local_modules_resynced=true count=$localModuleCount"
}

$msbuild = Get-MSBuildPath
Invoke-Native -FilePath $msbuild -Arguments @(
    $solutionPath,
    "/m:1",
    "/p:Configuration=$($manifest.build.configuration)",
    "/t:$Target"
)

if (-not $NoStageRuntime) {
    & (Join-Path $PSScriptRoot "Stage-BridgeLabRuntime.ps1") -WorkspaceRoot $WorkspaceRoot
}

Write-Host "bridge_lab_incremental_build=true workspace=$($paths.root) target=$Target"
