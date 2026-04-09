@echo off
setlocal
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "SCRIPT_PATH=%ROOT_DIR%\scripts\bootstrap\Setup-Workspace.ps1"

if not exist "%SCRIPT_PATH%" (
  echo Missing setup script:
  echo   %SCRIPT_PATH%
  exit /b 1
)

"%POWERSHELL_EXE%" -NoLogo -ExecutionPolicy Bypass -File "%SCRIPT_PATH%" %*
exit /b %ERRORLEVEL%
