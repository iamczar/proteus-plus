Param(
    [switch]$Restart
)

function Test-Command {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    return $null -ne $cmd
}

Write-Host "`n=======================================" -ForegroundColor Cyan
Write-Host "🔍 Checking for PM2..." -ForegroundColor Cyan
Write-Host "=======================================`n" -ForegroundColor Cyan

if (-not (Test-Command pm2)) {
    Write-Host "❌ PM2 not found. Checking for Node.js..." -ForegroundColor Yellow
    if (-not (Test-Command node)) {
        Write-Host "❌ Node.js not found. Please install Node.js from https://nodejs.org" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Node.js found. Installing PM2 globally..." -ForegroundColor Green
    npm install -g pm2
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install PM2. Try running PowerShell as Administrator." -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n=======================================" -ForegroundColor Cyan
Write-Host "🐍 Creating virtual environment..." -ForegroundColor Cyan
Write-Host "=======================================`n" -ForegroundColor Cyan

$python = "python"
if (-not (Test-Command $python)) { $python = "py" }

& $python -m venv "$PSScriptRoot/venv"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create virtual environment." -ForegroundColor Red
    exit 1
}

$venvPython = Join-Path $PSScriptRoot "venv/Scripts/python.exe"

Write-Host "`n=======================================" -ForegroundColor Cyan
Write-Host "📦 Installing Python dependencies..." -ForegroundColor Cyan
Write-Host "=======================================`n" -ForegroundColor Cyan

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit 1 }

# Core dependencies
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { exit 1 }

# Module controller specific deps
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "module_controller/requirements.txt")
if ($LASTEXITCODE -ne 0) { exit 1 }

# Software update service deps
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "software_update/requirements.txt")
if ($LASTEXITCODE -ne 0) { exit 1 }

# UI deps
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "proteus-ui/requirements.txt")
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n=======================================" -ForegroundColor Cyan
Write-Host "▶️ Starting PM2 services..." -ForegroundColor Cyan
Write-Host "=======================================`n" -ForegroundColor Cyan

if ($Restart) {
    pm2 restart (Join-Path $PSScriptRoot "ecosystem.config.js")
} else {
    pm2 start (Join-Path $PSScriptRoot "ecosystem.config.js")
}

pm2 save | Out-Null

Write-Host "`n=======================================" -ForegroundColor Cyan
Write-Host "✅ All done!" -ForegroundColor Green
Write-Host "🔧 Use 'pm2 status' or 'pm2 logs' to monitor your services." -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan


