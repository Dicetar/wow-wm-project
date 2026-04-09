@echo off
title Rebuild AzerothCore Rebuilt Server
mode con: cols=70 lines=18
setlocal

set "PROJECT_ROOT=D:\WOW\wm-project"
set "BUILD_SCRIPT=%PROJECT_ROOT%\scripts\repack\New-ExactSourceTree.ps1"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%BUILD_SCRIPT%" (
  echo Missing rebuild script:
  echo   %BUILD_SCRIPT%
  pause
  exit /b 1
)

echo Rebuilding latest baseline from the current source tree...
echo This uses BuildOnly mode and does not re-clone the whole workspace.
echo.
"%POWERSHELL_EXE%" -NoLogo -ExecutionPolicy Bypass -File "%BUILD_SCRIPT%" -Build -BuildOnly
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
  echo Rebuild failed with exit code %EXIT_CODE%.
  pause
  exit /b %EXIT_CODE%
)

echo Rebuild finished successfully.
echo.
echo Next step:
echo   Run "Start Rebuilt Server.bat" to start or restart auth/world.
pause
exit /b 0
