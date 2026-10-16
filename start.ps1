Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Launching TERRAIN ANALYZER + OPENTELEMETRY STACK" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Starting Jaeger All-In-One Tracing Collector & UI on http://localhost:16686 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '.\telemetry_tools\jaeger-1.60.0-windows-amd64\jaeger-all-in-one.exe'"

Write-Host "2. Starting FastAPI Backend on http://localhost:5240 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m uvicorn backend.main:app --host 0.0.0.0 --port 5240 --reload"

Write-Host "3. Starting Vite React Frontend on http://localhost:3000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location frontend; npm run dev"

Write-Host ""
Write-Host "All services launched successfully!" -ForegroundColor Green
Write-Host "  - Web App:               http://localhost:3000" -ForegroundColor Green
Write-Host "  - API Backend:           http://localhost:5240" -ForegroundColor Green
Write-Host "  - Jaeger Tracing UI:     http://localhost:16686" -ForegroundColor Yellow
Write-Host "  - Telemetry Center:      http://localhost:5240/telemetry" -ForegroundColor Yellow
Write-Host "  - Prometheus /metrics:   http://localhost:5240/metrics" -ForegroundColor Yellow

