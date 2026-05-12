@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "SCRIPT=%PROJECT_ROOT%\scripts\bridge_lab\Start-BridgeLabNativeWatch.ps1"

if not exist "%SCRIPT%" (
  echo Missing BridgeLab watcher launcher at "%SCRIPT%"
  pause
  exit /b 1
)

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -WorkspaceRoot "%PROJECT_ROOT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%WM_BRIDGE_LAB_WATCH_NO_PAUSE%"=="1" (
  echo.
  if "%EXIT_CODE%"=="0" (
    echo BridgeLab watcher launcher finished.
  ) else (
    echo BridgeLab watcher launcher failed with exit code %EXIT_CODE%.
  )
  pause
)

exit /b %EXIT_CODE%
