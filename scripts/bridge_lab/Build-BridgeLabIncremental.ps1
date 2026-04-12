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

$cmake = Get-CMakePath
$reconfigure = Test-CMakeReconfigureRequired `
    -BuildRoot $paths.buildRoot `
    -RepoRoot $repoRoot `
    -Manifest $manifest `
    -CoreRoot $paths.coreRoot
if ($reconfigure.required) {
    Invoke-WorkspaceCMakeConfigure `
        -CMakePath $cmake `
        -WorkspaceRoot $paths.root `
        -Manifest $manifest `
        -CoreRoot $paths.coreRoot `
        -BuildRoot $paths.buildRoot
    $patched = Repair-WorldserverResourceProject -BuildRoot $paths.buildRoot -SourceRoot $paths.coreRoot
    if (-not $patched) {
        throw "worldserver.vcxproj was not found under $($paths.buildRoot)"
    }
    $fingerprint = Save-CMakeConfigureState `
        -BuildRoot $paths.buildRoot `
        -RepoRoot $repoRoot `
        -Manifest $manifest `
        -CoreRoot $paths.coreRoot
    Write-Host "bridge_lab_cmake_reconfigured=true reason=$($reconfigure.reason) hash=$($fingerprint.hash) files=$($fingerprint.file_count)"
}

$patched = Repair-WorldserverResourceProject -BuildRoot $paths.buildRoot -SourceRoot $paths.coreRoot
if ($Target -ieq "worldserver" -and -not $patched) {
    throw "worldserver.vcxproj was not found under $($paths.buildRoot)"
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
