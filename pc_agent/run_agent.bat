@echo off
title Rony PC Local Agent
chcp 65001 > NUL
cd /d "%~dp0"

echo ========================================================
echo STARTING RONY PC TELEGRAM CONTROL AGENT
echo ========================================================

python agent.py

pause