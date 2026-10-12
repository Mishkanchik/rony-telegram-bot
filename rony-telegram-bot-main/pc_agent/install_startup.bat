@echo off
chcp 65001 > NUL
title Rony PC Agent - Install Startup
cd /d "%~dp0"

echo =======================================================
echo    VSTANOVLENNYA RONY PC AGENT V AVTOZAVANTAZHENNYA
echo =======================================================
echo.

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_VBS=%STARTUP_FOLDER%\RonyPCAgent.vbs
set AGENT_PATH=%~dp0agent.py

echo [1/3] Poshuk Python...

set PYTHONW_CMD=
for /f "delims=" %%I in ('where pythonw 2^>nul') do (
    if not defined PYTHONW_CMD set PYTHONW_CMD=%%I
)
if not defined PYTHONW_CMD (
    for /f "delims=" %%I in ('where python 2^>nul') do (
        if not defined PYTHONW_CMD set PYTHONW_CMD=%%~dpIpythonw.exe
    )
)
if not defined PYTHONW_CMD (
    if exist "C:\Program Files\Python313\pythonw.exe" set PYTHONW_CMD=C:\Program Files\Python313\pythonw.exe
)
if not defined PYTHONW_CMD (
    if exist "C:\Program Files\Python312\pythonw.exe" set PYTHONW_CMD=C:\Program Files\Python312\pythonw.exe
)
if not defined PYTHONW_CMD (
    if exist "C:\Program Files\Python311\pythonw.exe" set PYTHONW_CMD=C:\Program Files\Python311\pythonw.exe
)

if not defined PYTHONW_CMD (
    echo [ERROR] Python ne znajdeno! Vstanovit Python z python.org
    pause
    exit /b 1
)

echo [OK] Python znajdeno: %PYTHONW_CMD%
echo.

echo [2/3] Stvorennya VBS-avtozapusku...

(
echo Set WshShell = CreateObject("WScript.Shell"^)
echo WshShell.Run Chr(34^) ^& "%PYTHONW_CMD%" ^& Chr(34^) ^& " " ^& Chr(34^) ^& "%AGENT_PATH%" ^& Chr(34^), 0, False
) > "%SHORTCUT_VBS%"

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RonyPCAgent" /t REG_SZ /d "wscript.exe \"%SHORTCUT_VBS%\"" /f >nul 2>&1

echo [3/3] Zapusk agenta u fonovomu rezhymi...
wscript.exe "%SHORTCUT_VBS%"

echo.
echo =======================================================
echo    Rony PC Agent uspishno vstanovleno ta zapushcheno!
echo =======================================================
echo.
echo  - Agent avtozapuskatymetsia pry kozhnomy vvimknanni PK
echo  - Perevirit Telegram - bot povynen buly onlain
echo =======================================================
echo.

pause