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
pip install --upgrade pip
REM Install root requirements
pip install -r requirements.txt
REM Install module_controller specific requirements
pip install -r module_controller/requirements.txt
pip install -r software_update/requirements.txt
pip install -r proteus-ui/requirements.txt

echo.
echo =======================================
echo ✅ Python environment setup complete.
echo You can now run tools using the virtual environment.
echo =======================================
pause


