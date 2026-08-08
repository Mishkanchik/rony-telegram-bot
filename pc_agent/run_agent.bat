@echo off
title 🚀 Rony PC Local Agent
chcp 65001 > NUL
cd /d "%~dp0"

echo ========================================================
echo 🚀 ЗАПУСК RONY PC LOCAL AGENT...
echo ========================================================
echo.

python agent.py

pause