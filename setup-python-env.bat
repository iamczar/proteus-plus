@echo off
setlocal

REM Ensure we are in the directory of this script (repository root)
cd /d "%~dp0"

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
echo ✅ Python environment setup complete.
echo You can now run tools using the virtual environment.
echo =======================================
pause


