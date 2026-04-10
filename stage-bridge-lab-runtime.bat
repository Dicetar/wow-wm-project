@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bridge_lab\Stage-BridgeLabRuntime.ps1" %*
