Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Launching TERRAIN ANALYZER (Backend + Frontend)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting FastAPI Backend on http://localhost:5000 ..." -ForegroundColor Cyan

Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m uvicorn backend.main:app --port 5000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location frontend; npm run dev"

Write-Host "Both servers launched! Open http://localhost:3000 in your browser." -ForegroundColor Green
