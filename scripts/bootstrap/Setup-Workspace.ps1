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
$git = Get-GitPath

Invoke-Step "Creating workspace directories under $($paths.root)" {
    foreach ($relativePath in $manifest.workspace.directories) {
        Ensure-Directory -Path (Resolve-PortablePath -BasePath $paths.root -CandidatePath $relativePath)
    }
}

Invoke-Step "Cloning or updating AzerothCore core into $($paths.coreRoot)" {
    Clone-Or-UpdateGitRepo `
        -GitPath $git `
        -RepoUrl $manifest.core.repo_url `
        -TargetDir $paths.coreRoot `
        -Branch $manifest.core.branch `
        -Commit $manifest.core.commit
}

Invoke-Step "Cloning or updating module sources into $($paths.moduleRoot)" {
    Ensure-Directory -Path (Join-Path $paths.coreRoot "modules")
    foreach ($module in $manifest.modules) {
        $targetDir = Resolve-PortablePath -BasePath $paths.root -CandidatePath $module.target_path
        Clone-Or-UpdateGitRepo `
            -GitPath $git `
            -RepoUrl $module.repo_url `
            -TargetDir $targetDir `
            -Branch $module.branch `
            -Commit $module.commit
        $junctionPath = Join-Path (Join-Path $paths.coreRoot "modules") $module.key
        Ensure-DirectoryJunction -Path $junctionPath -Target $targetDir
    }
}

Invoke-Step "Syncing repo-owned local modules into $($paths.moduleRoot)" {
    Sync-LocalModules -RepoRoot $repoRoot -WorkspaceRoot $paths.root -CoreRoot $paths.coreRoot -Manifest $manifest
}

Invoke-Step "Disabling IPP optional SQL updates in the workspace" {
    $ippModuleRoot = Join-Path $paths.moduleRoot "mod-individual-progression"
    $moved = Disable-IppOptionalSql -ModuleRoot $ippModuleRoot
    Write-Host "ipp_optional_sql_disabled=$moved"
}

Invoke-Step "Fetching and staging local build dependencies into $($paths.depsRoot)" {
    $dependencyState = @()
    foreach ($dependency in $manifest.dependencies) {
        $dependencyState += Install-Dependency `
            -Dependency $dependency `
            -WorkspaceRoot $paths.root `
            -DownloadsRoot $paths.downloadsRoot
    }
    Save-JsonFile -Path (Join-Path $paths.stateRoot "dependencies.json") -Value $dependencyState
}

Invoke-Step "Copying repo-owned assets into $($paths.runRoot)" {
    foreach ($asset in $manifest.stage_assets) {
        Copy-RepoAsset -RepoRoot $repoRoot -Asset $asset -WorkspaceRoot $paths.root
    }
}

Invoke-Step "Recording setup state into $($paths.stateRoot)" {
    $moduleState = foreach ($module in $manifest.modules) {
        $targetDir = Resolve-PortablePath -BasePath $paths.root -CandidatePath $module.target_path
        [pscustomobject]@{
            key = $module.key
            kind = "git"
            repo_url = $module.repo_url
            target_path = $targetDir
            exists = Test-Path $targetDir
        }
    }
    $moduleState += foreach ($module in @($manifest.local_modules)) {
        $targetDir = Resolve-PortablePath -BasePath $paths.root -CandidatePath $module.target_path
        [pscustomobject]@{
            key = $module.key
            kind = "local"
            source = Resolve-PortablePath -BasePath $repoRoot -CandidatePath $module.source
            target_path = $targetDir
            exists = Test-Path $targetDir
        }
    }
    Save-JsonFile -Path (Join-Path $paths.stateRoot "sources.json") -Value $moduleState
    Save-JsonFile -Path (Join-Path $paths.stateRoot "setup-summary.json") -Value ([pscustomobject]@{
        workspace_root = $paths.root
        core_root = $paths.coreRoot
        module_root = $paths.moduleRoot
        dependency_root = $paths.depsRoot
        run_root = $paths.runRoot
        module_count = @($manifest.modules).Count + @($manifest.local_modules).Count
        dependency_count = @($manifest.dependencies).Count
        what_if = [bool]$WhatIf
    })
}

Write-Host "setup_ready=true workspace=$($paths.root) core=$($paths.coreRoot) modules=$($paths.moduleRoot) deps=$($paths.depsRoot)"
Write-Host "next_step=run build-wm.bat"
