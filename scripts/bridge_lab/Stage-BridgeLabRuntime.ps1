param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $repoRoot "scripts\bootstrap\Common.ps1")

$manifestEnvelope = Get-BootstrapManifest -ManifestPath (Join-Path $repoRoot "bootstrap\sources.lock.json")
$manifest = $manifestEnvelope.data
$paths = Get-WorkspacePaths -RepoRoot $repoRoot -Manifest $manifest -WorkspaceRoot $WorkspaceRoot

$mysqlRoot = Get-DependencyInstallRoot -Manifest $manifest -WorkspaceRoot $paths.root -Key "mysql"
$openSslRoot = Get-DependencyInstallRoot -Manifest $manifest -WorkspaceRoot $paths.root -Key "openssl"
$buildBinRoot = Join-Path $paths.buildRoot ("bin\" + $manifest.build.configuration)

if (-not (Test-Path (Join-Path $buildBinRoot "worldserver.exe"))) {
    throw "worldserver.exe was not found in '$buildBinRoot'. Run build-bridge-lab.bat or incremental-bridge-lab.bat first."
}

Stage-RuntimeDependencies -BinRoot $buildBinRoot -MySQLRoot $mysqlRoot -OpenSSLRoot $openSslRoot
$lockPath = Write-RuntimeDllLock -BinRoot $buildBinRoot -StateRoot $paths.stateRoot
Copy-BuildOutputToRun -BuildBinRoot $buildBinRoot -RunRoot $paths.runRoot

Save-JsonFile -Path (Join-Path $paths.stateRoot "build-summary.json") -Value ([pscustomobject]@{
    workspace_root = $paths.root
    build_root = $paths.buildRoot
    run_root = $paths.runRoot
    run_bin_root = Join-Path $paths.runRoot "bin"
    configuration = $manifest.build.configuration
    staged_incremental = $true
    runtime_dll_lock = $lockPath
})

Write-Host "lab_runtime_staged=true workspace=$($paths.root) run=$($paths.runRoot) lock=$lockPath"
