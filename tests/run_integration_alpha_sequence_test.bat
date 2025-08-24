@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Usage:
rem   run_integration_alpha_sequence_test.bat [MODULE_ID] [MQTT_HOST]
rem Notes:
rem - If args are omitted, defaults are used (MODULE_ID=3005, MQTT_HOST=127.0.0.1).
rem - Ensure the Module Controller is running (python -m module_controller) before executing.

rem Defaults
if not defined MODULE_ID set "MODULE_ID=3005"
if not defined MQTT_HOST set "MQTT_HOST=127.0.0.1"

rem Arg overrides
if not "%~1"=="" set "MODULE_ID=%~1"
if not "%~2"=="" set "MQTT_HOST=%~2"

echo MODULE_ID=%MODULE_ID%
echo MQTT_HOST=%MQTT_HOST%

rem Move to repo root (this script lives in proteus-plus\tests)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.."

rem Run the hardware-in-the-loop integration test
python -m unittest tests\integration_alpha_sequence_mqtt_test.py
set "EXITCODE=%ERRORLEVEL%"

popd
exit /b %EXITCODE%


