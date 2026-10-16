@echo off
title Terrain Analyzer & OpenTelemetry Launcher
echo ========================================================
echo   Launching TERRAIN ANALYZER + OPENTELEMETRY STACK
echo ========================================================
echo.

echo 1. Starting Jaeger Tracing Collector & UI on http://localhost:16686 ...
start "Jaeger Tracing Backend" cmd /k ".\telemetry_tools\jaeger-1.60.0-windows-amd64\jaeger-all-in-one.exe"

echo 2. Starting FastAPI Backend on http://localhost:5240 ...
start "Terrain Analyzer Backend" cmd /k "python -m uvicorn backend.main:app --host 0.0.0.0 --port 5240 --reload"

echo 3. Starting Vite React Frontend on http://localhost:3000 ...
start "Terrain Analyzer Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo All services launched!
echo   - Web UI:               http://localhost:3000
echo   - Backend API:          http://localhost:5240
echo   - Jaeger Tracing:       http://localhost:16686
echo   - Telemetry Dashboard:  http://localhost:5240/telemetry
echo   - Prometheus Metrics:   http://localhost:5240/metrics

