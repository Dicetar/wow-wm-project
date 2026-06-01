@echo off
setlocal

set "ROOT=%~dp0"
set "HOST=127.0.0.1"
set "PORT=8765"

:parse
if "%~1"=="" goto parsed
if /I "%~1"=="-Host" (
  set "HOST=%~2"
  shift
  shift
  goto parse
)
if /I "%~1"=="-Port" (
  set "PORT=%~2"
  shift
  shift
  goto parse
)
shift
goto parse

:parsed
set "STATE=%ROOT%.wm-bootstrap\state\control-panel"
if not exist "%STATE%" mkdir "%STATE%"

start "WM Control Panel Server" /MIN cmd /c ""cd /d "%ROOT%" && python -m wm.panel serve --host %HOST% --port %PORT% > "%STATE%\panel-app.stdout.log" 2> "%STATE%\panel-app.stderr.log"""

powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='http://%HOST%:%PORT%'; $profile=Join-Path '%STATE%' 'browser-profile'; New-Item -ItemType Directory -Force -Path $profile | Out-Null; Start-Sleep -Seconds 1; $edge=(Get-Command msedge.exe -ErrorAction SilentlyContinue).Source; $chrome=(Get-Command chrome.exe -ErrorAction SilentlyContinue).Source; if($edge){ Start-Process $edge -ArgumentList @('--app=' + $url, '--user-data-dir=' + $profile) } elseif($chrome){ Start-Process $chrome -ArgumentList @('--app=' + $url, '--user-data-dir=' + $profile) } else { Start-Process $url }"

echo WM Control Panel app window requested at http://%HOST%:%PORT%
