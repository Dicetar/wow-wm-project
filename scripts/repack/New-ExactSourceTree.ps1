param(
    [string]$ManifestPath = "data/repack/live-repack-manifest.json",
    [string]$WorkspaceRoot = "D:\WOW\Azerothcore_WoTLK_Rebuild",
    [string]$BuildAliasRoot = "D:\WOW\ACRB",
    [switch]$Build,
    [switch]$BuildOnly,
    [switch]$PinLiveCore,
    [switch]$CloneCandidates,
    [string]$ResolutionPath = "data/repack/module-repo-resolution.json",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$script:CheckpointNote = $null

function Invoke-Step {
    param(
        [string]$Message,
        [scriptblock]$Action
    )

    Write-Host $Message
    if (-not $WhatIf) {
        & $Action
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

function Get-BoostRootCandidate {
    $envCandidates = @(
        $env:Boost_ROOT,
        $env:BOOST_ROOT,
        $env:BOOSTROOT
    ) | Where-Object { $_ }
    foreach ($candidate in $envCandidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $localRoot = "C:\local"
    $searchRoots = @()
    if (Test-Path $localRoot) {
        $searchRoots += $localRoot
    }

    $workspaceLocalRoot = Join-Path $WorkspaceRoot "local"
    if (Test-Path $workspaceLocalRoot) {
        $searchRoots += $workspaceLocalRoot
    }

    foreach ($root in $searchRoots) {
        $dirs = Get-ChildItem -Path $root -Directory -Filter "boost_*" |
            Sort-Object Name -Descending
        if ($dirs.Count -gt 0) {
            return $dirs[0].FullName
        }
    }

    return $null
}

function Get-OpenSSLRootCandidate {
    $envCandidates = @(
        $env:OPENSSL_ROOT_DIR,
        $env:OpenSSL_ROOT_DIR
    ) | Where-Object { $_ }
    foreach ($candidate in $envCandidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $searchRoots = @()
    $workspaceLocalRoot = Join-Path $WorkspaceRoot "local"
    if (Test-Path $workspaceLocalRoot) {
        $searchRoots += $workspaceLocalRoot
    }
    $searchRoots += @("D:\OpenSSL-Win64", "C:\OpenSSL-Win64", "C:\OpenSSL")

    foreach ($root in $searchRoots) {
        if (-not (Test-Path $root)) {
            continue
        }
        if (Test-Path (Join-Path $root "include\openssl\opensslv.h")) {
            return $root
        }
        $dirs = Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "OpenSSL*" } |
            Sort-Object Name -Descending
        foreach ($dir in $dirs) {
            if (Test-Path (Join-Path $dir.FullName "include\openssl\opensslv.h")) {
                return $dir.FullName
            }
        }
    }

    return $null
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
        (Join-Path $Root "lib\VC\libcrypto64MD.lib")
    )
    $releaseSslCandidates = @(
        (Join-Path $Root "lib\VC\x64\MD\libssl.lib"),
        (Join-Path $Root "lib\VC\libssl64MD.lib")
    )
    $debugCryptoCandidates = @(
        (Join-Path $Root "lib\VC\x64\MDd\libcrypto.lib"),
        (Join-Path $Root "lib\VC\libcrypto64MDd.lib")
    )
    $debugSslCandidates = @(
        (Join-Path $Root "lib\VC\x64\MDd\libssl.lib"),
        (Join-Path $Root "lib\VC\libssl64MDd.lib")
    )

    $releaseCrypto = $releaseCryptoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    $releaseSsl = $releaseSslCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    $debugCrypto = $debugCryptoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    $debugSsl = $debugSslCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $releaseCrypto -or -not $releaseSsl) {
        return $null
    }

    return [pscustomobject]@{
        Root = $Root
        IncludeDir = $includeDir
        ReleaseCrypto = $releaseCrypto
        ReleaseSsl = $releaseSsl
        DebugCrypto = $debugCrypto
        DebugSsl = $debugSsl
    }
}

function Reset-CMakeCacheForDependencyResolution {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildRoot
    )

    if (-not (Test-Path $BuildRoot)) {
        New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
        return
    }

    foreach ($child in Get-ChildItem -Path $BuildRoot -Force -ErrorAction SilentlyContinue) {
        Remove-Item -LiteralPath $child.FullName -Recurse -Force
    }
}

function Get-MsvcToolPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ToolName
    )

    $toolRoots = @(
        "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Tools\MSVC",
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
        "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC"
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

function Get-MySQLLibraryCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot
    )

    $directCandidates = @(
        (Join-Path $Root "lib\libmysql.lib"),
        (Join-Path $Root "lib\opt\libmysql.lib")
    )
    foreach ($candidate in $directCandidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $runtimeDll = Join-Path $Root "lib\libmysql.dll"
    if (-not (Test-Path $runtimeDll)) {
        return $null
    }

    $dumpbin = Get-MsvcToolPath -ToolName "dumpbin.exe"
    $libexe = Get-MsvcToolPath -ToolName "lib.exe"
    if (-not $dumpbin -or -not $libexe) {
        return $null
    }

    $sdkRoot = Join-Path $WorkspaceRoot "local\mysql-sdk"
    $defPath = Join-Path $sdkRoot "libmysql.def"
    $libPath = Join-Path $sdkRoot "libmysql.lib"
    New-Item -ItemType Directory -Force -Path $sdkRoot | Out-Null

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
    Set-Content -Path $defPath -Value $defContent

    & $libexe /def:$defPath /machine:x64 /out:$libPath | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $libPath)) {
        throw "lib.exe failed while generating import library at $libPath"
    }

    return $libPath
}

function Get-MySQLRuntimeDllCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $candidates = @(
        (Join-Path $Root "lib\libmysql.dll"),
        (Join-Path $Root "bin\libmysql.dll")
    )
    foreach ($candidate in $candidates) {
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

    $candidates = @(
        (Join-Path $Root "bin\$Name"),
        (Join-Path $Root $Name)
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
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
            $dll = Get-OpenSSLRuntimeDllCandidate -Root $OpenSSLRoot -Name $name
            if ($dll) {
                $copies += $dll
            }
        }
    }

    foreach ($sourcePath in ($copies | Sort-Object -Unique)) {
        Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $BinRoot ([System.IO.Path]::GetFileName($sourcePath))) -Force
    }
}

function Stage-RepoSqlOverrides {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot
    )

    $overrideRoot = Join-Path $RepoRoot "sql\repack"
    if (-not (Test-Path $overrideRoot)) {
        return
    }

    $dbMappings = @{
        "db_auth" = Join-Path $SourceRoot "data\sql\custom\db_auth"
        "db_characters" = Join-Path $SourceRoot "data\sql\custom\db_characters"
        "db_world" = Join-Path $SourceRoot "data\sql\custom\db_world"
    }

    foreach ($key in $dbMappings.Keys) {
        $sourceDir = Join-Path $overrideRoot $key
        if (-not (Test-Path $sourceDir)) {
            continue
        }

        $targetDir = $dbMappings[$key]
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

        foreach ($file in Get-ChildItem -Path $sourceDir -File -Filter "*.sql") {
            Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $targetDir $file.Name) -Force
        }
    }
}

function Ensure-WorkspaceAlias {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ActualWorkspaceRoot,
        [Parameter(Mandatory = $true)]
        [string]$AliasRoot
    )

    if (-not $AliasRoot) {
        return $ActualWorkspaceRoot
    }

    $actualResolved = (Resolve-Path $ActualWorkspaceRoot).Path
    if (Test-Path $AliasRoot) {
        $existingItem = Get-Item -LiteralPath $AliasRoot -Force
        if (-not ($existingItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            throw "Build alias path '$AliasRoot' already exists and is not a junction/symlink."
        }
        $aliasTarget = $null
        if ($existingItem.Target) {
            $aliasTarget = [string]($existingItem.Target | Select-Object -First 1)
        }
        if (-not $aliasTarget) {
            $aliasTarget = (Resolve-Path $AliasRoot).Path
        }
        if ($aliasTarget -ne $actualResolved) {
            throw "Build alias path '$AliasRoot' points to '$aliasTarget' instead of '$actualResolved'."
        }
        return $AliasRoot
    }

    $aliasParent = Split-Path -Parent $AliasRoot
    if ($aliasParent -and -not (Test-Path $aliasParent)) {
        New-Item -ItemType Directory -Force -Path $aliasParent | Out-Null
    }
    New-Item -ItemType Junction -Path $AliasRoot -Target $actualResolved | Out-Null
    return $AliasRoot
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

if (-not [System.IO.Path]::IsPathRooted($ManifestPath)) {
    $ManifestPath = Join-Path $repoRoot $ManifestPath
}
if (-not [System.IO.Path]::IsPathRooted($ResolutionPath)) {
    $ResolutionPath = Join-Path $repoRoot $ResolutionPath
}

if (-not (Test-Path $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}

$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$reachableCandidates = @{}
if ($CloneCandidates -and (Test-Path $ResolutionPath)) {
    $resolutionItems = Get-Content $ResolutionPath -Raw | ConvertFrom-Json
    foreach ($item in $resolutionItems) {
        if ($item.reachable) {
            $reachableCandidates[$item.key] = $true
        }
    }
}
$git = $manifest.build_tooling.git_path
$cmake = $manifest.build_tooling.cmake_path
$msbuild = $manifest.build_tooling.msbuild_path

if (-not $git) { throw "git path was not captured in the manifest." }
if (-not $cmake) { throw "cmake path was not captured in the manifest." }
if (-not $msbuild) { throw "MSBuild path was not captured in the manifest." }

$sourceRoot = Join-Path $WorkspaceRoot "source\azerothcore"
$moduleRoot = Join-Path $sourceRoot "modules"
$buildRoot = Join-Path $WorkspaceRoot "build"
$runRoot = Join-Path $WorkspaceRoot "run"
$runConfigRoot = Join-Path $runRoot "configs"
$statusPath = Join-Path $WorkspaceRoot "clone-status.txt"
$moduleStatusPath = Join-Path $WorkspaceRoot "module-clone-status.json"
$compatibilityOverlayScript = Join-Path $repoRoot "scripts\repack\Apply-RepackCompatibilityOverlay.ps1"

Invoke-Step "Creating workspace roots under $WorkspaceRoot" {
    New-Item -ItemType Directory -Force -Path $WorkspaceRoot,$buildRoot,$runConfigRoot | Out-Null
}

if (-not $BuildOnly) {
    Invoke-Step "Cloning Playerbot core into $sourceRoot" {
        if (-not (Test-Path $sourceRoot)) {
            New-Item -ItemType Directory -Force -Path $sourceRoot | Out-Null
        }
        if (-not (Test-Path (Join-Path $sourceRoot ".git"))) {
            Invoke-Native $git -C $sourceRoot init
            Invoke-Native $git -C $sourceRoot remote add origin $manifest.core.repo_url
        }
        if ($PinLiveCore) {
            & $git -C $sourceRoot fetch --depth 1 origin $manifest.core.commit
            if ($LASTEXITCODE -eq 0) {
                Invoke-Native $git -C $sourceRoot checkout FETCH_HEAD
            }
            else {
                Write-Host "Exact commit fetch failed, falling back to shallow branch fetch for $($manifest.core.branch)"
                Invoke-Native $git -C $sourceRoot fetch --depth 256 origin $manifest.core.branch
                & $git -C $sourceRoot rev-parse --verify $manifest.core.commit
                if ($LASTEXITCODE -eq 0) {
                    Invoke-Native $git -C $sourceRoot checkout $manifest.core.commit
                }
                else {
                    Invoke-Native $git -C $sourceRoot checkout FETCH_HEAD
                    $script:CheckpointNote = "Core checkout fell back to the current shallow $($manifest.core.branch) head because commit $($manifest.core.commit) was not directly available from the remote."
                }
            }
        }
        else {
            Invoke-Native $git -C $sourceRoot fetch --depth 256 origin $manifest.core.branch
            Invoke-Native $git -C $sourceRoot checkout FETCH_HEAD
            $currentHead = (& $git -C $sourceRoot rev-parse --verify HEAD).Trim()
            if ($manifest.core.commit -and $currentHead -and -not $currentHead.StartsWith($manifest.core.commit, [System.StringComparison]::OrdinalIgnoreCase)) {
                $script:CheckpointNote = "Using the latest $($manifest.core.branch) branch head ($currentHead) instead of the live repack commit $($manifest.core.commit) by design."
            }
        }
    }

    Invoke-Step "Ensuring module directory exists" {
        New-Item -ItemType Directory -Force -Path $moduleRoot | Out-Null
    }
}
elseif (-not (Test-Path $sourceRoot)) {
    throw "BuildOnly was requested, but no reconstructed source tree exists at $sourceRoot"
}

function Clone-ModuleEntry {
    param(
        [Parameter(Mandatory = $true)]
        $Module
    )

    $targetDir = Join-Path $moduleRoot $Module.key
    $result = [ordered]@{
        key = $Module.key
        display_name = $Module.display_name
        status = $Module.status
        repo_url = $Module.repo_url
        cloned = $false
        skipped = $false
        reason = $null
    }

    if (-not $Module.repo_url) {
        $result.skipped = $true
        $result.reason = "missing_repo_url"
        return [pscustomobject]$result
    }

    try {
        Invoke-Step "Cloning $($Module.status) module $($Module.display_name) into $targetDir" {
            $gitDir = Join-Path $targetDir ".git"
            if ((Test-Path $targetDir) -and -not (Test-Path $gitDir)) {
                Remove-Item -LiteralPath $targetDir -Recurse -Force
            }

            if (-not (Test-Path $targetDir)) {
                if ($Module.commit) {
                    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
                    Invoke-Native $git -C $targetDir init
                    Invoke-Native $git -C $targetDir remote add origin $Module.repo_url
                    Invoke-Native $git -C $targetDir fetch --depth 1 origin $Module.commit
                    Invoke-Native $git -C $targetDir checkout FETCH_HEAD
                }
                elseif ($Module.branch) {
                    Invoke-Native $git clone --depth 1 --branch $Module.branch $Module.repo_url $targetDir
                }
                else {
                    Invoke-Native $git clone --depth 1 $Module.repo_url $targetDir
                }
            }
            else {
                $remoteUrl = (& $git -C $targetDir remote get-url origin 2>$null).Trim()
                if ($LASTEXITCODE -ne 0 -or -not $remoteUrl) {
                    throw "Existing module directory is missing a usable origin remote."
                }

                if ($remoteUrl -ne $Module.repo_url) {
                    Remove-Item -LiteralPath $targetDir -Recurse -Force
                    if ($Module.branch) {
                        Invoke-Native $git clone --depth 1 --branch $Module.branch $Module.repo_url $targetDir
                    }
                    else {
                        Invoke-Native $git clone --depth 1 $Module.repo_url $targetDir
                    }
                }
                elseif ($Module.commit) {
                    Invoke-Native $git -C $targetDir fetch --depth 1 origin $Module.commit
                    Invoke-Native $git -C $targetDir checkout $Module.commit
                }
                elseif ($Module.branch) {
                    Invoke-Native $git -C $targetDir fetch --depth 1 origin $Module.branch
                    Invoke-Native $git -C $targetDir checkout $Module.branch
                }
                else {
                    Invoke-Native $git -C $targetDir fetch --depth 1 origin
                    Invoke-Native $git -C $targetDir checkout FETCH_HEAD
                }
            }
        }
        $result.cloned = $true
    }
    catch {
        $result.reason = $_.Exception.Message
    }

    return [pscustomobject]$result
}

$moduleCloneResults = @()
$cloneableStatuses = @("verified", "candidate")
$seenRepoUrls = @{}
$desiredModules = @()
foreach ($module in $manifest.modules) {
    if ($cloneableStatuses -notcontains $module.status) {
        continue
    }

    if ($module.status -eq "candidate" -and $reachableCandidates.Count -gt 0 -and -not $reachableCandidates.ContainsKey($module.key)) {
        $moduleCloneResults += [pscustomobject]@{
            key = $module.key
            display_name = $module.display_name
            status = $module.status
            repo_url = $module.repo_url
            cloned = $false
            skipped = $true
            reason = "candidate_not_marked_reachable"
        }
        continue
    }

    $normalizedRepoUrl = if ($module.repo_url) { $module.repo_url.ToLowerInvariant() } else { $null }
    if ($normalizedRepoUrl -and $seenRepoUrls.ContainsKey($normalizedRepoUrl)) {
        $moduleCloneResults += [pscustomobject]@{
            key = $module.key
            display_name = $module.display_name
            status = $module.status
            repo_url = $module.repo_url
            cloned = $false
            skipped = $true
            reason = "duplicate_repo_url_of:$($seenRepoUrls[$normalizedRepoUrl])"
        }
        continue
    }

    if ($normalizedRepoUrl) {
        $seenRepoUrls[$normalizedRepoUrl] = $module.key
    }
    $desiredModules += $module
}

if (-not $BuildOnly) {
    Invoke-Step "Pruning stale module directories under $moduleRoot" {
        $desiredNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($module in $desiredModules) {
            [void]$desiredNames.Add([string]$module.key)
        }
        foreach ($directory in Get-ChildItem -Path $moduleRoot -Directory -ErrorAction SilentlyContinue) {
            if (-not $desiredNames.Contains($directory.Name)) {
                Remove-Item -LiteralPath $directory.FullName -Recurse -Force
            }
        }
    }

    foreach ($module in $desiredModules) {
        $moduleCloneResults += Clone-ModuleEntry -Module $module
    }
}

$candidateCount = @($manifest.modules | Where-Object { $_.status -eq "candidate" }).Count
$unresolvedCount = @($manifest.modules | Where-Object { $_.status -eq "unresolved" }).Count
Write-Host "verified_modules=$(@($manifest.modules | Where-Object { $_.status -eq 'verified' }).Count) candidate_modules=$candidateCount unresolved_modules=$unresolvedCount"

if (-not $BuildOnly) {
    Invoke-Step "Copying current config overlays into $runConfigRoot" {
        foreach ($overlay in $manifest.config_overlays) {
            $sourcePath = Join-Path $manifest.runtime_layout.config_root $overlay.relative_path
            $targetPath = Join-Path $runConfigRoot $overlay.relative_path
            New-Item -ItemType Directory -Force -Path (Split-Path $targetPath) | Out-Null
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
        }
    }

    Invoke-Step "Staging optional SQL files for manual review" {
        foreach ($item in $manifest.optional_sql) {
            $targetDir = Join-Path $sourceRoot $item.target_relative_dir
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            Copy-Item -LiteralPath $item.source_path -Destination (Join-Path $targetDir $item.filename) -Force
        }
    }

    Invoke-Step "Staging repo SQL overrides into AzerothCore custom SQL paths" {
        Stage-RepoSqlOverrides -RepoRoot $repoRoot -SourceRoot $sourceRoot
    }
}

if (Test-Path $compatibilityOverlayScript) {
    Invoke-Step "Applying compatibility overlay patches" {
        $global:LASTEXITCODE = 0
        & $compatibilityOverlayScript -WorkspaceRoot $WorkspaceRoot
        if (-not $?) {
            throw "Compatibility overlay script failed."
        }
    }
}

if ($Build) {
    $buildWorkspaceRoot = Ensure-WorkspaceAlias -ActualWorkspaceRoot $WorkspaceRoot -AliasRoot $BuildAliasRoot
    $buildSourceRoot = Join-Path $buildWorkspaceRoot "source\azerothcore"
    $buildOutputRoot = Join-Path $buildWorkspaceRoot "build"
    $binOutputRoot = Join-Path $buildOutputRoot "bin\RelWithDebInfo"
    $mysqlRoot = $null
    $openSslRoot = $null
    Invoke-Step "Generating Visual Studio build files" {
        Reset-CMakeCacheForDependencyResolution -BuildRoot $buildOutputRoot
        $cmakeArgs = @("-S", $buildSourceRoot, "-B", $buildOutputRoot, "-A", "x64", "-DBUILD_SHARED_LIBS=OFF")
        $boostRoot = Get-BoostRootCandidate
        if ($boostRoot) {
            $cmakeArgs += "-DBoost_ROOT=$boostRoot"
        }
        $mysqlRoot = $manifest.runtime_layout.mysql_root
        if ($mysqlRoot -and (Test-Path $mysqlRoot)) {
            $cmakeArgs += "-DMYSQL_ROOT_DIR=$mysqlRoot"
            $mysqlLib = Get-MySQLLibraryCandidate -Root $mysqlRoot -WorkspaceRoot $WorkspaceRoot
            if ($mysqlLib) {
                $cmakeArgs += "-DMYSQL_LIBRARY=$mysqlLib"
            }
        }
        $openSslRoot = Get-OpenSSLRootCandidate
        if ($openSslRoot) {
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
        }
        Invoke-Native -FilePath $cmake -Arguments $cmakeArgs
    }
    Invoke-Step "Trimming worldserver resource include paths" {
        $patched = Repair-WorldserverResourceProject -BuildRoot $buildOutputRoot -SourceRoot $buildSourceRoot
        if (-not $patched) {
            throw "worldserver.vcxproj was not found under $buildOutputRoot"
        }
    }
    Invoke-Step "Building worldserver/authserver (RelWithDebInfo)" {
        Invoke-Native -FilePath $msbuild -Arguments @((Join-Path $buildOutputRoot "AzerothCore.sln"), "/m:1", "/p:Configuration=RelWithDebInfo")
    }
    Invoke-Step "Staging runtime DLL dependencies into $binOutputRoot" {
        if (-not (Test-Path $binOutputRoot)) {
            throw "Expected build output directory was not found: $binOutputRoot"
        }
        Stage-RuntimeDependencies -BinRoot $binOutputRoot -MySQLRoot $mysqlRoot -OpenSSLRoot $openSslRoot
    }
}

if (-not $WhatIf) {
    $coreHead = (& $git -C $sourceRoot rev-parse HEAD).Trim()
    $lines = @(
        "requested_core_commit=$($manifest.core.commit)",
        "core_head=$coreHead",
        "verified_modules=$(@($manifest.modules | Where-Object { $_.status -eq 'verified' }).Count)",
        "candidate_modules=$candidateCount",
        "unresolved_modules=$unresolvedCount"
    )
    if ($script:CheckpointNote) {
        $lines += "note=$script:CheckpointNote"
    }
    Set-Content -Path $statusPath -Value $lines
    $moduleCloneResults | ConvertTo-Json -Depth 4 | Set-Content -Path $moduleStatusPath
}

if ($script:CheckpointNote) {
    Write-Host "note=$script:CheckpointNote"
}
Write-Host "workspace=$WorkspaceRoot source=$sourceRoot build=$buildRoot run=$runRoot"
