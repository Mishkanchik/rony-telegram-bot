@echo off
title 🗑️ Видалення Rony PC Agent з ПК
chcp 65001 > NUL
cd /d "%~dp0"

echo ========================================================
echo 🗑️ ПОВНЕ ВИДАЛЕННЯ RONY PC AGENT З СИСТЕМИ 🗑️
echo ========================================================
echo.

echo 🛑 [1/3] Зупинка працюючого агента та процесів Python...
taskkill /F /FI "WINDOWTITLE eq Rony PC Local Agent*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Встановлення Rony PC Agent*" /T >nul 2>&1
wmic process where "commandline like '%%agent.py%%'" call terminate >nul 2>&1

echo ⚙️ [2/3] Видалення з Автозавантаження Windows (Startup & Registry)...
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_VBS=%SHORTCUT_VBS%
set SHORTCUT_VBS=%STARTUP_FOLDER%\RonyPCAgent.vbs

if exist "%SHORTCUT_VBS%" (
    del /f /q "%SHORTCUT_VBS%"
    echo    - Файл %SHORTCUT_VBS% видалено.
)

reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RonyPCAgent" /f >nul 2>&1
echo    - Запис в реєстрі HKCU Run видалено.

echo 🧹 [3/3] Очищення тимчасових кешів Python...
if exist "__pycache__" (
    rmdir /s /q "__pycache__" >nul 2>&1
)

echo.
echo ========================================================
echo ✅ Rony PC Agent повністю видалено з системи!
echo.
echo 📌 Якщо знадобиться знову:
echo  👉 Запустіть "Install Rony Agent" для встановлення агента.
echo ========================================================
echo.

pause