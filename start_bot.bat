@echo off
title Polymarket Bot - Selenium
cd /d C:\Users\rapha\polymarket_bot

echo.
echo   ========================================
echo     POLYMARKET BOT - Selenium Mode
echo   ========================================
echo.
echo   Oude processen opruimen...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5555.*LISTENING"') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8050.*LISTENING"') do taskkill /PID %%a /F >nul 2>&1
taskkill /IM chromedriver.exe /F >nul 2>&1
taskkill /IM chrome.exe /F >nul 2>&1
del /f "chrome_profile_bot\lockfile" >nul 2>&1
timeout /t 2 /nobreak >nul

echo   Dashboard starten op http://localhost:8050 ...
start /b python -c "from http.server import HTTPServer; from app.dashboard_server import DashboardHandler; HTTPServer(('127.0.0.1', 8050), DashboardHandler).serve_forever()" >nul 2>&1
timeout /t 1 /nobreak >nul
start http://localhost:8050

echo   Bot starten...
echo   Logs: bot_output.log
echo.
powershell -Command "python scripts\run_bot.py 2>&1 | Tee-Object -FilePath bot_output.log"

echo.
echo   Bot gestopt. Dashboard wordt afgesloten...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8050.*LISTENING"') do taskkill /PID %%a /F >nul 2>&1
pause
