@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\bridge_lab\Summon-BridgeLabBoneboundTwins.ps1" %*
exit /b %ERRORLEVEL%
