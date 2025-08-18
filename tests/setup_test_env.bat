@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Usage:
REM   From a Command Prompt in repo root:  call tests\setup_test_env.bat
REM   This will create .venv-test, activate it, and install test deps

REM Resolve repo root from this script's directory
set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..
cd /d "%ROOT%"

REM Create venv if missing
if not exist ".venv-test\Scripts\python.exe" (
    echo Creating test virtual environment at .venv-test ...
    py -3 -m venv .venv-test
)

REM Activate venv
call .venv-test\Scripts\activate
if errorlevel 1 (
    echo Failed to activate virtual environment.
    exit /b 1
)

REM Upgrade pip and install requirements
python -m pip install --upgrade pip
python -m pip install -r tests\requirements.txt

echo.
echo Test environment ready. You are now in the .venv-test virtual environment.
echo To deactivate later, run:  deactivate

REM Keep session open if launched directly
echo.
cmd /k
