param(
    [string]$LabRoot = "D:\WOW\WM_BridgeLab",
    [string]$WorkingRebuildRoot = "D:\WOW\Azerothcore_WoTLK_Rebuild",
    [switch]$ConfirmPromoteToWorkingRebuild
)

$ErrorActionPreference = "Stop"

if (-not $ConfirmPromoteToWorkingRebuild) {
    throw "Refusing to touch the working rebuild. Re-run with -ConfirmPromoteToWorkingRebuild after lab smoke tests pass."
}

$labBin = Join-Path $LabRoot "build\bin\RelWithDebInfo"
$workingBin = Join-Path $WorkingRebuildRoot "build\bin\RelWithDebInfo"

foreach ($required in @($labBin, $workingBin)) {
    if (-not (Test-Path $required)) {
        throw "Missing required path: $required"
    }
}

Write-Host "Promoting lab authserver/worldserver binaries from $labBin to $workingBin"
Copy-Item -LiteralPath (Join-Path $labBin "authserver.exe") -Destination $workingBin -Force
Copy-Item -LiteralPath (Join-Path $labBin "worldserver.exe") -Destination $workingBin -Force
Write-Host "Promotion complete. Runtime DLLs are intentionally not copied by this script."
