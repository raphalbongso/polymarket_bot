@echo off
title Polymarket Bot - Selenium
cd /d C:\Users\rapha\polymarket_bot

echo.
echo   ========================================
echo     POLYMARKET BOT - Selenium Mode
echo   ========================================
echo.
echo   Chrome opruimen...
taskkill /IM chromedriver.exe /F >nul 2>&1
taskkill /IM chrome.exe /F >nul 2>&1
del /f "chrome_profile_bot\lockfile" >nul 2>&1
timeout /t 2 /nobreak >nul

echo   Bot starten...
echo   Logs: bot_output.log
echo.
powershell -Command "python scripts\run_bot.py 2>&1 | Tee-Object -FilePath bot_output.log"
pause
