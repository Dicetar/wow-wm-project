param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$setupScript = Join-Path $repoRoot "scripts\bootstrap\Setup-Workspace.ps1"

& $setupScript -WorkspaceRoot $WorkspaceRoot -WhatIf:$WhatIf
