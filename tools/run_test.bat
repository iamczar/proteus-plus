@echo off
echo ========================================
echo AlphaCommsManager Test Runner
echo ========================================
echo.

echo Restarting MicroPython firmware...
ampy --port COM4 reset
if %errorlevel% neq 0 (
    echo ERROR: Failed to restart firmware
    pause
    exit /b 1
)
echo Firmware restarted successfully.
echo.

echo Waiting 5 seconds for firmware to initialize...
timeout /t 5 /nobreak >nul
echo.

echo Running AlphaCommsManager tests...
python alphacommsmanager_test.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Tests failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Test completed successfully!
echo ========================================
pause 