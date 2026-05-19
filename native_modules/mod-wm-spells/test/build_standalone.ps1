# Standalone Phase 0E native test build — no CMake, no reconfigure.
# Compiles only the engine-independent wm_spell_internal TU + micro-harness
# with cl.exe. Shims FIRST so #include "Common.h" resolves to the cstdint
# shim, then module src, then the test dir. Mirrors the 0A bridge harness.

$ErrorActionPreference = "Stop"

$vcvars = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
$root   = "D:\WOW\WM_BridgeLab\src\modules\mod-wm-spells"
$test   = "$root\test"
$src    = "$root\src"
$out    = "$test\out"

New-Item -ItemType Directory -Force -Path $out | Out-Null

$inc  = "/I`"$test\shims`" /I`"$src`" /I`"$test`""
$srcs = "`"$src\wm_spell_internal.cpp`" `"$test\test_wm_spell_internal.cpp`" `"$test\test_main.cpp`""
$cl   = "cl /nologo /std:c++17 /EHsc /W3 $inc $srcs /Fe`"$out\wm_spell_unit_tests.exe`" /Fo`"$out\\`""

cmd /c "`"$vcvars`" >nul 2>&1 && $cl"
if ($LASTEXITCODE -ne 0) { Write-Host "BUILD FAILED ($LASTEXITCODE)"; exit $LASTEXITCODE }

Write-Host "`n--- running wm_spell_unit_tests ---"
& "$out\wm_spell_unit_tests.exe"
$rc = $LASTEXITCODE
Write-Host "--- exit $rc ---"
exit $rc
