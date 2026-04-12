@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\client\Clear-WoWItemCache.ps1"
endlocal
