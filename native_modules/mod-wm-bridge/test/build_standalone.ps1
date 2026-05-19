# Standalone Phase 0 native test build — no CMake, no reconfigure.
# Compiles only the engine-independent WM TUs + micro-harness with cl.exe.
# Include order: shims FIRST so #include "Common.h" resolves to the
# cstdint shim, then module src, then the test dir.

$ErrorActionPreference = "Stop"

$vcvars = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
$root   = "D:\WOW\WM_BridgeLab\src\modules\mod-wm-bridge"
$test   = "$root\test"
$src    = "$root\src"
$out    = "$test\out"

New-Item -ItemType Directory -Force -Path $out | Out-Null

$inc  = "/I`"$test\shims`" /I`"$src`" /I`"$test`""
$srcs = "`"$src\wm_effect_registry.cpp`" `"$src\wm_bridge_json.cpp`" `"$src\wm_bridge_action_registry.cpp`" `"$test\test_wm_effect_registry.cpp`" `"$test\test_wm_json.cpp`" `"$test\test_wm_action_registry.cpp`" `"$test\test_main.cpp`""
$cl   = "cl /nologo /std:c++17 /EHsc /W3 $inc $srcs /Fe`"$out\wm_unit_tests.exe`" /Fo`"$out\\`""

cmd /c "`"$vcvars`" >nul 2>&1 && $cl"
if ($LASTEXITCODE -ne 0) { Write-Host "BUILD FAILED ($LASTEXITCODE)"; exit $LASTEXITCODE }

Write-Host "`n--- running wm_unit_tests ---"
& "$out\wm_unit_tests.exe"
$rc = $LASTEXITCODE
Write-Host "--- exit $rc ---"
exit $rc
