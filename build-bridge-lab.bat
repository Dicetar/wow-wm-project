@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bridge_lab\Build-BridgeLab.ps1" %*
