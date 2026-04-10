param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$buildScript = Join-Path $repoRoot "scripts\bootstrap\Build-Workspace.ps1"

& $buildScript -WorkspaceRoot $WorkspaceRoot -WhatIf:$WhatIf
