@echo off
chcp 65001 >NUL
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$vbs = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name RonyPCAgent -ErrorAction SilentlyContinue)?.RonyPCAgent; if ($vbs) { Start-Process wscript.exe -ArgumentList $vbs.Replace('wscript.exe ',''); Write-Host 'Агент запущено!' } else { Write-Host 'Спочатку запусти install_startup.bat!' }"
timeout /t 3 >NUL
