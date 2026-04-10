@echo off
title AzerothCore Rebuilt Server
mode con: cols=60 lines=16
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "RUN_DIR=%ROOT_DIR%\run"
set "BIN_DIR=%ROOT_DIR%\build\bin\RelWithDebInfo"
set "MYSQL_EXE=%RUN_DIR%\mysql\bin\mysqld.exe"
set "AUTH_EXE=%BIN_DIR%\authserver.exe"
set "WORLD_EXE=%BIN_DIR%\worldserver.exe"
set "RUNTIME_GUARD=%RUN_DIR%\helpers\Test-RuntimeDllGuard.ps1"
set "DLL_LOCK=%ROOT_DIR%\state\runtime-dlls.lock.json"

if not exist "%RUN_DIR%\configs\worldserver.conf" (
  echo Missing run config at "%RUN_DIR%\configs\worldserver.conf"
  pause
  exit /b 1
)

if not exist "%AUTH_EXE%" (
  echo Missing authserver at "%AUTH_EXE%"
  pause
  exit /b 1
)

if not exist "%WORLD_EXE%" (
  echo Missing worldserver at "%WORLD_EXE%"
  pause
  exit /b 1
)

if exist "%RUNTIME_GUARD%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%RUNTIME_GUARD%" -BinRoot "%BIN_DIR%" -LockPath "%DLL_LOCK%"
  if errorlevel 1 (
    echo Runtime DLL guard failed. Re-run build-wm.bat or rebuild the server before launching.
    pause
    exit /b 1
  )
)

:MENU
cls
color 0A
echo 1 - Start All Servers
echo 2 - Restart World Server (Visible)
echo 3 - Open Config Folder
echo 4 - Open Logs Folder
echo 5 - Exit
echo.
set /p M=Type menu number then press ENTER: 
if "%M%"=="1" goto STARTALL
if "%M%"=="2" goto RESTARTWORLD
if "%M%"=="3" goto OPENCONFIG
if "%M%"=="4" goto OPENLOGS
if "%M%"=="5" goto :EOF
goto MENU

:STARTALL
cls
echo CONNECTING DATABASE...
tasklist /fi "ImageName eq mysqld.exe" /fo csv 2>NUL | find /I "mysqld.exe" >NUL
if "%ERRORLEVEL%"=="1" (
  if exist "%MYSQL_EXE%" (
    start "Rebuilt MySQL" /min "%MYSQL_EXE%" --console --standalone --max_allowed_packet=128M
  ) else (
    echo Mysql executable not found, skipping database start.
  )
) else (
  echo Mysql was already started.
)
timeout /t 8 >nul

cls
echo CONNECTING LOGON AUTH SERVER...
tasklist /fi "ImageName eq authserver.exe" /fo csv 2>NUL | find /I "authserver.exe" >NUL
if "%ERRORLEVEL%"=="1" (
  start "Rebuilt AuthServer" /D "%RUN_DIR%" "%AUTH_EXE%" -c configs\authserver.conf
) else (
  echo Authserver was already started.
)
timeout /t 3 >nul

cls
echo CONNECTING LOGON WORLD SERVER...
tasklist /fi "ImageName eq worldserver.exe" /fo csv 2>NUL | find /I "worldserver.exe" >NUL
if "%ERRORLEVEL%"=="1" (
  start "Rebuilt WorldServer" /D "%RUN_DIR%" "%WORLD_EXE%" -c configs\worldserver.conf
) else (
  echo Worldserver was already started.
)
timeout /t 3 >nul

cls
echo LOADING WORLD SERVER, PLEASE WAIT!
timeout /t 15 >nul
goto MENU

:RESTARTWORLD
cls
echo RESTARTING WORLD SERVER...
tasklist /fi "ImageName eq worldserver.exe" /fo csv 2>NUL | find /I "worldserver.exe" >NUL
if "%ERRORLEVEL%"=="0" (
  taskkill /F /IM worldserver.exe >nul 2>&1
  timeout /t 3 >nul
)
start "Rebuilt WorldServer" /D "%RUN_DIR%" "%WORLD_EXE%" -c configs\worldserver.conf
timeout /t 3 >nul
goto MENU

:OPENCONFIG
start "" "%RUN_DIR%\configs"
goto MENU

:OPENLOGS
start "" "%RUN_DIR%\logs"
goto MENU

:EOF
exit /b 0
