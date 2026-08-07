@echo off
title Terrain Analyzer Launcher
echo ========================================================
echo   Launching TERRAIN ANALYZER (Backend + Frontend)
echo ========================================================
echo.

echo Starting FastAPI Backend on http://localhost:8000 ...
start "Terrain Analyzer Backend" cmd /k "python -m uvicorn backend.main:app --port 8000 --reload"

echo Starting Vite React Frontend on http://localhost:3000 ...
start "Terrain Analyzer Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Both servers are running! You can open http://localhost:3000 in your browser.
