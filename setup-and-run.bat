@echo off
setlocal

echo.
echo =======================================
echo 🔍 Checking for PM2...
echo =======================================
where pm2 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ PM2 not found. Please make sure Node.js is installed.
    echo ℹ️  You can install it from: https://nodejs.org
    echo.
    echo Once Node.js is installed, run:
    echo     npm install -g pm2
    echo.
    echo Exiting setup...
    pause
    exit /b 1
)

echo.
echo =======================================
echo 🐍 Creating virtual environment...
echo =======================================
python -m venv venv

echo.
echo =======================================
echo 🎛️ Activating virtual environment...
echo =======================================
call venv\Scripts\activate

echo.
echo =======================================
echo 📦 Installing Python dependencies...
echo =======================================
pip install --upgrade pip
pip install -r software_update/requirements.txt
pip install -r proteus-ui/requirements.txt

echo.
echo =======================================
echo ▶️ Starting PM2 services...
echo =======================================
pm2 start ecosystem.config.js

echo.
echo =======================================
echo ✅ All done!
echo 🔧 Use 'pm2 status' or 'pm2 logs' to monitor your services.
echo =======================================
pause
