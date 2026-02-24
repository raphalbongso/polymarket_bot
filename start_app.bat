@echo off
title Polymarket Bot
color 0B

echo.
echo   ========================================
echo          POLYMARKET BOT - Starting...
echo   ========================================
echo.

cd /d "%~dp0"

:: Check of Python beschikbaar is
python --version >nul 2>&1
if errorlevel 1 (
    echo   [FOUT] Python is niet gevonden!
    echo   Download Python 3.11+ van https://python.org
    echo   Vink "Add to PATH" aan tijdens installatie.
    echo.
    pause
    exit /b 1
)

:: Activeer venv als die bestaat
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo   [OK] Virtual environment geactiveerd
) else (
    echo   [INFO] Geen venv gevonden, gebruik systeem Python
)

:: Check of dependencies geinstalleerd zijn
python -c "import numpy" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] Dependencies installeren...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo   [FOUT] Dependencies installatie mislukt!
        pause
        exit /b 1
    )
)

:: Check of pywebview geinstalleerd is
python -c "import webview" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] pywebview installeren voor native venster...
    pip install pywebview
)

echo   [OK] Bot wordt gestart...
echo.

:: Start de echte bot op de achtergrond
start /B python scripts/run_bot.py
timeout /t 5 /nobreak >nul

:: Start het dashboard
echo   [OK] Dashboard openen...
python app/desktop_app.py

:: Als het dashboard sluit, stop ook de bot
echo.
echo   Dashboard gesloten. Bot wordt gestopt...
taskkill /F /IM python.exe >nul 2>&1
echo   Bot gestopt.
pause
