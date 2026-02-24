@echo off
title Polymarket Bot - Installatie
color 0A

echo.
echo   ========================================
echo     POLYMARKET BOT - INSTALLATIE
echo   ========================================
echo.
echo   Dit script doet het volgende:
echo     1. Checkt of Python geinstalleerd is
echo     2. Maakt een virtual environment aan
echo     3. Installeert alle dependencies
echo     4. Maakt een snelkoppeling op je bureaublad
echo.
echo   Druk op een toets om te beginnen...
pause >nul

cd /d "%~dp0"

:: ─── Stap 1: Python check ───
echo.
echo   [1/4] Python checken...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [FOUT] Python is niet gevonden!
    echo.
    echo   Wat je moet doen:
    echo     1. Ga naar https://python.org/downloads
    echo     2. Download Python 3.11 of nieuwer
    echo     3. BELANGRIJK: Vink "Add Python to PATH" aan!
    echo     4. Installeer en run dit script opnieuw
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo   [OK] %%i gevonden

:: ─── Stap 2: Virtual environment ───
echo.
echo   [2/4] Virtual environment aanmaken...
if exist "venv" (
    echo   [OK] venv bestaat al
) else (
    python -m venv venv
    if errorlevel 1 (
        echo   [FOUT] Kan venv niet aanmaken
        pause
        exit /b 1
    )
    echo   [OK] venv aangemaakt
)

:: Activeer venv
call venv\Scripts\activate.bat

:: ─── Stap 3: Dependencies ───
echo.
echo   [3/4] Dependencies installeren (dit kan even duren)...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo   [FOUT] Dependencies installatie mislukt
    pause
    exit /b 1
)

:: pywebview voor native venster
pip install pywebview
echo   [OK] Alle dependencies geinstalleerd

:: ─── Stap 4: Snelkoppeling ───
echo.
echo   [4/4] Snelkoppeling maken op bureaublad...

:: Maak een VBS script dat een snelkoppeling aanmaakt
set SCRIPT="%TEMP%\create_shortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\Polymarket Bot.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%CD%\start_app.bat" >> %SCRIPT%
echo oLink.WorkingDirectory = "%CD%" >> %SCRIPT%
echo oLink.Description = "Polymarket Trading Bot" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%

cscript /nologo %SCRIPT%
del %SCRIPT%
echo   [OK] "Polymarket Bot" snelkoppeling staat op je bureaublad

:: ─── Stap 5: .env check ───
echo.
if not exist ".env" (
    copy .env.template .env >nul
    echo   [INFO] .env bestand aangemaakt van template
    echo   [INFO] Open .env met Kladblok en vul je private key in:
    echo          notepad .env
) else (
    echo   [OK] .env bestand bestaat al
)

:: ─── Stap 6: Tests ───
echo.
echo   Tests draaien om te checken of alles werkt...
python run_tests.py 2>nul | findstr /C:"Ran " /C:"OK" /C:"FAILED"

:: ─── Klaar ───
echo.
echo   ========================================
echo     INSTALLATIE VOLTOOID!
echo   ========================================
echo.
echo   Wat nu:
echo     1. Open .env en vul je Polygon private key in
echo        (notepad .env)
echo     2. Dubbelklik "Polymarket Bot" op je bureaublad
echo     3. Of run: start_app.bat
echo.
echo   De app start standaard in DRY RUN modus
echo   (geen echt geld) zodat je veilig kunt testen.
echo.
pause
