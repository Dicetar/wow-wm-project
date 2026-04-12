@echo off
title WM Bridge Lab Server
mode con: cols=62 lines=18
setlocal EnableDelayedExpansion

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

if defined WM_BRIDGE_LAB_ROOT (
  set "WORKSPACE_ROOT=%WM_BRIDGE_LAB_ROOT%"
) else (
  set "WORKSPACE_ROOT=D:\WOW\WM_BridgeLab"
)

set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "RUN_DIR=%WORKSPACE_ROOT%\run"
set "BIN_DIR=%RUN_DIR%\bin"
set "AUTH_EXE=%BIN_DIR%\authserver.exe"
set "WORLD_EXE=%BIN_DIR%\worldserver.exe"
set "WORLD_CFG=%RUN_DIR%\configs\worldserver.conf"
set "AUTH_CFG=%RUN_DIR%\configs\authserver.conf"
set "RUNTIME_GUARD=%RUN_DIR%\helpers\Test-RuntimeDllGuard.ps1"
set "DLL_LOCK=%WORKSPACE_ROOT%\state\runtime-dlls.lock.json"
set "START_MYSQL_PS=%PROJECT_ROOT%\scripts\bridge_lab\Start-BridgeLabMySql.ps1"
set "STOP_MYSQL_PS=%PROJECT_ROOT%\scripts\bridge_lab\Stop-BridgeLabMySql.ps1"
set "SYNC_REALMLIST_PS=%PROJECT_ROOT%\scripts\bridge_lab\Sync-BridgeLabRealmlist.ps1"
set "RESTART_WORLD_PS=%PROJECT_ROOT%\scripts\bridge_lab\Restart-BridgeLabWorldServer.ps1"

if not exist "%WORLD_CFG%" (
  echo Missing lab world config at "%WORLD_CFG%"
  echo Run build-wm.bat or stage-bridge-lab-runtime.bat first.
  pause
  exit /b 1
)

if not exist "%AUTH_CFG%" (
  echo Missing lab auth config at "%AUTH_CFG%"
  echo Run build-wm.bat or stage-bridge-lab-runtime.bat first.
  pause
  exit /b 1
)

if not exist "%AUTH_EXE%" (
  echo Missing lab authserver at "%AUTH_EXE%"
  echo Run build-wm.bat or stage-bridge-lab-runtime.bat first.
  pause
  exit /b 1
)

if not exist "%WORLD_EXE%" (
  echo Missing lab worldserver at "%WORLD_EXE%"
  echo Run build-wm.bat or stage-bridge-lab-runtime.bat first.
  pause
  exit /b 1
)

if not exist "%START_MYSQL_PS%" (
  echo Missing lab MySQL helper at "%START_MYSQL_PS%"
  pause
  exit /b 1
)

if not exist "%SYNC_REALMLIST_PS%" (
  echo Missing lab realmlist sync helper at "%SYNC_REALMLIST_PS%"
  pause
  exit /b 1
)

if not exist "%RESTART_WORLD_PS%" (
  echo Missing lab world restart helper at "%RESTART_WORLD_PS%"
  pause
  exit /b 1
)

if exist "%RUNTIME_GUARD%" (
  "%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%RUNTIME_GUARD%" -BinRoot "%BIN_DIR%" -LockPath "%DLL_LOCK%"
  if errorlevel 1 (
    echo Runtime DLL guard failed. Re-run build-wm.bat or stage-bridge-lab-runtime.bat before launching.
    pause
    exit /b 1
  )
)

:MENU
cls
color 0A
echo 1 - Start All Lab Servers
echo 2 - Restart Lab World Server
echo 3 - Stop Lab MySQL
echo 4 - Open Lab Config Folder
echo 5 - Open Lab Logs Folder
echo 6 - Exit
echo.
set /p M=Type menu number then press ENTER: 
if "%M%"=="1" goto STARTALL
if "%M%"=="2" goto RESTARTWORLD
if "%M%"=="3" goto STOPMYSQL
if "%M%"=="4" goto OPENCONFIG
if "%M%"=="5" goto OPENLOGS
if "%M%"=="6" goto :EOF
goto MENU

:STARTALL
cls
echo CONNECTING LAB DATABASE...
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%START_MYSQL_PS%" -WorkspaceRoot "%WORKSPACE_ROOT%" -Port 33307
if errorlevel 1 (
  echo Lab MySQL failed to start.
  pause
  goto MENU
)
timeout /t 3 >nul

echo SYNCHRONIZING LAB REALMLIST...
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SYNC_REALMLIST_PS%" -WorkspaceRoot "%WORKSPACE_ROOT%" -MySqlPort 33307
if errorlevel 1 (
  echo Lab realmlist sync failed.
  pause
  goto MENU
)
timeout /t 1 >nul

cls
echo CONNECTING LAB AUTH SERVER...
set "WM_TARGET_EXE=%AUTH_EXE%"
"%POWERSHELL_EXE%" -NoProfile -Command "$p = Get-Process authserver -ErrorAction SilentlyContinue | Where-Object { $_.Path -ieq $env:WM_TARGET_EXE } | Select-Object -First 1; if ($p) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  start "BridgeLab AuthServer" /D "%RUN_DIR%" "%AUTH_EXE%" -c configs\authserver.conf
) else (
  echo Lab authserver was already started.
)
timeout /t 2 >nul

cls
echo CONNECTING LAB WORLD SERVER...
set "WM_TARGET_EXE=%WORLD_EXE%"
"%POWERSHELL_EXE%" -NoProfile -Command "$p = Get-Process worldserver -ErrorAction SilentlyContinue | Where-Object { $_.Path -ieq $env:WM_TARGET_EXE } | Select-Object -First 1; if ($p) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  start "BridgeLab WorldServer" /D "%RUN_DIR%" "%WORLD_EXE%" -c configs\worldserver.conf
) else (
  echo Lab worldserver was already started.
)
timeout /t 3 >nul

cls
echo LOADING LAB WORLD SERVER, PLEASE WAIT!
timeout /t 10 >nul
goto MENU

:RESTARTWORLD
cls
echo RESTARTING LAB WORLD SERVER...
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%RESTART_WORLD_PS%" -WorkspaceRoot "%WORKSPACE_ROOT%"
timeout /t 3 >nul
goto MENU

:STOPMYSQL
cls
echo STOPPING LAB MYSQL...
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%STOP_MYSQL_PS%" -WorkspaceRoot "%WORKSPACE_ROOT%"
timeout /t 2 >nul
goto MENU

:OPENCONFIG
start "" "%RUN_DIR%\configs"
goto MENU

:OPENLOGS
start "" "%WORKSPACE_ROOT%\logs"
goto MENU

:EOF
exit /b 0
