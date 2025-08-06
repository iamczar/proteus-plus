Write-Host "========================================" -ForegroundColor Green
Write-Host "AlphaCommsManager Test Runner" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Restarting MicroPython firmware..." -ForegroundColor Yellow
try {
    ampy --port COM4 reset
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to restart firmware" -ForegroundColor Red
        Read-Host "Press Enter to continue"
        exit 1
    }
    Write-Host "Firmware restarted successfully." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to restart firmware - $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to continue"
    exit 1
}
Write-Host ""

Write-Host "Waiting 5 seconds for firmware to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
Write-Host ""

Write-Host "Running AlphaCommsManager tests..." -ForegroundColor Yellow
try {
    python alphacommsmanager_test.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Tests failed" -ForegroundColor Red
        Read-Host "Press Enter to continue"
        exit 1
    }
} catch {
    Write-Host "ERROR: Failed to run tests - $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to continue"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Test completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Read-Host "Press Enter to continue" 