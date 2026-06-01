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
set "LLM_LANES=chat"
set "LLM_MODEL=(panel setting)"
:parse_args
if "%~1"=="" goto run_autoplay
if /I "%~1"=="-PlayerGuid" goto arg_player_guid
if /I "%~1"=="-LlmModel" goto arg_llm_model
if /I "%~1"=="-LlmBaseUrl" goto arg_llm_base_url
if /I "%~1"=="-LlmLanes" goto arg_llm_lanes
if /I "%~1"=="-LlmEventAgeSeconds" goto arg_llm_event_age
if /I "%~1"=="-LlmCooldownSeconds" goto arg_llm_cooldown
if /I "%~1"=="-LlmEventsPerTick" goto arg_llm_events_per_tick
if /I "%~1"=="-NoLlm" goto arg_no_llm
if /I "%~1"=="-NoLlmChat" goto arg_no_llm_chat
set "ARGS=%ARGS% %~1"
shift
goto parse_args

:arg_player_guid
set "ARGS=%ARGS% --player-guid "%~2""
shift
shift
goto parse_args

:arg_llm_model
set "ARGS=%ARGS% --llm-model "%~2""
set "LLM_MODEL=%~2"
shift
shift
goto parse_args

:arg_llm_base_url
set "ARGS=%ARGS% --llm-base-url "%~2""
shift
shift
goto parse_args

:arg_llm_lanes
set "LANES=%~2"
shift
shift
goto collect_lanes

:collect_lanes
if "%~1"=="" goto lanes_done
set "NEXT_ARG=%~1"
if "%NEXT_ARG:~0,1%"=="-" goto lanes_done
set "LANES=%LANES%,%~1"
shift
goto collect_lanes

:lanes_done
set "LLM_LANES=%LANES%"
goto parse_args

:arg_llm_event_age
set "ARGS=%ARGS% --llm-event-age-seconds "%~2""
shift
shift
goto parse_args

:arg_llm_cooldown
set "ARGS=%ARGS% --llm-cooldown-seconds "%~2""
shift
shift
goto parse_args

:arg_llm_events_per_tick
set "ARGS=%ARGS% --llm-events-per-tick "%~2""
shift
shift
goto parse_args

:arg_no_llm
set "ARGS=%ARGS% --no-llm"
shift
goto parse_args

:arg_no_llm_chat
set "ARGS=%ARGS% --no-llm-chat"
shift
goto parse_args

:run_autoplay
set "RUN_ROOT=%PROJECT_ROOT%\.wm-bootstrap\state\autoplay"
if not exist "%RUN_ROOT%" mkdir "%RUN_ROOT%"
set "RUNNER=%RUN_ROOT%\run-wm-playable.bat"
set "STDOUT=%RUN_ROOT%\autoplay.stdout.log"
set "STDERR=%RUN_ROOT%\autoplay.stderr.log"

(
  echo @echo off
  echo setlocal
  echo set "WM_WORLD_DB_PORT=33307"
  echo set "WM_CHAR_DB_PORT=33307"
  echo set "WM_SOAP_PORT=7879"
  echo set "WM_SOAP_ENABLED=1"
  echo cd /d "%PROJECT_ROOT%"
  echo "%PYTHON_EXE%" -m wm.autoplay run --project-root "%PROJECT_ROOT%" --llm-lanes "%LLM_LANES%" %ARGS% --summary ^>^> "%STDOUT%" 2^>^> "%STDERR%"
) > "%RUNNER%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ComSpec%' -ArgumentList @('/c','%RUNNER%') -WorkingDirectory '%PROJECT_ROOT%' -WindowStyle Hidden"
if ERRORLEVEL 1 exit /b %ERRORLEVEL%

echo wm_playable_started=true lanes=%LLM_LANES% model=%LLM_MODEL% stdout=%STDOUT% stderr=%STDERR%
powershell -NoProfile -Command "Start-Sleep -Seconds 2" >nul
"%PYTHON_EXE%" -m wm.autoplay status --summary
exit /b %ERRORLEVEL%
