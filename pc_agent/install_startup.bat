@echo off
title Встановлення Rony PC Agent у Автозавантаження Windows
chcp 65001 > NUL
cd /d "%~dp0"

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_VBS=%STARTUP_FOLDER%\RonyPCAgent.vbs
set BATCH_PATH=%~dp0run_agent.bat

echo Створення файлу автозапуску у Startup...

echo Set WshShell = CreateObject("WScript.Shell") > "%SHORTCUT_VBS%"
echo WshShell.Run """%BATCH_PATH%""", 0, False >> "%SHORTCUT_VBS%"

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RonyPCAgent" /t REG_SZ /d "wscript.exe \"%SHORTCUT_VBS%\"" /f >nul 2>&1

echo.
echo =======================================================
echo ✅ Агент успішно додано до Автозавантаження Windows!
echo.
echo Тепер при кожному ввімкненні ПК:
echo 1. Агент автоматично запускатиметься у фоні.
echo 2. У Телеграм прийде сповіщення "🟢 ПК онлайн!".
echo 3. Всі кнопки у Телеграм боті працюватимуть миттєво!
echo =======================================================
echo.

wscript.exe "%SHORTCUT_VBS%"

pause