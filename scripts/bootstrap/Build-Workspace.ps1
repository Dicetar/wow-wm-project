param(
    [string]$ManifestPath = "bootstrap/sources.lock.json",
    [string]$WorkspaceRoot,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host $Message
    if ($WhatIf) {
        return
    }
    & $Action
}

$manifestEnvelope = Get-BootstrapManifest -ManifestPath $ManifestPath
$repoRoot = $manifestEnvelope.root
$manifest = $manifestEnvelope.data
$paths = Get-WorkspacePaths -RepoRoot $repoRoot -Manifest $manifest -WorkspaceRoot $WorkspaceRoot

if (-not $WhatIf) {
    foreach ($requiredPath in @($paths.coreRoot, $paths.depsRoot, $paths.stateRoot)) {
        if (-not (Test-Path $requiredPath)) {
            throw "Workspace is not ready. Missing required path: $requiredPath. Run setup-wm.bat first."
        }
    }
}

$cmake = Get-CMakePath
$msbuild = Get-MSBuildPath
$boostRoot = Get-DependencyInstallRoot -Manifest $manifest -WorkspaceRoot $paths.root -Key "boost"
$mysqlRoot = Get-DependencyInstallRoot -Manifest $manifest -WorkspaceRoot $paths.root -Key "mysql"
$openSslRoot = Get-DependencyInstallRoot -Manifest $manifest -WorkspaceRoot $paths.root -Key "openssl"
$compatibilityOverlayScript = Join-Path $repoRoot "scripts\repack\Apply-RepackCompatibilityOverlay.ps1"
$buildBinRoot = Join-Path $paths.buildRoot ("bin\" + $manifest.build.configuration)

Invoke-Step "Staging repo SQL overrides into AzerothCore custom SQL paths" {
    Stage-RepoSqlOverrides -RepoRoot $repoRoot -SourceRoot $paths.coreRoot -Manifest $manifest
}

Invoke-Step "Applying module compatibility overlay patches" {
    & $compatibilityOverlayScript -WorkspaceRoot $paths.root -SourceRoot $paths.coreRoot
    if (-not $?) {
        throw "Compatibility overlay script failed."
    }
}

Invoke-Step "Generating Visual Studio build files in $($paths.buildRoot)" {
    Reset-BuildDirectory -BuildRoot $paths.buildRoot
    $cmakeArgs = @(
        "-S", $paths.coreRoot,
        "-B", $paths.buildRoot,
        "-A", $manifest.build.generator_arch,
        "-DBUILD_SHARED_LIBS=" + ($(if ($manifest.build.build_shared_libs) { "ON" } else { "OFF" })),
        "-DBoost_ROOT=$boostRoot",
        "-DMYSQL_ROOT_DIR=$mysqlRoot"
    )

    $mysqlLib = Get-MySQLLibraryCandidate -Root $mysqlRoot -WorkspaceRoot $paths.root
    if ($mysqlLib) {
        $cmakeArgs += "-DMYSQL_LIBRARY=$mysqlLib"
    }

    $openSslLayout = Get-OpenSSLLayout -Root $openSslRoot
    if (-not $openSslLayout) {
        throw "OpenSSL root '$openSslRoot' does not expose the expected include/lib layout."
    }

    $cmakeArgs += @(
        "-DOPENSSL_ROOT_DIR=$($openSslLayout.Root)",
        "-DOPENSSL_INCLUDE_DIR=$($openSslLayout.IncludeDir)",
        "-DOPENSSL_CRYPTO_LIBRARY=$($openSslLayout.ReleaseCrypto)",
        "-DOPENSSL_SSL_LIBRARY=$($openSslLayout.ReleaseSsl)"
    )

    Invoke-Native -FilePath $cmake -Arguments $cmakeArgs
}

Invoke-Step "Trimming worldserver resource include paths for the generated project" {
    $patched = Repair-WorldserverResourceProject -BuildRoot $paths.buildRoot -SourceRoot $paths.coreRoot
    if (-not $patched) {
        throw "worldserver.vcxproj was not found under $($paths.buildRoot)"
    }
}

Invoke-Step "Building AzerothCore ($($manifest.build.configuration))" {
    Invoke-Native -FilePath $msbuild -Arguments @(
        (Join-Path $paths.buildRoot "AzerothCore.sln"),
        "/m:1",
        "/p:Configuration=$($manifest.build.configuration)"
    )
}

Invoke-Step "Staging runtime DLLs into the build output" {
    Stage-RuntimeDependencies -BinRoot $buildBinRoot -MySQLRoot $mysqlRoot -OpenSSLRoot $openSslRoot
}

Invoke-Step "Copying build output into the portable run layout" {
    Copy-BuildOutputToRun -BuildBinRoot $buildBinRoot -RunRoot $paths.runRoot
}

Invoke-Step "Recording build state into $($paths.stateRoot)" {
    Save-JsonFile -Path (Join-Path $paths.stateRoot "build-summary.json") -Value ([pscustomobject]@{
        workspace_root = $paths.root
        build_root = $paths.buildRoot
        run_root = $paths.runRoot
        run_bin_root = Join-Path $paths.runRoot "bin"
        configuration = $manifest.build.configuration
        cmake = $cmake
        msbuild = $msbuild
        what_if = [bool]$WhatIf
    })
}

Write-Host "build_ready=true workspace=$($paths.root) build=$($paths.buildRoot) run=$($paths.runRoot)"
Write-Host "next_step=edit run\\configs\\worldserver.conf and run\\configs\\authserver.conf before starting the realm"
