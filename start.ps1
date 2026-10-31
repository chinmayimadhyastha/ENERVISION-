Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " ENERVISION - Official Decision-Support Platform for Karnataka" -ForegroundColor Green
Write-Host " Starting Backend (Flask :5000) and Frontend (Vite :5173)..." -ForegroundColor Yellow
Write-Host "======================================================================"

$repoRoot = $PSScriptRoot

# Start Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot'; & '.\.venv\Scripts\python.exe' backend/app.py"

# Start Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot\frontend'; npm run dev"

Write-Host "`nBoth processes launched!" -ForegroundColor Green
Write-Host "  * Backend API:  http://localhost:5000/api/health" -ForegroundColor Cyan
Write-Host "  * Web Portal:   http://localhost:5173" -ForegroundColor Cyan
