@echo off
setlocal

echo.
echo =======================================
echo 🔍 Checking for PM2...
echo =======================================
where pm2 >nul 2>&1
rem Use ERRORLEVEL form of the check so nested checks work correctly
if ERRORLEVEL 1 (
    echo ❌ PM2 not found. Checking for Node.js...

    rem Check if Node.js is available on PATH
    where node >nul 2>&1
    if ERRORLEVEL 1 (
        echo ❌ Node.js not found in PATH. Trying default locations...
        set "NODE_DEFAULT=%ProgramFiles%\nodejs\node.exe"
        if exist "%NODE_DEFAULT%" (
            set "PATH=%ProgramFiles%\nodejs;%PATH%"
            echo ⚠️  Using Node.js from "%ProgramFiles%\nodejs" for this session.
        ) else (
            set "NODE_DEFAULT_X86=%ProgramFiles(x86)%\nodejs\node.exe"
            if exist "%NODE_DEFAULT_X86%" (
                set "PATH=%ProgramFiles(x86)%\nodejs;%PATH%"
                echo ⚠️  Using Node.js from "%ProgramFiles(x86)%\nodejs" for this session.
            ) else (
                echo ❌ Node.js not found. Please install Node.js first.
                echo ℹ️  You can install it from: https://nodejs.org
                echo.
                echo Once Node.js is installed, run this batch file again.
                echo.
                echo Exiting setup...
                pause
                exit /b 1
            )
        )
    )

    echo ✅ Node.js found. Installing PM2...
    npm install -g pm2
    if ERRORLEVEL 1 (
        echo ❌ Failed to install PM2. Please try running as administrator.
        echo.
        echo Exiting setup...
        pause
        exit /b 1
    )
    echo ✅ PM2 installed successfully!
)

echo.
echo =======================================
echo 🐍 Checking for Python...
echo =======================================
python --version >nul 2>&1
if ERRORLEVEL 1 (
    echo ❌ Python not found on PATH.
    echo ℹ️  Please install Python 3.x from: https://www.python.org/downloads/windows/
    echo    When installing, be sure to check "Add python.exe to PATH".
    echo.
    echo Once Python is installed, re-run this script.
    echo.
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
python -m pip install --upgrade pip
REM Install root requirements
python -m pip install -r requirements.txt
REM Install module_controller specific requirements
python -m pip install -r module_controller/requirements.txt
python -m pip install -r software_update/requirements.txt
python -m pip install -r proteus-ui/requirements.txt

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


