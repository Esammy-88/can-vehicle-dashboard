@echo off
rem One-click start on Windows: opens the backend and the frontend in two
rem separate windows, then the dashboard in the browser. Close a window
rem (or press Ctrl+C in it) to stop that part.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Python environment missing. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements-dev.txt
    pause
    exit /b 1
)
if not exist "frontend\node_modules" (
    echo Frontend dependencies missing. Run: cd frontend ^&^& npm install
    pause
    exit /b 1
)

start "CAN Dashboard - BACKEND (keep open)" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend"
start "CAN Dashboard - FRONTEND (keep open)" cmd /k "cd frontend && npm run dev"

echo Starting... the dashboard opens in your browser in a few seconds.
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
