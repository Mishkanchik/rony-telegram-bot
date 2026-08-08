@echo off
title 🚀 Встановлення Rony PC Agent у Автозавантаження Windows
chcp 65001 > NUL
cd /d "%~dp0"

echo =======================================================
echo 🚀 ВСТАНОВЛЕННЯ RONY PC AGENT В АВТОЗАВАНТАЖЕННЯ 🚀
echo =======================================================
echo.

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_VBS=%STARTUP_FOLDER%\RonyPCAgent.vbs
set AGENT_PATH=%~dp0agent.py

echo ⚙️ [1/2] Створення файлу автозапуску у Startup...

echo Set WshShell = CreateObject("WScript.Shell") > "%SHORTCUT_VBS%"
echo WshShell.Run "pythonw """"%AGENT_PATH%""""", 0, False >> "%SHORTCUT_VBS%"

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RonyPCAgent" /t REG_SZ /d "wscript.exe \"%SHORTCUT_VBS%\"" /f >nul 2>&1

echo 🟢 [2/2] Запуск агента у фоновому режимі...
wscript.exe "%SHORTCUT_VBS%"

echo.
echo =======================================================
echo ✅ Rony PC Agent успішно встановлено та запущено!
echo.
echo 📌 Тепер при кожному ввімкненні ПК:
echo  1️⃣ Агент автоматично запускатиметься у фоні.
echo  2️⃣ У Телеграм прийде сповіщення "🟢 ПК онлайн!".
echo  3️⃣ Всі кнопки у Телеграм боті працюватимуть миттєво!
echo =======================================================
echo.

pause