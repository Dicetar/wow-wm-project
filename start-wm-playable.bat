@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

set "WM_WORLD_DB_PORT=33307"
set "WM_CHAR_DB_PORT=33307"
set "WM_SOAP_PORT=7879"
set "WM_SOAP_ENABLED=1"

cd /d "%PROJECT_ROOT%"

set "ARGS="
:parse_args
if "%~1"=="" goto run_autoplay
if /I "%~1"=="-PlayerGuid" (
  set "ARGS=%ARGS% --player-guid %~2"
  shift
  shift
  goto parse_args
)
set "ARGS=%ARGS% %~1"
shift
goto parse_args

:run_autoplay
"%PYTHON_EXE%" -m wm.autoplay run --project-root "%PROJECT_ROOT%" %ARGS%
exit /b %ERRORLEVEL%
