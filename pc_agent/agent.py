import time
import os
import sys
import subprocess
import re
import json

# Ensure stdout and stderr handle UTF-8 encoding on Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
        sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass

# Auto-install required dependencies if missing
required_packages = {
    'requests': 'requests',
    'psutil': 'psutil',
    'PIL': 'Pillow'
}

for module_name, pip_name in required_packages.items():
    try:
        __import__(module_name)
    except ImportError:
        print(f"[*] Installing missing package: {pip_name}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        except Exception as e:
            print(f"[-] Failed to install {pip_name}: {e}")

import requests
import psutil
import datetime
import ctypes
import glob
from ctypes import wintypes
from PIL import ImageGrab

# SERVER URL ON HOSTING (driver.lutsk.ua / Render)
SERVER_URL = "https://rony-telegram-bot.onrender.com/"

# ---- MULTI-PC CONFIGURATION ----
PC_ID = "pc_default"
PC_NAME = "Rony PC"

# Audio output devices via pycaw + PolicyConfig
def _ensure_audio_deps():
    for module_name, pip_name in (("pycaw", "pycaw"), ("comtypes", "comtypes")):
        try:
            __import__(module_name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

def _get_policy_config():
    import comtypes
    from comtypes import GUID, COMMETHOD, HRESULT, CLSCTX_ALL, CoCreateInstance
    from ctypes import c_int, c_longlong, POINTER
    from ctypes.wintypes import LPCWSTR

    class IPolicyConfig(comtypes.IUnknown):
        _case_insensitive_ = True
        _iid_ = GUID("{F8679F50-850A-41CF-9C72-430F290290C8}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetMixFormat", (["in"], LPCWSTR, "pszDeviceName"), (["out"], POINTER(c_int), "ppFormat")),
            COMMETHOD([], HRESULT, "SetDefaultEndpoint", (["in"], LPCWSTR, "wszDeviceId"), (["in"], c_int, "role")),
        ]

    CLSID_PolicyConfigClient = GUID("{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}")
    return CoCreateInstance(CLSID_PolicyConfigClient, IPolicyConfig, CLSCTX_ALL)

def _is_render_device(device_id):
    return bool(device_id) and str(device_id).startswith("{0.0.0.")

def get_audio_devices():
    _ensure_audio_deps()
    try:
        from pycaw.pycaw import AudioUtilities
        default_id = getattr(AudioUtilities.GetSpeakers(), "id", None)
        devices = []
        for dev in AudioUtilities.GetAllDevices():
            try:
                name, devid, state = dev.FriendlyName, dev.id, dev.state
                if not name or not devid or not _is_render_device(str(devid)): continue
                devices.append({"index": len(devices), "name": str(name).strip(), "id": str(devid), "is_default": str(devid) == str(default_id)})
            except: continue
        return devices
    except: return []

def set_audio_device(device_index=None, device_id=None):
    _ensure_audio_deps()
    devices = get_audio_devices()
    target_id = device_id
    if not target_id and device_index is not None:
        idx = int(device_index)
        if 0 <= idx < len(devices): target_id = devices[idx].get("id")
    if target_id:
        try:
            policy = _get_policy_config()
            for role in (0, 1, 2): policy.SetDefaultEndpoint(str(target_id), role)
        except: pass
    return get_audio_devices()

# Windows Virtual Key Codes
VK_CONTROL, VK_SHIFT, VK_TAB, VK_RETURN, VK_ESCAPE, VK_LEFT, VK_RIGHT, VK_F, VK_L, VK_T, VK_W, VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP, VK_MEDIA_NEXT_TRACK, VK_MEDIA_PREV_TRACK, VK_MEDIA_PLAY_PAUSE = 0x11, 0x10, 0x09, 0x0D, 0x1B, 0x25, 0x27, 0x46, 0x4C, 0x54, 0x57, 0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB3
KEYEVENTF_KEYUP = 0x0002
user32 = ctypes.windll.user32

BROWSER_PROCESS_NAMES = {'chrome.exe', 'msedge.exe', 'brave.exe', 'opera.exe', 'firefox.exe', 'chromium.exe'}
APP_WINDOW_HINTS = {'browser': ['chrome', 'msedge', 'brave', 'opera'], 'telegram': ['telegram'], 'discord': ['discord'], 'steam': ['steam'], 'ytmusic': ['youtube music']}

def press_key(vk_code):
    scan_code = user32.MapVirtualKeyW(vk_code, 0)
    user32.keybd_event(vk_code, scan_code, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(vk_code, scan_code, KEYEVENTF_KEYUP, 0)

def press_hotkey(*vk_codes):
    for vk in vk_codes:
        scan_code = user32.MapVirtualKeyW(vk, 0)
        user32.keybd_event(vk, scan_code, 0, 0)
    time.sleep(0.03)
    for vk in reversed(vk_codes):
        scan_code = user32.MapVirtualKeyW(vk, 0)
        user32.keybd_event(vk, scan_code, KEYEVENTF_KEYUP, 0)

def type_text(text):
    import pyperclip
    pyperclip.copy(text)
    press_hotkey(VK_CONTROL, 0x56) # Ctrl+V

def enum_windows():
    results = []
    def callback(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            results.append((hwnd, title.value, pid.value))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(callback), 0)
    return results

def get_process_name(pid):
    try: return psutil.Process(pid).name().lower()
    except: return ""

def force_foreground(hwnd):
    user32.SetForegroundWindow(hwnd)
    return True

def find_window_by_hints(hints=None, process_names=None):
    hints_l = [h.lower() for h in (hints or [])]
    p_names = {p.lower() for p in (process_names or [])}
    for hwnd, title, pid in enum_windows():
        title_l = title.lower()
        pname = get_process_name(pid)
        if 'telegram' in hints_l and pname == 'telegram.exe': return hwnd, title, pname
        if pname in p_names or any(h in title_l for h in hints_l): return hwnd, title, pname
    return None, None, None

def find_browser_window():
    for hwnd, title, pid in enum_windows():
        if get_process_name(pid) in BROWSER_PROCESS_NAMES: return (hwnd, title, get_process_name(pid))
    return (None, None, None)

def focus_browser():
    hwnd, title, pname = find_browser_window()
    if hwnd: return force_foreground(hwnd)
    return False

def open_in_browser(url):
    os.system(f'start "" "{url}"')
    return "Браузер (за замовчуванням)"

def focus_or_open_app(app, yt_url=None):
    if app == 'ytmusic':
        if focus_browser():
            press_hotkey(VK_CONTROL, VK_T)
            time.sleep(0.2)
            type_text(yt_url or 'https://music.youtube.com')
            press_key(VK_RETURN)
            return
        open_in_browser(yt_url or 'https://music.youtube.com')
        return
    if app == 'browser':
        hwnd, _, _ = find_browser_window()
        if hwnd: force_foreground(hwnd)
        else: open_in_browser("https://google.com")
        return
    if app == 'telegram':
        hwnd, _, _ = find_window_by_hints(process_names=['telegram.exe'])
        if hwnd: force_foreground(hwnd)
        else: os.system("start telegram")
        return

def browser_tab_action(action):
    focus_browser()
    time.sleep(0.1)
    if action == 'new': press_hotkey(VK_CONTROL, VK_T)
    elif action == 'close': press_hotkey(VK_CONTROL, VK_W)
    elif action == 'next': press_hotkey(VK_CONTROL, VK_TAB)

def browser_search(query):
    focus_browser()
    press_hotkey(VK_CONTROL, VK_T)
    time.sleep(0.3)
    type_text(f"https://www.google.com/search?q={query}")
    press_key(VK_RETURN)

def handle_command(cmd_item):
    cmd = cmd_item.get('command')
    params = cmd_item.get('params', {})
    if cmd == 'open_app': focus_or_open_app(params.get('app'), params.get('yt_url'))
    elif cmd == 'browser_tab': browser_tab_action(params.get('action'))
    elif cmd == 'browser_search': browser_search(params.get('query'))
    elif cmd == 'msg': subprocess.run(f'msg * "{params.get("text")}"', shell=True)

def main():
    while True:
        try:
            r = requests.get(f"{SERVER_URL}?agent_poll=1&pc_id={PC_ID}", timeout=10)
            if r.status_code == 200:
                for cmd in r.json().get('commands', []): handle_command(cmd)
        except: pass
        time.sleep(0.5)

if __name__ == '__main__': main()