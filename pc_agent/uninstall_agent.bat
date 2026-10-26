@echo off
title Uninstall Rony PC Agent
chcp 65001 > NUL
cd /d "%~dp0"

echo ========================================================
echo  REMOVE RONY PC AGENT FROM SYSTEM
echo ========================================================
echo.

echo [1/3] Stopping agent processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%%agent.py%%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [2/3] Removing from autostart (Task Scheduler + VBS + Registry)...

REM Remove Task Scheduler task (primary method)
schtasks /Delete /TN "RonyPCAgent" /F >nul 2>&1
echo    - Task Scheduler: RonyPCAgent removed (if existed)

REM Remove legacy VBS from Startup folder
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
if exist "%STARTUP%\RonyPCAgent.vbs" (
    del /f /q "%STARTUP%\RonyPCAgent.vbs"
    echo    - Removed VBS from Startup folder
)

REM Remove legacy Registry Run key
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RonyPCAgent" /f >nul 2>&1
echo    - Registry Run key removed (if existed)

echo [3/3] Cleaning Python cache...
if exist "__pycache__" (
    rmdir /s /q "__pycache__" >nul 2>&1
)
if exist "rony_task.xml" (
    del /f /q "rony_task.xml" >nul 2>&1
)

echo.
echo ========================================================
echo  Rony PC Agent successfully removed!
echo.
echo  To reinstall: run 'Install Rony Agent'
echo ========================================================
echo.
pause
