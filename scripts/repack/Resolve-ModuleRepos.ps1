param(
    [string]$ManifestPath = "data/repack/live-repack-manifest.json",
    [string]$Output = "data/repack/module-repo-resolution.md",
    [string]$JsonOutput = "data/repack/module-repo-resolution.json"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not [System.IO.Path]::IsPathRooted($ManifestPath)) {
    $ManifestPath = Join-Path $repoRoot $ManifestPath
}
if (-not [System.IO.Path]::IsPathRooted($Output)) {
    $Output = Join-Path $repoRoot $Output
}
if (-not [System.IO.Path]::IsPathRooted($JsonOutput)) {
    $JsonOutput = Join-Path $repoRoot $JsonOutput
}

if (-not (Test-Path $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}

$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$git = $manifest.build_tooling.git_path
if (-not $git) {
    throw "git path was not captured in the manifest."
}

$lines = @(
    "# Module Repo Resolution",
    "",
    ("- Manifest: `"${ManifestPath}`""),
    "- Generated: $(Get-Date -Format s)",
    ""
)

$candidateCount = 0
$reachableCount = 0
$results = @()

foreach ($module in $manifest.modules) {
    if ($module.status -ne "candidate") {
        continue
    }
    $candidateCount++
    $repo = $module.repo_url
    if (-not $repo) {
        $lines += ("- `"{0}`": no repo URL candidate recorded." -f $module.display_name)
        $results += [pscustomobject]@{
            key = $module.key
            display_name = $module.display_name
            repo_url = $repo
            reachable = $false
            reason = "missing_repo_url"
        }
        continue
    }

    $escapedGit = $git.Replace('"', '""')
    $escapedRepo = $repo.Replace('"', '""')
    cmd /c """$escapedGit"" ls-remote --heads ""$escapedRepo"" HEAD 1>nul 2>nul"
    if ($LASTEXITCODE -eq 0) {
        $reachableCount++
        $lines += ("- `"{0}`": reachable candidate repo `"{1}`"" -f $module.display_name, $repo)
        $results += [pscustomobject]@{
            key = $module.key
            display_name = $module.display_name
            repo_url = $repo
            reachable = $true
            reason = $null
        }
    }
    else {
        $lines += ("- `"{0}`": unreachable candidate repo `"{1}`"" -f $module.display_name, $repo)
        $results += [pscustomobject]@{
            key = $module.key
            display_name = $module.display_name
            repo_url = $repo
            reachable = $false
            reason = "ls_remote_failed"
        }
    }
}

$lines += ""
$lines += "- candidate_count=$candidateCount"
$lines += "- reachable_count=$reachableCount"

New-Item -ItemType Directory -Force -Path (Split-Path $Output) | Out-Null
Set-Content -Path $Output -Value $lines
$results | ConvertTo-Json -Depth 4 | Set-Content -Path $JsonOutput
Write-Host "output=$Output json=$JsonOutput candidates=$candidateCount reachable=$reachableCount"
