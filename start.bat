@echo off
echo ================================================
echo   LyricTranslate AI — Starting development servers
echo ================================================
echo.

:: Check if .env exists
if not exist backend\.env (
    echo [!] backend\.env not found — copying from .env.example
    copy backend\.env.example backend\.env >nul
    echo [!] Please edit backend\.env and add your ANTHROPIC_API_KEY, then re-run this script.
    pause
    exit /b 1
)

:: Start backend in a new window
echo [1/2] Starting FastAPI backend on http://localhost:8000 ...
start "LyricTranslate Backend" cmd /k "cd backend && (if exist venv\Scripts\python.exe (venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload) else (python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload))"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend in a new window
echo [2/2] Starting Vite frontend on http://localhost:5173 ...
start "LyricTranslate Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ✅ Both servers starting in separate windows.
echo    Open http://localhost:5173 in your browser.
echo.
pause
