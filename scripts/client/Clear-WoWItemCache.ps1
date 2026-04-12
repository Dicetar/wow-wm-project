param(
    [string]$ClientRoot = "D:\WOW\world of warcraft 3.3.5a hd"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ClientRoot)) {
    throw "WoW client root was not found: $ClientRoot"
}

$running = Get-Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.ProcessName -in @("Wow", "Wow-64", "WowClassic", "WowClassicT")
    }

if ($running) {
    $names = ($running | Select-Object -ExpandProperty ProcessName | Sort-Object -Unique) -join ", "
    throw "Close the WoW client before clearing the item cache. Running processes: $names"
}

$cacheRoot = Join-Path $ClientRoot "Cache\WDB"
$patterns = @("itemcache.wdb", "wowitemcache.wdb")

if (-not (Test-Path -LiteralPath $cacheRoot)) {
    Write-Host "item_cache_cleared=false cache_root_missing=$cacheRoot"
    exit 0
}

$targets = foreach ($pattern in $patterns) {
    Get-ChildItem -Path $cacheRoot -Recurse -File -Filter $pattern -ErrorAction SilentlyContinue
}

$uniqueTargets = $targets | Sort-Object FullName -Unique

if (-not $uniqueTargets) {
    Write-Host "item_cache_cleared=false files_found=0 cache_root=$cacheRoot"
    exit 0
}

foreach ($target in $uniqueTargets) {
    Remove-Item -LiteralPath $target.FullName -Force
    Write-Host "deleted=$($target.FullName)"
}

Write-Host "item_cache_cleared=true files_deleted=$($uniqueTargets.Count) cache_root=$cacheRoot"
