Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Resolve-PortablePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$CandidatePath
    )

    if ([System.IO.Path]::IsPathRooted($CandidatePath)) {
        return $CandidatePath
    }

    return (Join-Path $BasePath $CandidatePath)
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Get-BootstrapManifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath
    )

    $repoRoot = Get-RepoRoot
    $resolvedPath = Resolve-PortablePath -BasePath $repoRoot -CandidatePath $ManifestPath
    if (-not (Test-Path $resolvedPath)) {
        throw "Bootstrap manifest not found: $resolvedPath"
    }

    return [pscustomobject]@{
        path = $resolvedPath
        root = $repoRoot
        data = Get-Content -Path $resolvedPath -Raw | ConvertFrom-Json
    }
}

function Get-WorkspacePaths {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        $Manifest,
        [string]$WorkspaceRoot
    )

    $workspaceValue = if ($WorkspaceRoot) { $WorkspaceRoot } else { $Manifest.workspace.root }
    $workspaceResolved = Resolve-PortablePath -BasePath $RepoRoot -CandidatePath $workspaceValue

    return [pscustomobject]@{
        root = $workspaceResolved
        srcRoot = Join-Path $workspaceResolved "src"
        coreRoot = Join-Path $workspaceResolved "src\azerothcore"
        moduleRoot = Join-Path $workspaceResolved "src\modules"
        depsRoot = Join-Path $workspaceResolved "deps"
        downloadsRoot = Join-Path $workspaceResolved "downloads"
        buildRoot = Join-Path $workspaceResolved "build"
        runRoot = Join-Path $workspaceResolved "run"
        runBinRoot = Join-Path $workspaceResolved "run\bin"
        runConfigRoot = Join-Path $workspaceResolved "run\configs"
        runLogRoot = Join-Path $workspaceResolved "run\logs"
        stateRoot = Join-Path $workspaceResolved "state"
        logsRoot = Join-Path $workspaceResolved "logs"
    }
}

function Get-GitPath {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        throw "git was not found on PATH."
    }
    return $git.Source
}

function Clone-Or-UpdateGitRepo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$GitPath,
        [Parameter(Mandatory = $true)]
        [string]$RepoUrl,
        [Parameter(Mandatory = $true)]
        [string]$TargetDir,
        [string]$Branch,
        [string]$Commit
    )

    $gitDir = Join-Path $TargetDir ".git"
    if ((Test-Path $TargetDir) -and -not (Test-Path $gitDir)) {
        Remove-Item -LiteralPath $TargetDir -Recurse -Force
    }

    if (-not (Test-Path $TargetDir)) {
        Ensure-Directory -Path (Split-Path -Parent $TargetDir)
        if ($Commit) {
            Ensure-Directory -Path $TargetDir
            Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "init")
            Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "remote", "add", "origin", $RepoUrl)
            Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "fetch", "--depth", "1", "origin", $Commit)
            Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "checkout", "FETCH_HEAD")
            return
        }

        if ($Branch) {
            Invoke-Native -FilePath $GitPath -Arguments @("clone", "--depth", "1", "--branch", $Branch, $RepoUrl, $TargetDir)
        }
        else {
            Invoke-Native -FilePath $GitPath -Arguments @("clone", "--depth", "1", $RepoUrl, $TargetDir)
        }
        return
    }

    $remoteUrl = (& $GitPath -C $TargetDir remote get-url origin 2>$null).Trim()
    if (-not $remoteUrl) {
        throw "Existing repo at $TargetDir is missing an origin remote."
    }
    if ($remoteUrl -ne $RepoUrl) {
        throw "Existing repo at $TargetDir points to $remoteUrl instead of $RepoUrl."
    }

    if ($Commit) {
        Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "fetch", "--depth", "1", "origin", $Commit)
        Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "checkout", $Commit)
        return
    }

    if ($Branch) {
        Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "fetch", "--depth", "1", "origin", $Branch)
        Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "checkout", $Branch)
        Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "reset", "--hard", "origin/$Branch")
        return
    }

    Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "fetch", "--depth", "1", "origin")
    Invoke-Native -FilePath $GitPath -Arguments @("-C", $TargetDir, "checkout", "FETCH_HEAD")
}

function Sync-LocalModule {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        $Module,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,
        [string]$TargetDirOverride,
        [string]$StateKeySuffix = "workspace"
    )

    $sourceDir = Resolve-PortablePath -BasePath $RepoRoot -CandidatePath $Module.source
    $targetDir = if ($TargetDirOverride) {
        $TargetDirOverride
    }
    else {
        Resolve-PortablePath -BasePath $WorkspaceRoot -CandidatePath $Module.target_path
    }
    if (-not (Test-Path $sourceDir)) {
        throw "Local module source not found: $sourceDir"
    }

    Ensure-Directory -Path (Split-Path -Parent $targetDir)
    Ensure-Directory -Path $targetDir

    $manifestPath = $null
    $stateDir = Join-Path $WorkspaceRoot "state\local-module-sync"
    try {
        Ensure-Directory -Path $stateDir
        $manifestPath = Join-Path $stateDir "$($Module.key).$StateKeySuffix.json"
    }
    catch {
        Write-Host "local_module_sync_state_warning=true module=$($Module.key) message=$($_.Exception.Message)"
    }
    $previousPaths = @()
    if ($manifestPath -and (Test-Path $manifestPath)) {
        $manifest = Get-Content -Path $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.paths) {
            $previousPaths = @($manifest.paths)
        }
    }

    $currentPaths = New-Object System.Collections.Generic.List[string]
    foreach ($directory in Get-ChildItem -LiteralPath $sourceDir -Recurse -Directory | Sort-Object FullName) {
        $relativePath = $directory.FullName.Substring($sourceDir.Length).TrimStart('\', '/')
        if (-not $relativePath) {
            continue
        }
        $currentPaths.Add($relativePath)
        Ensure-Directory -Path (Join-Path $targetDir $relativePath)
    }

    foreach ($file in Get-ChildItem -LiteralPath $sourceDir -Recurse -File | Sort-Object FullName) {
        $relativePath = $file.FullName.Substring($sourceDir.Length).TrimStart('\', '/')
        $currentPaths.Add($relativePath)
        $destination = Join-Path $targetDir $relativePath
        Ensure-Directory -Path (Split-Path -Parent $destination)
        try {
            Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
        }
        catch {
            if (Test-Path $destination) {
                Write-Host "local_module_copy_warning=true module=$($Module.key) path=$relativePath message=$($_.Exception.Message)"
                continue
            }
            throw
        }
    }

    $currentSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($path in $currentPaths) {
        $currentSet.Add([string]$path) | Out-Null
    }

    $staleFiles = @()
    $staleDirectories = @()
    foreach ($previousPath in $previousPaths) {
        if (-not $currentSet.Contains([string]$previousPath)) {
            $fullPath = Join-Path $targetDir $previousPath
            if (-not (Test-Path $fullPath)) {
                continue
            }
            $item = Get-Item -LiteralPath $fullPath -Force
            if ($item.PSIsContainer) {
                $staleDirectories += $fullPath
            }
            else {
                $staleFiles += $fullPath
            }
        }
    }

    foreach ($staleFile in $staleFiles | Sort-Object) {
        Remove-Item -LiteralPath $staleFile -Force
    }
    foreach ($staleDirectory in $staleDirectories | Sort-Object Length -Descending) {
        Remove-Item -LiteralPath $staleDirectory -Recurse -Force
    }

    if ($manifestPath) {
        Save-JsonFile -Path $manifestPath -Value ([pscustomobject]@{
            paths = @($currentPaths | Sort-Object -Unique)
        })
    }

    return $targetDir
}

function Sync-LocalModules {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)]
        [string]$CoreRoot,
        [Parameter(Mandatory = $true)]
        $Manifest
    )

    Ensure-Directory -Path (Join-Path $CoreRoot "modules")
    foreach ($module in @($Manifest.local_modules)) {
        $junctionPath = Join-Path (Join-Path $CoreRoot "modules") $module.key
        $targetDir = Sync-LocalModule -RepoRoot $RepoRoot -Module $module -WorkspaceRoot $WorkspaceRoot
        Ensure-DirectoryJunction -Path $junctionPath -Target $targetDir
    }
}

function Link-LocalModulesDirectly {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$CoreRoot,
        [Parameter(Mandatory = $true)]
        $Manifest
    )

    Ensure-Directory -Path (Join-Path $CoreRoot "modules")
    foreach ($module in @($Manifest.local_modules)) {
        $sourceDir = Resolve-PortablePath -BasePath $RepoRoot -CandidatePath $module.source
        if (-not (Test-Path $sourceDir)) {
            throw "Local module source not found for direct link: $sourceDir"
        }
        $junctionPath = Join-Path (Join-Path $CoreRoot "modules") $module.key
        Ensure-DirectoryJunction -Path $junctionPath -Target $sourceDir
    }
}

function Sync-LocalModulesIntoCore {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)]
        [string]$CoreRoot,
        [Parameter(Mandatory = $true)]
        $Manifest
    )

    Ensure-Directory -Path (Join-Path $CoreRoot "modules")
    foreach ($module in @($Manifest.local_modules)) {
        $targetDir = Join-Path (Join-Path $CoreRoot "modules") $module.key
        Sync-LocalModule `
            -RepoRoot $RepoRoot `
            -Module $module `
            -WorkspaceRoot $WorkspaceRoot `
            -TargetDirOverride $targetDir `
            -StateKeySuffix "core" | Out-Null
    }
}

function Disable-IppOptionalSql {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ModuleRoot
    )

    if (-not (Test-Path $ModuleRoot)) {
        return 0
    }

    $worldSqlRoot = Join-Path $ModuleRoot "data\sql\world"
    if (-not (Test-Path $worldSqlRoot)) {
        return 0
    }

    $disabledRoot = Join-Path $ModuleRoot "_wm_disabled_optional_sql"
    Ensure-Directory -Path $disabledRoot

    $moved = 0
    foreach ($file in Get-ChildItem -Path $worldSqlRoot -Recurse -File -Filter "zz_optional_*.sql" -ErrorAction SilentlyContinue) {
        $destination = Join-Path $disabledRoot $file.Name
        if (Test-Path $destination) {
            Remove-Item -LiteralPath $destination -Force
        }
        Move-Item -LiteralPath $file.FullName -Destination $destination
        $moved += 1
    }

    return $moved
}

function Ensure-DirectoryJunction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Target
    )

    Ensure-Directory -Path (Split-Path -Parent $Path)
    $resolvedTarget = (Resolve-Path $Target).Path

    $existingItem = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($existingItem) {
        if ($existingItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            $resolvedExisting = (Resolve-Path $Path).Path
            if ($resolvedExisting -eq $resolvedTarget) {
                return
            }
        }
        Remove-Item -LiteralPath $Path -Recurse -Force
    }

    try {
        New-Item -ItemType Junction -Path $Path -Target $resolvedTarget | Out-Null
    }
    catch {
        $mklinkOutput = & cmd.exe /c "mklink /J `"$Path`" `"$resolvedTarget`""
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Path)) {
            throw
        }
        $null = $mklinkOutput
    }
}

function Copy-RepoAsset {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        $Asset,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot
    )

    $sourcePath = Resolve-PortablePath -BasePath $RepoRoot -CandidatePath $Asset.source
    $targetPath = Resolve-PortablePath -BasePath $WorkspaceRoot -CandidatePath $Asset.target

    if (-not (Test-Path $sourcePath)) {
        throw "Repo asset not found: $sourcePath"
    }

    Ensure-Directory -Path (Split-Path -Parent $targetPath)
    if ($Asset.kind -eq "directory") {
        if (Test-Path $targetPath) {
            Remove-Item -LiteralPath $targetPath -Recurse -Force
        }
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Recurse -Force
        return
    }

    Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
}

function Save-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        $Value
    )

    Ensure-Directory -Path (Split-Path -Parent $Path)
    $Value | ConvertTo-Json -Depth 10 | Set-Content -Path $Path -Encoding UTF8
}

function Ensure-DownloadedFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [Parameter(Mandatory = $true)]
        [string]$DownloadPath
    )

    Ensure-Directory -Path (Split-Path -Parent $DownloadPath)
    if (Test-Path $DownloadPath) {
        return $DownloadPath
    }

    Invoke-WebRequest -Uri $Url -OutFile $DownloadPath
    return $DownloadPath
}

function Install-Dependency {
    param(
        [Parameter(Mandatory = $true)]
        $Dependency,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)]
        [string]$DownloadsRoot
    )

    $installRoot = Resolve-PortablePath -BasePath $WorkspaceRoot -CandidatePath $Dependency.target_path
    $markerPath = Join-Path $installRoot $Dependency.required_marker
    if (Test-Path $markerPath) {
        return [pscustomobject]@{
            key = $Dependency.key
            install_root = $installRoot
            status = "ready"
        }
    }

    $downloadPath = Join-Path $DownloadsRoot $Dependency.filename
    Ensure-DownloadedFile -Url $Dependency.url -DownloadPath $downloadPath | Out-Null

    if ($Dependency.type -eq "archive") {
        $extractRoot = Join-Path $DownloadsRoot "$($Dependency.key)-extract"
        if (Test-Path $extractRoot) {
            Remove-Item -LiteralPath $extractRoot -Recurse -Force
        }
        Ensure-Directory -Path $extractRoot
        Expand-Archive -Path $downloadPath -DestinationPath $extractRoot -Force

        $sourceDir = $extractRoot
        if ($Dependency.extracted_subdir) {
            $sourceDir = Join-Path $extractRoot $Dependency.extracted_subdir
        }
        if (-not (Test-Path $sourceDir)) {
            throw "Dependency extract path not found: $sourceDir"
        }

        if (Test-Path $installRoot) {
            Remove-Item -LiteralPath $installRoot -Recurse -Force
        }
        Ensure-Directory -Path (Split-Path -Parent $installRoot)
        Move-Item -LiteralPath $sourceDir -Destination $installRoot
    }
    elseif ($Dependency.type -eq "installer") {
        if (Test-Path $installRoot) {
            Remove-Item -LiteralPath $installRoot -Recurse -Force
        }
        Ensure-Directory -Path (Split-Path -Parent $installRoot)
        $argumentList = @()
        foreach ($argument in $Dependency.silent_args) {
            $argumentList += ($argument -replace "\{InstallDir\}", $installRoot)
        }
        $process = Start-Process -FilePath $downloadPath -ArgumentList $argumentList -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Installer for dependency '$($Dependency.key)' failed with exit code $($process.ExitCode)."
        }
    }
    else {
        throw "Unsupported dependency type '$($Dependency.type)' for '$($Dependency.key)'."
    }

    if (-not (Test-Path $markerPath)) {
        throw "Dependency '$($Dependency.key)' did not produce the expected marker at $markerPath"
    }

    return [pscustomobject]@{
        key = $Dependency.key
        install_root = $installRoot
        status = "installed"
    }
}

function Get-MsvcToolPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ToolName
    )

    $toolRoots = @(
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools",
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools",
        "C:\Program Files\Microsoft Visual Studio\2022\Community",
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\Community",
        "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools"
    )

    foreach ($root in $toolRoots) {
        if (-not (Test-Path $root)) {
            continue
        }
        $candidate = Get-ChildItem -Path $root -Recurse -Filter $ToolName -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }

    return $null
}

function Get-CMakePath {
    $cmake = Get-Command cmake -ErrorAction SilentlyContinue
    if ($cmake) {
        return $cmake.Source
    }

    $candidate = Get-MsvcToolPath -ToolName "cmake.exe"
    if ($candidate) {
        return $candidate
    }

    throw "cmake.exe was not found on PATH or in a Visual Studio installation."
}

function Get-MSBuildPath {
    $msbuild = Get-Command msbuild -ErrorAction SilentlyContinue
    if ($msbuild) {
        return $msbuild.Source
    }

    $candidate = Get-MsvcToolPath -ToolName "MSBuild.exe"
    if ($candidate) {
        return $candidate
    }

    throw "MSBuild.exe was not found on PATH or in a Visual Studio installation."
}

function Get-DependencyInstallRoot {
    param(
        [Parameter(Mandatory = $true)]
        $Manifest,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    foreach ($dependency in $Manifest.dependencies) {
        if ($dependency.key -eq $Key) {
            return Resolve-PortablePath -BasePath $WorkspaceRoot -CandidatePath $dependency.target_path
        }
    }
    throw "Dependency '$Key' was not found in the manifest."
}

function Get-LocalModuleBuildFingerprint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        $Manifest
    )

    $records = New-Object System.Collections.Generic.List[string]
    $fileCount = 0
    foreach ($module in @($Manifest.local_modules)) {
        $sourceDir = Resolve-PortablePath -BasePath $RepoRoot -CandidatePath $module.source
        if (-not (Test-Path $sourceDir)) {
            throw "Local module source not found while computing build fingerprint: $sourceDir"
        }

        $records.Add("module|$($module.key)|$($module.source)|$($module.target_path)")
        $files = Get-ChildItem -LiteralPath $sourceDir -Recurse -File | Sort-Object FullName
        foreach ($file in $files) {
            $relativePath = $file.FullName.Substring($sourceDir.Length).TrimStart('\', '/')
            $records.Add("file|$($module.key)|$relativePath|$($file.Length)|$($file.LastWriteTimeUtc.Ticks)")
            $fileCount += 1
        }
    }

    $payload = [string]::Join("`n", $records)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($payload))
    }
    finally {
        $sha.Dispose()
    }

    return [pscustomobject]@{
        hash = ([System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLowerInvariant())
        module_count = @($Manifest.local_modules).Count
        file_count = $fileCount
    }
}

function Get-CMakeConfigureStatePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildRoot
    )

    return (Join-Path $BuildRoot "wm-cmake-configure-state.json")
}

function Save-CMakeConfigureState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildRoot,
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        $Manifest,
        [Parameter(Mandatory = $true)]
        [string]$CoreRoot
    )

    $fingerprint = Get-LocalModuleBuildFingerprint -RepoRoot $RepoRoot -Manifest $Manifest
    Save-JsonFile -Path (Get-CMakeConfigureStatePath -BuildRoot $BuildRoot) -Value ([pscustomobject]@{
        local_module_hash = $fingerprint.hash
        local_module_count = $fingerprint.module_count
        local_module_file_count = $fingerprint.file_count
        core_root = $CoreRoot
        generator_arch = $Manifest.build.generator_arch
        build_shared_libs = [bool]$Manifest.build.build_shared_libs
    })
    return $fingerprint
}

function Test-CMakeReconfigureRequired {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildRoot,
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        $Manifest,
        [Parameter(Mandatory = $true)]
        [string]$CoreRoot
    )

    $solutionPath = Join-Path $BuildRoot "AzerothCore.sln"
    $statePath = Get-CMakeConfigureStatePath -BuildRoot $BuildRoot
    $fingerprint = Get-LocalModuleBuildFingerprint -RepoRoot $RepoRoot -Manifest $Manifest

    if (-not (Test-Path $solutionPath)) {
        return [pscustomobject]@{
            required = $true
            reason = "solution_missing"
            fingerprint = $fingerprint
        }
    }

    if (-not (Test-Path $statePath)) {
        return [pscustomobject]@{
            required = $true
            reason = "configure_state_missing"
            fingerprint = $fingerprint
        }
    }

    $state = Get-Content -Path $statePath -Raw | ConvertFrom-Json
    if ($state.local_module_hash -ne $fingerprint.hash) {
        return [pscustomobject]@{
            required = $true
            reason = "local_module_hash_changed"
            fingerprint = $fingerprint
        }
    }

    if ([string]$state.core_root -ne [string]$CoreRoot) {
        return [pscustomobject]@{
            required = $true
            reason = "core_root_changed"
            fingerprint = $fingerprint
        }
    }

    if ([string]$state.generator_arch -ne [string]$Manifest.build.generator_arch) {
        return [pscustomobject]@{
            required = $true
            reason = "generator_arch_changed"
            fingerprint = $fingerprint
        }
    }

    if ([bool]$state.build_shared_libs -ne [bool]$Manifest.build.build_shared_libs) {
        return [pscustomobject]@{
            required = $true
            reason = "build_shared_libs_changed"
            fingerprint = $fingerprint
        }
    }

    return [pscustomobject]@{
        required = $false
        reason = "up_to_date"
        fingerprint = $fingerprint
    }
}

function Invoke-WorkspaceCMakeConfigure {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CMakePath,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)]
        $Manifest,
        [Parameter(Mandatory = $true)]
        [string]$CoreRoot,
        [Parameter(Mandatory = $true)]
        [string]$BuildRoot
    )

    $boostRoot = Get-DependencyInstallRoot -Manifest $Manifest -WorkspaceRoot $WorkspaceRoot -Key "boost"
    $mysqlRoot = Get-DependencyInstallRoot -Manifest $Manifest -WorkspaceRoot $WorkspaceRoot -Key "mysql"
    $openSslRoot = Get-DependencyInstallRoot -Manifest $Manifest -WorkspaceRoot $WorkspaceRoot -Key "openssl"
    $cmakeArgs = @(
        "-S", $CoreRoot,
        "-B", $BuildRoot,
        "-A", $Manifest.build.generator_arch,
        "-DBUILD_SHARED_LIBS=" + ($(if ($Manifest.build.build_shared_libs) { "ON" } else { "OFF" })),
        "-DBoost_ROOT=$boostRoot",
        "-DMYSQL_ROOT_DIR=$mysqlRoot"
    )

    $mysqlLib = Get-MySQLLibraryCandidate -Root $mysqlRoot -WorkspaceRoot $WorkspaceRoot
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

    Invoke-Native -FilePath $CMakePath -Arguments $cmakeArgs
}

function Get-OpenSSLLayout {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $includeDir = Join-Path $Root "include"
    if (-not (Test-Path (Join-Path $includeDir "openssl\opensslv.h"))) {
        return $null
    }

    $releaseCryptoCandidates = @(
        (Join-Path $Root "lib\VC\x64\MD\libcrypto.lib"),
        (Join-Path $Root "lib\VC\libcrypto64MD.lib"),
        (Join-Path $Root "lib\libcrypto.lib")
    )
    $releaseSslCandidates = @(
        (Join-Path $Root "lib\VC\x64\MD\libssl.lib"),
        (Join-Path $Root "lib\VC\libssl64MD.lib"),
        (Join-Path $Root "lib\libssl.lib")
    )

    $releaseCrypto = $releaseCryptoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    $releaseSsl = $releaseSslCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $releaseCrypto -or -not $releaseSsl) {
        return $null
    }

    return [pscustomobject]@{
        Root = $Root
        IncludeDir = $includeDir
        ReleaseCrypto = $releaseCrypto
        ReleaseSsl = $releaseSsl
    }
}

function Get-MySQLRuntimeDllCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    foreach ($candidate in @(
        (Join-Path $Root "lib\libmysql.dll"),
        (Join-Path $Root "bin\libmysql.dll")
    )) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Get-OpenSSLRuntimeDllCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    foreach ($candidate in @(
        (Join-Path $Root "bin\$Name"),
        (Join-Path $Root $Name)
    )) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Get-MySQLLibraryCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot
    )

    foreach ($candidate in @(
        (Join-Path $Root "lib\libmysql.lib"),
        (Join-Path $Root "lib\opt\libmysql.lib")
    )) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $runtimeDll = Get-MySQLRuntimeDllCandidate -Root $Root
    if (-not $runtimeDll) {
        return $null
    }

    $dumpbin = Get-MsvcToolPath -ToolName "dumpbin.exe"
    $libexe = Get-MsvcToolPath -ToolName "lib.exe"
    if (-not $dumpbin -or -not $libexe) {
        return $null
    }

    $sdkRoot = Join-Path $WorkspaceRoot "state\mysql-sdk"
    Ensure-Directory -Path $sdkRoot
    $defPath = Join-Path $sdkRoot "libmysql.def"
    $libPath = Join-Path $sdkRoot "libmysql.lib"

    $dumpOutput = & $dumpbin /exports $runtimeDll
    if ($LASTEXITCODE -ne 0) {
        throw "dumpbin failed while extracting exports from $runtimeDll"
    }

    $exportNames = @()
    foreach ($line in $dumpOutput) {
        if ($line -match '^\s+\d+\s+[0-9A-F]+\s+[0-9A-F]+\s+([A-Za-z0-9_@?]+)$') {
            $exportNames += $matches[1]
        }
    }
    if ($exportNames.Count -eq 0) {
        throw "No exports were parsed from $runtimeDll"
    }

    $defContent = @(
        "LIBRARY libmysql.dll",
        "EXPORTS"
    ) + ($exportNames | Sort-Object -Unique | ForEach-Object { "    $_" })
    Set-Content -Path $defPath -Value $defContent -Encoding ASCII

    & $libexe /def:$defPath /machine:x64 /out:$libPath | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $libPath)) {
        throw "lib.exe failed while generating import library at $libPath"
    }

    return $libPath
}

function Reset-BuildDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildRoot
    )

    Ensure-Directory -Path $BuildRoot
    foreach ($child in Get-ChildItem -Path $BuildRoot -Force -ErrorAction SilentlyContinue) {
        Remove-Item -LiteralPath $child.FullName -Recurse -Force
    }
}

function Stage-RuntimeDependencies {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BinRoot,
        [string]$MySQLRoot,
        [string]$OpenSSLRoot
    )

    $copies = @()
    if ($MySQLRoot) {
        $mysqlRuntimeDll = Get-MySQLRuntimeDllCandidate -Root $MySQLRoot
        if ($mysqlRuntimeDll) {
            $copies += $mysqlRuntimeDll
        }
    }

    if ($OpenSSLRoot) {
        foreach ($name in @("libcrypto-3-x64.dll", "libssl-3-x64.dll", "legacy.dll")) {
            $candidate = Get-OpenSSLRuntimeDllCandidate -Root $OpenSSLRoot -Name $name
            if ($candidate) {
                $copies += $candidate
            }
        }
    }

    Ensure-Directory -Path $BinRoot
    foreach ($sourcePath in $copies | Sort-Object -Unique) {
        Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $BinRoot ([System.IO.Path]::GetFileName($sourcePath))) -Force
    }
}

function Get-RuntimeDllInventory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BinRoot
    )

    $requiredNames = @("libmysql.dll", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "legacy.dll")
    $files = @()
    foreach ($name in $requiredNames) {
        $path = Join-Path $BinRoot $name
        if (-not (Test-Path $path)) {
            throw "Required runtime DLL is missing: $path"
        }
        $item = Get-Item -LiteralPath $path
        $versionInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($item.FullName)
        $files += [pscustomobject]@{
            name = $name
            path = $item.FullName
            length = $item.Length
            sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            file_version = $versionInfo.FileVersion
            product_version = $versionInfo.ProductVersion
        }
    }
    return $files
}

function Write-RuntimeDllLock {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BinRoot,
        [Parameter(Mandatory = $true)]
        [string]$StateRoot
    )

    Ensure-Directory -Path $StateRoot
    $lockPath = Join-Path $StateRoot "runtime-dlls.lock.json"
    $payload = [pscustomobject]@{
        schema_version = "wm.runtime_dlls.v1"
        bin_root = (Resolve-Path $BinRoot).Path
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        files = @(Get-RuntimeDllInventory -BinRoot $BinRoot)
    }
    Save-JsonFile -Path $lockPath -Value $payload
    return $lockPath
}

function Test-RuntimeDllLock {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BinRoot,
        [Parameter(Mandatory = $true)]
        [string]$LockPath
    )

    if (-not (Test-Path $LockPath)) {
        throw "Runtime DLL lock is missing: $LockPath. Re-run build-wm.bat to restage dependencies."
    }

    $lock = Get-Content -Path $LockPath -Raw | ConvertFrom-Json
    $actualByName = @{}
    foreach ($entry in @(Get-RuntimeDllInventory -BinRoot $BinRoot)) {
        $actualByName[$entry.name] = $entry
    }

    foreach ($expected in @($lock.files)) {
        $actual = $actualByName[$expected.name]
        if (-not $actual) {
            throw "Runtime DLL is missing from inventory: $($expected.name)"
        }
        if ($actual.sha256 -ne $expected.sha256 -or [int64]$actual.length -ne [int64]$expected.length) {
            throw "Runtime DLL mismatch for $($expected.name). Re-run build-wm.bat before starting the rebuilt server."
        }
    }
    return $true
}

function Repair-WorldserverResourceProject {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildRoot,
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot
    )

    $projectPath = Join-Path $BuildRoot "src\server\apps\worldserver.vcxproj"
    if (-not (Test-Path $projectPath)) {
        return $false
    }

    [xml]$projectXml = Get-Content -LiteralPath $projectPath
    $namespaceManager = New-Object System.Xml.XmlNamespaceManager($projectXml.NameTable)
    $namespaceManager.AddNamespace("msb", "http://schemas.microsoft.com/developer/msbuild/2003")

    $minimalIncludeDirectories = @(
        (Join-Path $SourceRoot "src\server\apps"),
        (Join-Path $SourceRoot "src\server\apps\worldserver"),
        $BuildRoot
    ) -join ";"

    $nodes = $projectXml.SelectNodes("//msb:ItemDefinitionGroup/msb:ResourceCompile/msb:AdditionalIncludeDirectories", $namespaceManager)
    foreach ($node in $nodes) {
        $node.InnerText = "$minimalIncludeDirectories;%(AdditionalIncludeDirectories)"
    }

    $projectXml.Save($projectPath)
    return $true
}

function Stage-RepoSqlOverrides {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot,
        [Parameter(Mandatory = $true)]
        $Manifest
    )

    foreach ($mapping in $Manifest.sql_overrides) {
        $sourceDir = Resolve-PortablePath -BasePath $RepoRoot -CandidatePath $mapping.source
        if (-not (Test-Path $sourceDir)) {
            continue
        }

        $targetDir = Join-Path $SourceRoot $mapping.target
        Ensure-Directory -Path $targetDir
        foreach ($file in Get-ChildItem -Path $sourceDir -File -Filter "*.sql") {
            Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $targetDir $file.Name) -Force
        }
    }
}

function Copy-BuildOutputToRun {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildBinRoot,
        [Parameter(Mandatory = $true)]
        [string]$RunRoot
    )

    $runBinRoot = Join-Path $RunRoot "bin"
    $runConfigRoot = Join-Path $RunRoot "configs"
    Ensure-Directory -Path $runBinRoot
    Ensure-Directory -Path $runConfigRoot
    Ensure-Directory -Path (Join-Path $runConfigRoot "modules")
    Ensure-Directory -Path (Join-Path $RunRoot "logs")

    foreach ($item in Get-ChildItem -Path $BuildBinRoot -Force) {
        if ($item.PSIsContainer -and $item.Name -ieq "configs") {
            continue
        }
        $destination = Join-Path $runBinRoot $item.Name
        if ($item.PSIsContainer) {
            if (Test-Path $destination) {
                Remove-Item -LiteralPath $destination -Recurse -Force
            }
            Copy-Item -LiteralPath $item.FullName -Destination $destination -Recurse -Force
        }
        else {
            Copy-Item -LiteralPath $item.FullName -Destination $destination -Force
        }
    }

    $buildConfigRoot = Join-Path $BuildBinRoot "configs"
    if (Test-Path $buildConfigRoot) {
        Copy-Item -Path (Join-Path $buildConfigRoot "*") -Destination $runConfigRoot -Recurse -Force
    }

    foreach ($distPath in Get-ChildItem -Path $runConfigRoot -Recurse -Filter "*.conf.dist" -File -ErrorAction SilentlyContinue) {
        $targetPath = $distPath.FullName.Substring(0, $distPath.FullName.Length - 5)
        if (-not (Test-Path $targetPath)) {
            Copy-Item -LiteralPath $distPath.FullName -Destination $targetPath -Force
        }
    }
}
