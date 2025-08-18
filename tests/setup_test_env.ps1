# PowerShell setup for Proteus test environment in tests/.venv-test
# Usage (persist activation in current PS session):
#   cd proteus-plus/tests
#   . .\setup_test_env.ps1
#
# If you run without the leading dot (i.e., ./setup_test_env.ps1),
# the activation will not persist after the script exits.

param()

$ErrorActionPreference = 'Stop'

# Move to the folder of this script (tests directory)
Set-Location -Path $PSScriptRoot

# Create venv if missing
$venvPython = Join-Path $PSScriptRoot ".venv-test/Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Host "Creating test virtual environment at tests/.venv-test ..."
  try {
    py -3 -m venv .venv-test
  } catch {
    try { python -m venv .venv-test } catch { python3 -m venv .venv-test }
  }
}

# Upgrade pip and install requirements using venv python
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

# Activate venv for current shell (requires dot-sourcing this script)
. .\.venv-test\Scripts\Activate.ps1

Write-Host "Test environment ready. You are now in tests/.venv-test. To deactivate, run: deactivate"
