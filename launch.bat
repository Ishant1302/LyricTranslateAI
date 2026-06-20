@echo off
title LyricTranslate AI — Launcher (Java Backend)

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       LyricTranslate AI  🎶              ║
echo  ║     Spring Boot + Vite  Launcher         ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── Build the Java backend (if not already built) ─────────────────────────────
echo [1/3] Building Java backend (Maven)...
if not exist "%~dp0backend\target\lyrictranslate-ai-1.0.0.jar" (
    cd /d "%~dp0backend"
    call apache-maven-3.9.9\bin\mvn.cmd clean package -q -DskipTests
    if errorlevel 1 (
        echo [ERROR] Maven build failed. Make sure Java 17+ is installed.
        pause
        exit /b 1
    )
    echo [OK] Build successful.
) else (
    echo [OK] JAR already exists — skipping build. Delete target\ folder to force rebuild.
)

:: ── Start Spring Boot backend ─────────────────────────────────────────────────
echo [2/3] Starting Spring Boot backend on http://localhost:8000 ...
start "LyricTranslate — Backend (Java)" cmd /k "cd /d %~dp0backend && java -jar target\lyrictranslate-ai-1.0.0.jar"

:: ── Start Vite frontend ───────────────────────────────────────────────────────
echo [3/3] Starting Vite frontend on http://localhost:5173 ...
start "LyricTranslate — Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: ── Wait for servers then open browser ────────────────────────────────────────
echo.
echo  Waiting for servers to start...
timeout /t 6 /nobreak >nul

echo  Opening browser at http://localhost:5173 ...
start "" "http://localhost:5173"

echo.
echo  Done! Both server windows are open.
echo  Close those windows to stop the servers.
echo.
exit
