#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ RONY AGENT DIAGNOSTICS ⚡
Запусти цей файл щоб зрозуміти чому агент не виконує команди.
"""

import sys
import os
import subprocess
import time

print("=" * 60)
print("⚡ RONY AGENT DIAGNOSTICS ⚡")
print("=" * 60)

# ── 1. Python версія
print(f"\n[1] Python: {sys.version}")
print(f"    Шлях: {sys.executable}")

# ── 2. Перевірка пакетів
print("\n[2] Перевірка залежностей...")
packages = {
    'requests': 'requests',
    'psutil': 'psutil',
    'PIL': 'Pillow',
    'mss': 'mss',
    'win32com': 'pywin32',
    'win32gui': 'pywin32',
    'win32ui': 'pywin32',
    'pycaw': 'pycaw',
    'comtypes': 'comtypes',
}
missing = []
for mod, pip in packages.items():
    try:
        __import__(mod)
        print(f"    OK  {mod} ({pip})")
    except ImportError:
        print(f"    MISSING  {mod} ({pip})")
        missing.append(pip)

if missing:
    print(f"\n    Installing: {', '.join(set(missing))}")
    for pkg in set(missing):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            print(f"    OK installed {pkg}")
        except Exception as e:
            print(f"    FAILED {pkg}: {e}")
else:
    print("    All packages OK!")

# ── 3. Server connectivity
print("\n[3] Testing server connection...")
SERVER_URL = "https://rony-telegram-bot.onrender.com/"
try:
    import requests
    r = requests.get(SERVER_URL, timeout=15)
    print(f"    OK HTTP {r.status_code}")
except requests.exceptions.Timeout:
    print("    TIMEOUT - Render is sleeping! Wait 30s and try again.")
except Exception as e:
    print(f"    ERROR: {e}")

# ── 4. Agent poll test
print("\n[4] Testing agent_poll...")
PC_ID = "pc_default"
PC_NAME = "Rony PC"
try:
    from urllib.parse import quote
    r = requests.get(f"{SERVER_URL}?agent_poll=1&pc_id={quote(PC_ID)}&pc_name={quote(PC_NAME)}", timeout=15)
    print(f"    HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        cmds = data.get('commands', [])
        print(f"    OK Poll works! Commands in queue: {len(cmds)}")
        if cmds:
            print(f"    First cmd: {cmds[0]}")
    else:
        print(f"    ERROR: {r.text[:300]}")
except Exception as e:
    print(f"    ERROR: {e}")

# ── 5. Is agent running?
print("\n[5] Is agent.py running?...")
try:
    import psutil
    agent_procs = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = ' '.join(p.info['cmdline'] or []).lower()
            if 'agent.py' in cmd and p.pid != os.getpid():
                agent_procs.append(p)
        except Exception:
            pass
    if agent_procs:
        print(f"    OK Agent running! PIDs: {[p.pid for p in agent_procs]}")
    else:
        print("    AGENT NOT RUNNING!")
        print("    -> Run install_startup.bat as Administrator")
except Exception as e:
    print(f"    ERROR: {e}")

# ── 6. Autostart check
print("\n[6] Checking autostart...")
startup_vbs = os.path.join(os.environ.get('APPDATA', ''), 
    r"Microsoft\Windows\Start Menu\Programs\Startup\RonyPCAgent.vbs")
if os.path.exists(startup_vbs):
    print(f"    OK VBS autostart found")
else:
    print(f"    MISSING VBS autostart!")

try:
    result = subprocess.run(
        ['reg', 'query', r'HKCU\Software\Microsoft\Windows\CurrentVersion\Run', '/v', 'RonyPCAgent'],
        capture_output=True, text=True
    )
    if 'RonyPCAgent' in result.stdout:
        print(f"    OK Registry autorun found")
    else:
        print(f"    MISSING Registry autorun!")
except Exception:
    pass

# ── 7. Send online notification
print("\n[7] Sending online notification to server...")
try:
    r = requests.get(
        f"{SERVER_URL}?agent_online=1&pc_id={quote(PC_ID)}&pc_name={quote(PC_NAME)}",
        timeout=10
    )
    print(f"    HTTP {r.status_code}: {r.text[:100]}")
    if r.status_code == 200:
        print("    Check Telegram - you should see 'PC online' message!")
except Exception as e:
    print(f"    ERROR: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTICS DONE")
print("=" * 60)
input("\nPress Enter to close...")
