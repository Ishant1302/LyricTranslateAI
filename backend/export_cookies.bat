@echo off
echo ================================================
echo   LyricTranslate AI — Export YouTube Cookies
echo ================================================
echo.
echo This will export your YouTube cookies from Chrome.
echo IMPORTANT: Close all Chrome windows first, then press any key.
echo.
pause

echo Exporting cookies from Chrome...
.\venv\Scripts\python.exe -m yt_dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1

if exist cookies.txt (
    echo.
    echo [OK] cookies.txt created successfully!
    echo      YouTube links will now work in LyricTranslate AI.
) else (
    echo.
    echo [!] Failed to export cookies from Chrome.
    echo     Try closing ALL Chrome windows and run this again.
)
echo.
pause
