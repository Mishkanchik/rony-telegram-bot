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

def take_screenshot():
    try:
        shot_path = os.path.join(os.path.dirname(__file__), 'screenshot_temp.png')
        img = ImageGrab.grab()
        img.save(shot_path)
        return shot_path
    except Exception as e:
        print(f"[-] Error taking screenshot: {e}")
        return None

def get_system_status():
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        uptime_seconds = int(time.time() - psutil.boot_time())
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        
        status_text = (
            f"📊 *СТАН ПК ({PC_NAME})*\n"
            f"───────────────────────────\n"
            f"💻 *Завантаження ЦП:* `{cpu}%` \n"
            f"🧠 *ОЗУ:* `{ram.percent}%` ({round(ram.used / (1024**3), 1)}GB / {round(ram.total / (1024**3), 1)}GB)\n"
            f"💾 *Диск C:* `{disk.percent}%` ({round(disk.free / (1024**3), 1)}GB вільно)\n"
            f"⏱️ *Час роботи:* `{hours}г {minutes}хв`\n"
            f"───────────────────────────"
        )
        return status_text
    except Exception as e:
        return f"📊 *СТАН ПК:* Помилка отримання даних: {e}"

def get_running_processes():
    procs = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            name = p.info['name']
            if not name: continue
            pid = p.info['pid']
            procs.append({'pid': pid, 'name': name, 'title': name})
        except: pass
    return sorted(procs, key=lambda x: x['name'].lower())

def media_control(action):
    if action == 'play' or action == 'music_play': press_key(VK_MEDIA_PLAY_PAUSE)
    elif action == 'prev' or action == 'music_prev': press_key(VK_MEDIA_PREV_TRACK)
    elif action == 'next' or action == 'music_next': press_key(VK_MEDIA_NEXT_TRACK)
    elif action == 'vup': press_key(VK_VOLUME_UP)
    elif action == 'vdown': press_key(VK_VOLUME_DOWN)
    elif action == 'mute': press_key(VK_VOLUME_MUTE)
    elif action == 'fullscreen': press_key(VK_F)
    elif action == 'rewind': press_key(VK_LEFT)
    elif action == 'forward': press_key(VK_RIGHT)
    elif action == 'scroll_up': press_key(0x26) # Up arrow
    elif action == 'scroll_down': press_key(0x28) # Down arrow

def send_result_to_server(chat_id, text=None, result_type=None, shot_path=None, extra_params=None):
    try:
        data = {
            'agent_result': '1',
            'pc_id': PC_ID,
            'chat_id': chat_id
        }
        if text: data['text'] = text
        if result_type: data['type'] = result_type
        if extra_params: data.update(extra_params)

        files = {}
        if shot_path and os.path.exists(shot_path):
            files['screenshot'] = open(shot_path, 'rb')

        requests.post(SERVER_URL, data=data, files=files if files else None, timeout=15)

        if files:
            files['screenshot'].close()
            try: os.remove(shot_path)
            except: pass
    except Exception as e:
        print(f"[-] Error sending result to server: {e}")

def handle_command(cmd_item):
    cmd = cmd_item.get('command')
    chat_id = cmd_item.get('chat_id')
    params = cmd_item.get('params', {})
    print(f"[*] Processing command: {cmd} with params: {params}")

    if cmd == 'open_app':
        focus_or_open_app(params.get('app'), params.get('yt_url'))
    elif cmd == 'browser_tab':
        browser_tab_action(params.get('action'))
    elif cmd == 'browser_search':
        browser_search(params.get('query'))
    elif cmd == 'screenshot':
        shot_path = take_screenshot()
        send_result_to_server(chat_id, shot_path=shot_path, extra_params={'msg_id': params.get('msg_id')})
    elif cmd == 'status':
        status_text = get_system_status()
        send_result_to_server(chat_id, text=status_text)
    elif cmd == 'get_processes':
        procs = get_running_processes()
        send_result_to_server(chat_id, result_type='processes', extra_params={
            'procs_json': json.dumps(procs),
            'page': params.get('page', 1),
            'msg_id': params.get('msg_id')
        })
    elif cmd == 'kill_app':
        pid = params.get('pid')
        target = params.get('target')
        if pid:
            try: psutil.Process(pid).kill()
            except: pass
        elif target:
            os.system(f'taskkill /F /IM "{target}*" /T')
        # Send updated processes back
        procs = get_running_processes()
        send_result_to_server(chat_id, result_type='processes', extra_params={
            'procs_json': json.dumps(procs),
            'page': params.get('page', 1),
            'msg_id': params.get('msg_id')
        })
    elif cmd == 'media':
        media_control(params.get('action'))
    elif cmd == 'get_audio_devices':
        devices = get_audio_devices()
        send_result_to_server(chat_id, result_type='audio_devices', extra_params={
            'audio_devices_json': json.dumps(devices),
            'msg_id': params.get('msg_id')
        })
    elif cmd == 'set_audio_device':
        devices = set_audio_device(device_index=params.get('device_index'))
        send_result_to_server(chat_id, result_type='audio_devices', extra_params={
            'audio_devices_json': json.dumps(devices),
            'msg_id': params.get('msg_id')
        })
    elif cmd == 'shutdown':
        os.system('shutdown /s /t 5')
    elif cmd == 'sleep':
        os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
    elif cmd == 'reboot':
        os.system('shutdown /r /t 5')
    elif cmd == 'lock':
        ctypes.windll.user32.LockWorkStation()
    elif cmd == 'cmd':
        subprocess.run(params.get('command'), shell=True)
    elif cmd == 'msg':
        subprocess.run(f'msg * "{params.get("text")}"', shell=True)

def main():
    while True:
        try:
            r = requests.get(f"{SERVER_URL}?agent_poll=1&pc_id={PC_ID}", timeout=10)
            if r.status_code == 200:
                for cmd in r.json().get('commands', []): handle_command(cmd)
        except: pass
        time.sleep(0.5)

if __name__ == '__main__': main()