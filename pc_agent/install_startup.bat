@echo off
chcp 65001 >NUL
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_agent.ps1"