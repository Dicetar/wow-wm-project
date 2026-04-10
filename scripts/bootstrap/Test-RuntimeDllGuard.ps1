param(
    [Parameter(Mandatory = $true)]
    [string]$BinRoot,
    [Parameter(Mandatory = $true)]
    [string]$LockPath
)

$ErrorActionPreference = "Stop"

function Get-Inventory {
    param([Parameter(Mandatory = $true)][string]$Root)

    $requiredNames = @("libmysql.dll", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "legacy.dll")
    $items = @()
    foreach ($name in $requiredNames) {
        $path = Join-Path $Root $name
        if (-not (Test-Path $path)) {
            throw "Required runtime DLL is missing: $path"
        }
        $item = Get-Item -LiteralPath $path
        $items += [pscustomobject]@{
            name = $name
            length = $item.Length
            sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    return $items
}

if (-not (Test-Path $LockPath)) {
    throw "Runtime DLL lock is missing: $LockPath. Re-run build-wm.bat to restage dependencies."
}

$lock = Get-Content -Path $LockPath -Raw | ConvertFrom-Json
$actualByName = @{}
foreach ($entry in @(Get-Inventory -Root $BinRoot)) {
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

Write-Host "runtime_dll_guard=ok"
