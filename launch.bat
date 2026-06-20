@echo off
title LyricTranslate AI — Launcher

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       LyricTranslate AI  🎶              ║
echo  ║       Starting servers...                ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── Check .env exists ────────────────────────────────────────────────────────
if not exist "%~dp0backend\.env" (
    echo [!] backend\.env not found — copying from .env.example
    copy "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
    echo [!] Please edit backend\.env and add your ANTHROPIC_API_KEY, then re-run.
    pause
    exit /b 1
)

:: ── Start FastAPI backend ─────────────────────────────────────────────────────
echo [1/2] Starting FastAPI backend on http://localhost:8000 ...
if exist "%~dp0backend\venv\Scripts\python.exe" (
    start "LyricTranslate — Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
) else (
    start "LyricTranslate — Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
)

:: ── Start Vite frontend ───────────────────────────────────────────────────────
echo [2/2] Starting Vite frontend on http://localhost:5173 ...
start "LyricTranslate — Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: ── Wait a few seconds for servers to boot, then open browser ─────────────────
echo.
echo  Waiting for servers to start...
timeout /t 4 /nobreak >nul

echo  Opening browser at http://localhost:5173 ...
start "" "http://localhost:5173"

echo.
echo  ✅ Done! Both server windows are open.
echo     Close those windows to stop the servers.
echo.
exit
