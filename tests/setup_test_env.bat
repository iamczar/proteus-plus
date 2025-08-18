@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Usage:
REM   From within the tests folder:  call setup_test_env.bat
REM   Or from repo root:            call tests\setup_test_env.bat
REM   This will create tests\.venv-test, activate it, and install test deps

REM Resolve tests directory from this script's location
set "TEST_DIR=%~dp0"
cd /d "%TEST_DIR%"

REM Create venv inside tests if missing
if not exist ".venv-test\Scripts\python.exe" (
    echo Creating test virtual environment at tests\.venv-test ...
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
        py -3 -m venv .venv-test
    ) else (
        python -m venv .venv-test
    )
)

REM Activate venv
call .venv-test\Scripts\activate
if errorlevel 1 (
    echo Failed to activate virtual environment.
    exit /b 1
)

REM Upgrade pip and install test requirements from tests/requirements.txt
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Test environment ready at %TEST_DIR%\.venv-test
echo You are now in the .venv-test virtual environment in the tests folder.
echo To deactivate later, run:  deactivate
