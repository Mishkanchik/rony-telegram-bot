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
# Change these values for each PC that runs this agent
PC_ID = "pc_default"
PC_NAME = "Rony PC"


# Audio output devices via pycaw + PolicyConfig (no PowerShell COM)
def _ensure_audio_deps():
    for module_name, pip_name in (("pycaw", "pycaw"), ("comtypes", "comtypes")):
        try:
            __import__(module_name)
        except ImportError:
            print(f"[*] Installing missing package: {pip_name}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            except Exception as e:
                print(f"[-] Failed to install {pip_name}: {e}")

def _get_policy_config():
    import comtypes
    from comtypes import GUID, COMMETHOD, HRESULT, CLSCTX_ALL, CoCreateInstance
    from ctypes import c_int, c_longlong, POINTER
    from ctypes.wintypes import LPCWSTR

    class IPolicyConfig(comtypes.IUnknown):
        _case_insensitive_ = True
        _iid_ = GUID("{F8679F50-850A-41CF-9C72-430F290290C8}")
        _idlflags_ = []
        _methods_ = [
            COMMETHOD([], HRESULT, "GetMixFormat",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["out"], POINTER(c_int), "ppFormat")),
            COMMETHOD([], HRESULT, "GetDeviceFormat",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["in"], c_int, "bDefault"),
                      (["out"], POINTER(c_int), "ppFormat")),
            COMMETHOD([], HRESULT, "ResetDeviceFormat",
                      (["in"], LPCWSTR, "pszDeviceName")),
            COMMETHOD([], HRESULT, "SetDeviceFormat",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["in"], c_int, "pEndpointFormat"),
                      (["in"], c_int, "mixFormat")),
            COMMETHOD([], HRESULT, "GetProcessingPeriod",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["in"], c_int, "bDefault"),
                      (["out"], POINTER(c_longlong), "pmftDefaultPeriod"),
                      (["out"], POINTER(c_longlong), "pmftMinimumPeriod")),
            COMMETHOD([], HRESULT, "SetProcessingPeriod",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["in"], POINTER(c_longlong), "pmftPeriod")),
            COMMETHOD([], HRESULT, "GetShareMode",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["out"], POINTER(c_int), "pMode")),
            COMMETHOD([], HRESULT, "SetShareMode",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["in"], c_int, "mode")),
            COMMETHOD([], HRESULT, "GetPropertyValue",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["in"], c_int, "key"),
                      (["out"], POINTER(c_int), "pv")),
            COMMETHOD([], HRESULT, "SetPropertyValue",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["in"], c_int, "key"),
                      (["in"], c_int, "pv")),
            COMMETHOD([], HRESULT, "SetDefaultEndpoint",
                      (["in"], LPCWSTR, "wszDeviceId"),
                      (["in"], c_int, "role")),
            COMMETHOD([], HRESULT, "SetEndpointVisibility",
                      (["in"], LPCWSTR, "pszDeviceName"),
                      (["in"], c_int, "bVisible")),
        ]

    CLSID_PolicyConfigClient = GUID("{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}")
    return CoCreateInstance(CLSID_PolicyConfigClient, IPolicyConfig, CLSCTX_ALL)

def _is_render_device(device_id):
    # Render/playback endpoints use data-flow prefix {0.0.0.
    return bool(device_id) and str(device_id).startswith("{0.0.0.")

def get_audio_devices():
    _ensure_audio_deps()
    try:
        from pycaw.pycaw import AudioUtilities
        import warnings

        default_id = None
        try:
            speakers = AudioUtilities.GetSpeakers()
            default_id = getattr(speakers, "id", None)
        except Exception:
            default_id = None

        devices = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            all_devs = AudioUtilities.GetAllDevices()

        for dev in all_devs:
            try:
                name = getattr(dev, "FriendlyName", None)
                devid = getattr(dev, "id", None)
                state = getattr(dev, "state", None)
                if not name or not devid:
                    continue
                if not _is_render_device(str(devid)):
                    continue
                state_name = str(state).replace("AudioDeviceState.", "") if state is not None else "Unknown"
                # Show active/unplugged playback devices only
                if state_name not in ("Active", "Unplugged"):
                    continue
                devices.append({
                    "index": len(devices),
                    "name": str(name).strip(),
                    "id": str(devid),
                    "is_default": bool(default_id and str(devid) == str(default_id)),
                    "status": state_name,
                })
            except Exception:
                continue
        return devices
    except Exception as e:
        print(f"[-] get_audio_devices error: {e}")
        return []

def set_audio_device(device_index=None, device_id=None):
    _ensure_audio_deps()
    devices = get_audio_devices()
    target_id = device_id
    if target_id is None and device_index is not None:
        try:
            idx = int(device_index)
            if 0 <= idx < len(devices):
                target_id = devices[idx].get("id")
        except Exception:
            target_id = None

    if not target_id:
        print("[-] No audio device target provided")
        return devices

    try:
        policy = _get_policy_config()
        # 0=eConsole, 1=eMultimedia, 2=eCommunications
        for role in (0, 1, 2):
            policy.SetDefaultEndpoint(str(target_id), role)
        time.sleep(0.25)
        print(f"[+] Default audio output set to: {target_id}")
    except Exception as e:
        print(f"[-] set_audio_device error: {e}")

    return get_audio_devices()

# Windows Virtual Key Codes & Flags
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_T = 0x54
VK_W = 0x57
VK_L = 0x4C
VK_F = 0x46
VK_J = 0x4A
VK_K = 0x4B
VK_SPACE = 0x20
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Browser process names (Comet is Chromium-based)
BROWSER_PROCESS_NAMES = {
    'comet.exe', 'chrome.exe', 'msedge.exe', 'brave.exe',
    'opera.exe', 'firefox.exe', 'chromium.exe'
}

APP_WINDOW_HINTS = {
    'comet': ['comet', 'chrome'],
    'discord': ['discord'],
    'steam': ['steam'],
    'chrome': ['chrome', 'google chrome'],
    'ytmusic': ['youtube music', 'music.youtube', 'comet', 'chrome'],
}

def press_key(vk_code, extended=True):
    try:
        scan_code = user32.MapVirtualKeyW(vk_code, 0)
        flags = KEYEVENTF_EXTENDEDKEY if extended else 0
        user32.keybd_event(vk_code, scan_code, flags, 0)
        time.sleep(0.02)
        user32.keybd_event(vk_code, scan_code, flags | KEYEVENTF_KEYUP, 0)
    except Exception as e:
        print(f"[-] Key press error: {e}")

def key_down(vk_code):
    scan_code = user32.MapVirtualKeyW(vk_code, 0)
    user32.keybd_event(vk_code, scan_code, 0, 0)

def key_up(vk_code):
    scan_code = user32.MapVirtualKeyW(vk_code, 0)
    user32.keybd_event(vk_code, scan_code, KEYEVENTF_KEYUP, 0)

def press_hotkey(*vk_codes):
    """Press combination like Ctrl+Tab, Ctrl+T, etc."""
    try:
        for vk in vk_codes:
            key_down(vk)
            time.sleep(0.01)
        time.sleep(0.03)
        for vk in reversed(vk_codes):
            key_up(vk)
            time.sleep(0.01)
    except Exception as e:
        print(f"[-] Hotkey error: {e}")

def set_clipboard_text(text):
    """Set Windows clipboard text safely (Unicode)."""
    # Escape for PowerShell single-quoted string: double single-quotes
    safe = (text or '').replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.Clipboard]::SetText('{safe}'); "
        "Start-Sleep -Milliseconds 60"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=5)

def type_text(text):
    """Type unicode text via clipboard paste (Ctrl+V) for reliability with non-ASCII."""
    try:
        set_clipboard_text(text or '')
        time.sleep(0.05)
        press_hotkey(VK_CONTROL, 0x56)  # Ctrl+V
        return
    except Exception as e:
        print(f"[-] Clipboard type failed, falling back to SendKeys: {e}")

    try:
        escaped = text or ''
        for ch in ['+', '^', '%', '~', '(', ')', '{', '}', '[', ']']:
            escaped = escaped.replace(ch, '{' + ch + '}')
        # Escape single quotes for PowerShell
        escaped = escaped.replace("'", "''")
        ps = f"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys('{escaped}')"
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=5)
    except Exception as e:
        print(f"[-] Type text error: {e}")

def get_clipboard_text():
    """Get text from Windows clipboard."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::GetText()"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[-] get_clipboard_text error: {e}")
        return ""

def get_browser_address_bar_url():
    """Read the current URL from the browser's address bar."""
    try:
        press_hotkey(VK_CONTROL, VK_L)  # Focus address bar
        time.sleep(0.1)
        press_hotkey(VK_CONTROL, 0x41)  # Select all (Ctrl+A)
        time.sleep(0.05)
        press_hotkey(VK_CONTROL, 0x43)  # Copy (Ctrl+C)
        time.sleep(0.1)

        url = get_clipboard_text()

        # Press Escape to unfocus address bar without navigating
        press_key(VK_ESCAPE, extended=False)
        time.sleep(0.05)

        return url
    except Exception as e:
        print(f"[-] get_browser_address_bar_url error: {e}")
        return ""

def get_window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value or ""

def enum_windows():
    """Return list of (hwnd, title, pid) for visible top-level windows."""
    results = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = get_window_title(hwnd)
        if not title.strip():
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append((hwnd, title, pid.value))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return results

def get_process_name(pid):
    try:
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""

def get_active_processes(limit=None):
    """
    Get all active user & window processes dynamically without artificial hard limits.
    Prioritizes top-level visible application windows, followed by active user applications.
    Returns list of dicts: [{'pid': int, 'name': str, 'title': str}]
    """
    ignore_proc = {
        'system', 'idle', 'svchost.exe', 'csrss.exe', 'services.exe',
        'wininit.exe', 'lsass.exe', 'smss.exe', 'winlogon.exe', 'dwm.exe',
        'ctfmon.exe', 'searchhost.exe', 'startmenuexperiencehost.exe',
        'runtimebroker.exe', 'shellexperiencehost.exe', 'applicationframehost.exe',
        'lockapp.exe', 'sihost.exe', 'taskhostw.exe', 'conhost.exe', 'compattelrunner.exe'
    }
    ignore_titles = {
        'program manager', 'settings', 'windows input experience', 'taskbar',
        'msctfime ui', 'systemtray', 'desktop', 'new notification'
    }

    processes = []
    seen_pids = set()
    name_cache = {}

    # 1. Gather top-level visible window processes (Task Manager Apps)
    try:
        windows = enum_windows()
        for hwnd, title, pid in windows:
            if pid in seen_pids or pid == os.getpid():
                continue
            if pid not in name_cache:
                name_cache[pid] = get_process_name(pid)
            pname = name_cache[pid]
            if not pname or pname in ignore_proc:
                continue
            t_clean = title.strip()
            if not t_clean or t_clean.lower() in ignore_titles:
                continue

            seen_pids.add(pid)
            processes.append({
                'pid': pid,
                'name': pname,
                'title': t_clean[:35]
            })
    except Exception as e:
        print(f"[-] Error listing window processes: {e}")

    # 2. Add remaining non-system user processes sorted by memory usage
    try:
        proc_list = []
        for p in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                pid = p.info['pid']
                pname = (p.info['name'] or '').lower()
                if pid in seen_pids or pid == os.getpid() or pid == 0 or pname in ignore_proc:
                    continue
                mem = p.info['memory_info'].rss if p.info['memory_info'] else 0
                proc_list.append((mem, pid, pname))
            except Exception:
                pass

        proc_list.sort(key=lambda x: x[0], reverse=True)
        for mem, pid, pname in proc_list:
            seen_pids.add(pid)
            clean_name = pname.rsplit('.', 1)[0].capitalize()
            processes.append({
                'pid': pid,
                'name': pname,
                'title': clean_name
            })
    except Exception as e:
        print(f"[-] Error listing psutil processes: {e}")

    if limit is not None and isinstance(limit, int) and limit > 0:
        return processes[:limit]

    return processes

def force_foreground(hwnd):
    """Bring window to foreground reliably on Windows."""
    try:
        # Allow this process to set foreground
        try:
            user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
        except Exception:
            pass

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            user32.ShowWindow(hwnd, 5)  # SW_SHOW

        foreground = user32.GetForegroundWindow()
        current_thread = kernel32.GetCurrentThreadId()
        foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)

        attached_fg = False
        attached_tg = False
        if foreground_thread and foreground_thread != current_thread:
            attached_fg = bool(user32.AttachThreadInput(current_thread, foreground_thread, True))
        if target_thread and target_thread != current_thread and target_thread != foreground_thread:
            attached_tg = bool(user32.AttachThreadInput(current_thread, target_thread, True))

        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.SetFocus(hwnd)

        if attached_tg:
            user32.AttachThreadInput(current_thread, target_thread, False)
        if attached_fg:
            user32.AttachThreadInput(current_thread, foreground_thread, False)

        # Alt key trick sometimes unlocks foreground lock
        if user32.GetForegroundWindow() != hwnd:
            press_key(0x12, extended=False)  # VK_MENU / Alt
            user32.SetForegroundWindow(hwnd)

        time.sleep(0.05)
        return user32.GetForegroundWindow() == hwnd
    except Exception as e:
        print(f"[-] force_foreground error: {e}")
        return False

def title_matches_ytmusic(title):
    t = (title or '').lower()
    return (
        'youtube music' in t
        or 'music.youtube' in t
        or ('youtube' in t and 'music' in t)
    )

def find_ytmusic_via_tab_cycle(max_tabs=12):
    """
    Focus browser and cycle Ctrl+Tab looking for YouTube Music in window title.
    Returns True if found and focused.
    """
    if not focus_browser(prefer_comet=True):
        return False
    time.sleep(0.1)
    for i in range(max_tabs):
        hwnd = user32.GetForegroundWindow()
        title = get_window_title(hwnd)
        if title_matches_ytmusic(title):
            print(f"[+] Found YT Music tab after cycle: {title}")
            return True
        press_hotkey(VK_CONTROL, VK_TAB)
        time.sleep(0.12)
    return False

def find_window_by_hints(hints, process_names=None):
    """Find first matching window by title hints and optional process names."""
    hints_l = [h.lower() for h in hints if h]
    process_names_l = {p.lower() for p in (process_names or [])}

    for hwnd, title, pid in enum_windows():
        title_l = title.lower()
        pname = get_process_name(pid)
        title_ok = any(h in title_l for h in hints_l) if hints_l else True
        proc_ok = (pname in process_names_l) if process_names_l else True
        if title_ok and proc_ok:
            return hwnd, title, pname
        # If only process match requested and no title match needed
        if process_names_l and pname in process_names_l and not hints_l:
            return hwnd, title, pname
    return None, None, None

def find_browser_window(prefer_comet=True):
    """Find an open browser window, preferring Comet."""
    windows = enum_windows()
    comet = []
    others = []
    for hwnd, title, pid in windows:
        pname = get_process_name(pid)
        if pname in BROWSER_PROCESS_NAMES:
            if pname == 'comet.exe':
                comet.append((hwnd, title, pname))
            else:
                others.append((hwnd, title, pname))
    if prefer_comet and comet:
        return comet[0]
    pool = comet + others
    return pool[0] if pool else (None, None, None)

def focus_browser(prefer_comet=True):
    hwnd, title, pname = find_browser_window(prefer_comet=prefer_comet)
    if hwnd:
        ok = force_foreground(hwnd)
        print(f"[+] Focused browser window: {title} ({pname}) success={ok}")
        return ok
    print("[-] No browser window found to focus")
    return False

def is_process_running(names):
    names_l = {n.lower() for n in names}
    for p in psutil.process_iter(['name']):
        try:
            if (p.info['name'] or '').lower() in names_l:
                return True
        except Exception:
            pass
    return False

def find_comet_exe():
    comet_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Comet\Application\comet.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Comet\Application\comet.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Comet\Application\comet.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Comet\Application\comet.exe"),
    ]
    for path in comet_paths:
        if os.path.exists(path):
            return path
    try:
        res = subprocess.run(["where", "comet"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip().splitlines()[0].strip()
    except Exception:
        pass
    return None

def open_in_comet_or_browser(url_or_app, new_window=False):
    comet_exe = find_comet_exe()

    if comet_exe:
        args = [comet_exe]
        if new_window:
            args.append("--new-window")
        if url_or_app.startswith("http://") or url_or_app.startswith("https://"):
            args.append(url_or_app)
        try:
            subprocess.Popen(args)
        except Exception:
            os.system(f'start "" "{comet_exe}" "{url_or_app}"' if url_or_app.startswith("http") else f'start "" "{comet_exe}"')
        return "Comet Browser"
    else:
        if url_or_app.startswith("http://") or url_or_app.startswith("https://"):
            os.system(f'start "" "{url_or_app}"')
        else:
            os.system("start chrome")
        return "Браузер (за замовчуванням)"

def focus_or_open_app(app, yt_url=None, focus_only=False, focus_existing_yt=False, resume_play=False):
    app = (app or '').lower()
    yt_url = yt_url or 'https://music.youtube.com/watch?v=1rXJbd3I2W4&list=RDAMVMn6P0SitRwy8'

    if app == 'ytmusic':
        # Always open YouTube Music fresh — no searching existing tabs/windows
        if focus_browser(prefer_comet=True):
            time.sleep(0.15)
            # Open in a new tab
            press_hotkey(VK_CONTROL, 0x54)  # Ctrl+T
            time.sleep(0.2)
            type_text(yt_url)
            time.sleep(0.1)
            press_key(VK_RETURN, extended=False)
            print(f"[+] Opened YouTube Music in new tab: {yt_url}")
            return

        # Fallback: launch Comet/browser with URL
        open_in_comet_or_browser(yt_url)
        print(f"[+] Launched YouTube Music via browser: {yt_url}")
        return

    if app == 'comet':
        # Focus existing Comet if running
        hwnd, title, pname = find_window_by_hints(['comet'], process_names=['comet.exe'])
        if not hwnd:
            hwnd, title, pname = find_browser_window(prefer_comet=True)
        if hwnd:
            force_foreground(hwnd)
            print(f"[+] Focused Comet/browser: {title}")
            return
        if focus_only:
            # Still try open if nothing to focus
            open_in_comet_or_browser("about:blank")
            return
        open_in_comet_or_browser("https://google.com")
        return

    if app == 'discord':
        hwnd, title, _ = find_window_by_hints(['discord'], process_names=['discord.exe'])
        if hwnd:
            force_foreground(hwnd)
            print(f"[+] Focused Discord: {title}")
            return
        if focus_only and is_process_running(['discord.exe']):
            # Process exists but no main window yet
            return
        local_data = os.environ.get('LOCALAPPDATA', '')
        update_exe = os.path.join(local_data, 'Discord', 'Update.exe')
        discord_exes = glob.glob(os.path.join(local_data, 'Discord', 'app-*', 'Discord.exe'))
        if os.path.exists(update_exe):
            subprocess.Popen([update_exe, '--processStart', 'Discord.exe'])
        elif discord_exes:
            subprocess.Popen([discord_exes[-1]])
        else:
            os.system("start discord")
        return

    if app == 'steam':
        hwnd, title, _ = find_window_by_hints(['steam'], process_names=['steam.exe'])
        if hwnd:
            force_foreground(hwnd)
            print(f"[+] Focused Steam: {title}")
            return
        os.system("start steam://open/main")
        return

    if app == 'chrome':
        hwnd, title, _ = find_window_by_hints(['chrome', 'google chrome'], process_names=['chrome.exe'])
        if hwnd:
            force_foreground(hwnd)
            return
        os.system("start chrome")
        return

    # Generic: try focus by name, else start
    hints = APP_WINDOW_HINTS.get(app, [app])
    hwnd, title, _ = find_window_by_hints(hints)
    if hwnd:
        force_foreground(hwnd)
        return
    if not focus_only:
        os.system(f'start "" "{app}"')

def is_browser_foreground():
    """Check if current foreground window is a browser."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    pname = get_process_name(pid.value)
    return pname in BROWSER_PROCESS_NAMES

def browser_tab_action(action):
    """Switch/create/close browser tabs via Chromium shortcuts after focusing browser."""
    # Only focus browser if it's not already in foreground (speeds up rapid tab switching)
    if not is_browser_foreground():
        if not focus_browser(prefer_comet=True):
            # Try open Comet first
            open_in_comet_or_browser("about:blank")
            time.sleep(1.0)
            if not focus_browser(prefer_comet=True):
                print("[-] browser_tab: cannot focus browser")
                return False
        time.sleep(0.05)

    action = (action or '').lower()

    if action == 'prev':
        # Ctrl+Shift+Tab
        press_hotkey(VK_CONTROL, VK_SHIFT, VK_TAB)
    elif action == 'next':
        # Ctrl+Tab
        press_hotkey(VK_CONTROL, VK_TAB)
    elif action == 'new':
        # Ctrl+T
        press_hotkey(VK_CONTROL, VK_T)
    elif action == 'close':
        # Ctrl+W
        press_hotkey(VK_CONTROL, VK_W)
    else:
        print(f"[-] Unknown browser_tab action: {action}")
        return False

    print(f"[+] browser_tab action done: {action}")
    return True

def clean_google_redirect_url(url):
    """Extract the real URL from a Google redirect URL (google.com/url?q=REAL_URL)."""
    if not url:
        return None
    url_lower = url.lower()
    if 'google.com/url?' not in url_lower and 'google.com/url/' not in url_lower:
        return None

    from urllib.parse import urlparse, parse_qs, unquote
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    # Google redirect uses 'q' or 'url' parameter
    real_url = params.get('q', params.get('url', [None]))
    if real_url and real_url[0]:
        return unquote(real_url[0])
    return None

def browser_search(query, open_first_result=True):
    """
    Focus/open browser, open new tab, run Google search.
    If open_first_result: use Google "I'm Feeling Lucky" (btnI) to jump to first organic hit.
    Automatically cleans Google redirect URLs (google.com/url?q=) to navigate directly.
    """
    from urllib.parse import quote_plus

    query = (query or '').strip()
    if not query:
        print("[-] browser_search: empty query")
        return False

    focused = focus_browser(prefer_comet=True)
    if not focused:
        open_in_comet_or_browser("https://www.google.com")
        time.sleep(1.2)
        focused = focus_browser(prefer_comet=True)
    if not focused:
        print("[-] browser_search: no browser")
        return False

    time.sleep(0.15)
    press_hotkey(VK_CONTROL, VK_T)  # new tab
    time.sleep(0.3)
    press_hotkey(VK_CONTROL, VK_L)  # address bar
    time.sleep(0.12)
    press_hotkey(VK_CONTROL, 0x41)  # select all
    time.sleep(0.05)

    if open_first_result:
        # Feeling Lucky ≈ first non-ad organic result
        url = f"https://www.google.com/search?btnI=1&q={quote_plus(query)}"
    else:
        url = f"https://www.google.com/search?q={quote_plus(query)}"

    type_text(url)
    time.sleep(0.1)
    press_key(VK_RETURN, extended=False)

    # If using "I'm Feeling Lucky", check for Google redirect and navigate directly
    if open_first_result:
        time.sleep(2.0)  # Wait for Google redirect to process
        current_url = get_browser_address_bar_url()
        real_url = clean_google_redirect_url(current_url)
        if real_url:
            print(f"[+] Google redirect detected, navigating directly to: {real_url}")
            press_hotkey(VK_CONTROL, VK_L)  # Address bar
            time.sleep(0.1)
            press_hotkey(VK_CONTROL, 0x41)  # Select all
            time.sleep(0.05)
            type_text(real_url)
            time.sleep(0.1)
            press_key(VK_RETURN, extended=False)

    print(f"[+] browser_search done: {query} (lucky={open_first_result})")
    return True

def send_online_notification():
    try:
        from urllib.parse import quote
        requests.get(f"{SERVER_URL}?agent_online=1&pc_id={quote(PC_ID)}&pc_name={quote(PC_NAME)}", timeout=5)
        print(f"[+] Online notification sent (PC_ID={PC_ID}, PC_NAME={PC_NAME}).")
    except Exception as e:
        print(f"[-] Failed to send online notification: {e}")

def send_result(chat_id, text=None, photo_path=None, msg_id=None, proc_list=None, audio_devices=None, page=1):
    try:
        data = {'agent_result': '1', 'chat_id': str(chat_id), 'pc_id': PC_ID, 'pc_name': PC_NAME}
        if msg_id:
            data['msg_id'] = str(msg_id)
        if text:
            data['text'] = text
        if proc_list is not None:
            data['type'] = 'processes'
            data['procs_json'] = json.dumps(proc_list, ensure_ascii=False)
            data['page'] = page
        if audio_devices is not None:
            data['type'] = 'audio_devices'
            data['audio_devices_json'] = json.dumps(audio_devices, ensure_ascii=False)
        files = {}
        if photo_path and os.path.exists(photo_path):
            files['screenshot'] = open(photo_path, 'rb')

        requests.post(SERVER_URL, data=data, files=files, timeout=15)
        if files:
            files['screenshot'].close()
            try:
                os.remove(photo_path)
            except Exception:
                pass
    except Exception as e:
        print(f"[-] Error sending result to server: {e}")

def take_screenshot():
    screenshot_path = os.path.join(os.getcwd(), 'temp_screenshot.png')
    try:
        img = ImageGrab.grab()
        img.save(screenshot_path)
        if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
            return screenshot_path
    except Exception as e:
        print(f"[-] PIL screenshot failed: {e}")

    try:
        ps_script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bitmap = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
        $bitmap.Save('{screenshot_path.replace("\\", "/")}', [System.Drawing.Imaging.ImageFormat]::Png)
        $graphics.Dispose()
        $bitmap.Dispose()
        """
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
            return screenshot_path
    except Exception as e:
        print(f"[-] PowerShell screenshot failed: {e}")

    return None

def set_brightness(level):
    try:
        ps_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"
        subprocess.run(["powershell", "-Command", ps_cmd])
    except Exception as e:
        print(f"[-] Brightness error: {e}")

def handle_command(cmd_item):
    cmd_name = cmd_item.get('command')
    chat_id = cmd_item.get('chat_id')
    params = cmd_item.get('params', {}) or {}

    print(f"[*] Executing command: {cmd_name} with params: {params}")

    if cmd_name == 'screenshot':
        photo = take_screenshot()
        if photo:
            send_result(chat_id, text="📸 Скріншот екрана ПК RONY", photo_path=photo, msg_id=params.get('msg_id'))

    elif cmd_name == 'get_processes':
        try:
            procs = get_active_processes(limit=None)
            page = params.get('page', 1)
            send_result(chat_id, proc_list=procs, msg_id=params.get('msg_id'), page=page)
        except Exception as e:
            print(f"[-] get_processes error: {e}")

    elif cmd_name == 'get_audio_devices':
        try:
            devices = get_audio_devices()
            send_result(chat_id, audio_devices=devices, msg_id=params.get('msg_id'))
        except Exception as e:
            print(f"[-] get_audio_devices error: {e}")

    elif cmd_name == 'status':
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('C:').percent
            boot_time = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
            uptime_seconds = int(time.time() - psutil.boot_time())
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours} год {minutes} хв"

            status_text = (
                f"📊 *СТАН ПК RONY*\n"
                f"───────────────────────────\n"
                f"💻 *Завантаження CPU:* `{cpu}%`\n"
                f"🧠 *Оперативна пам'ять:* `{ram}%`\n"
                f"💾 *Диск C:* `{disk}%`\n"
                f"⏱️ *Uptime:* `{uptime_str}`\n"
                f"📅 *Час запуску:* `{boot_time}`\n"
                f"───────────────────────────"
            )
            send_result(chat_id, text=status_text)
        except Exception as e:
            print(f"[-] Status error: {e}")

    elif cmd_name == 'open_app':
        app = params.get('app', '').lower()
        yt_url = params.get('yt_url', 'https://music.youtube.com/watch?v=1rXJbd3I2W4&list=RDAMVMn6P0SitRwy8')
        focus_only = bool(params.get('focus_only', False))
        focus_existing_yt = bool(params.get('focus_existing_yt', False))
        resume_play = bool(params.get('resume_play', False))
        try:
            focus_or_open_app(
                app,
                yt_url=yt_url,
                focus_only=focus_only,
                focus_existing_yt=focus_existing_yt,
                resume_play=resume_play
            )
        except Exception as e:
            print(f"[-] open_app error: {e}")

    elif cmd_name == 'browser_tab':
        action = params.get('action', '')
        try:
            browser_tab_action(action)
        except Exception as e:
            print(f"[-] browser_tab error: {e}")

    elif cmd_name == 'browser_search':
        query = params.get('query', '')
        open_first = bool(params.get('open_first_result', True))
        try:
            browser_search(query, open_first_result=open_first)
        except Exception as e:
            print(f"[-] browser_search error: {e}")

    elif cmd_name == 'media':
        action = params.get('action', '')
        if action == 'vup':
            for _ in range(5):
                press_key(VK_VOLUME_UP)
        elif action == 'vdown':
            for _ in range(5):
                press_key(VK_VOLUME_DOWN)
        elif action == 'mute':
            press_key(VK_VOLUME_MUTE)
        elif action == 'play':
            # For general Play action (movies / sites / video players):
            # Focus browser, move cursor to EXACT CENTER of active window, and click!
            if not is_browser_foreground():
                focus_browser(prefer_comet=True)
                time.sleep(0.05)
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                cx = (rect.left + rect.right) // 2
                cy = (rect.top + rect.bottom) // 2
                user32.SetCursorPos(cx, cy)
                time.sleep(0.01)
                user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
                time.sleep(0.02)
                user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
            else:
                press_key(VK_MEDIA_PLAY_PAUSE)
        elif action == 'music_play':
            # Hardware / OS level media play/pause for background music without touching cursor
            press_key(VK_MEDIA_PLAY_PAUSE)
        elif action == 'music_next':
            press_key(VK_MEDIA_NEXT_TRACK)
        elif action == 'music_prev':
            press_key(VK_MEDIA_PREV_TRACK)
        elif action == 'scroll_up':
            # Center cursor on active window to ensure scroll events hit the content and not dead areas
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                cx = (rect.left + rect.right) // 2
                cy = (rect.top + rect.bottom) // 2
                user32.SetCursorPos(cx, cy)
            # Smaller scroll per click (240 = 2 wheel notches; WHEEL_DELTA=120)
            user32.mouse_event(0x0800, 0, 0, 240, 0)  # MOUSEEVENTF_WHEEL
        elif action == 'scroll_down':
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                cx = (rect.left + rect.right) // 2
                cy = (rect.top + rect.bottom) // 2
                user32.SetCursorPos(cx, cy)
            user32.mouse_event(0x0800, 0, 0, -240, 0)  # MOUSEEVENTF_WHEEL
        elif action == 'next':
            press_key(VK_MEDIA_NEXT_TRACK)
        elif action == 'prev':
            press_key(VK_MEDIA_PREV_TRACK)
        elif action in ['rewind', 'rewind_15']:
            press_key(VK_LEFT)
            press_key(VK_J)
        elif action in ['forward', 'forward_15']:
            press_key(VK_RIGHT)
            press_key(VK_L)
        elif action == 'fullscreen':
            press_key(VK_F)

    elif cmd_name == 'brightness':
        val = params.get('level', 80)
        set_brightness(val)

    elif cmd_name == 'lock':
        os.system("rundll32.exe user32.dll,LockWorkStation")

    elif cmd_name == 'unlock':
        ps_cmd = "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys(' '); Start-Sleep -Milliseconds 300; $wsh.SendKeys('{ENTER}')"
        subprocess.run(["powershell", "-Command", ps_cmd])

    elif cmd_name == 'uninstall':
        print("[!] Cleaning up agent files and startup...")
        # Remove startup shortcut
        startup_path = os.path.join(os.environ.get('APPDATA', ''), r"Microsoft\Windows\Start Menu\Programs\Startup\run_agent.bat")
        if os.path.exists(startup_path):
            os.remove(startup_path)
        # Kill all instances of agent.py as well
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if proc.info['name'] == 'python.exe' and 'agent.py' in str(proc.info['cmdline']):
                    proc.terminate()
            except: pass
        # Self-delete (limited, but tries to script it)
        os.system('del /f /q "run_agent.bat"')
        sys.exit(0)

    elif cmd_name == 'shutdown':
        os.system("shutdown /s /f /t 2")

    elif cmd_name == 'sleep':
        subprocess.run(["powershell", "-Command", "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"])

    elif cmd_name == 'hibernate':
        os.system("shutdown /h")

    elif cmd_name == 'reboot':
        os.system("shutdown /r /f /t 2")

    elif cmd_name == 'msg':
        msg_text = params.get('text', '')
        subprocess.run(f'msg * "{msg_text}"', shell=True)

    elif cmd_name == 'cmd':
        command = params.get('command', '')
        try:
            subprocess.run(command, shell=True, timeout=10)
        except Exception as e:
            print(f"[-] CMD execution error: {e}")

    elif cmd_name == 'kill_app':
        target = params.get('target', 'active')
        pid = params.get('pid')
        if pid:
            try:
                p = psutil.Process(int(pid))
                p.kill()
                print(f"[+] Killed PID {pid}")
            except Exception as e:
                print(f"[-] Error killing PID {pid}: {e}")
                try:
                    subprocess.run(f"taskkill /F /PID {pid} /T", shell=True)
                except Exception:
                    pass
        elif target in ['active', 'current', '']:
            ps = '$hwnd = (Get-Process | Where-Object {$_.MainWindowHandle -ne 0} | Select-Object -First 1); if ($hwnd) { Stop-Process -Id $hwnd.Id -Force }'
            subprocess.run(["powershell", "-Command", ps])
        else:
            os.system(f"taskkill /F /IM \"{target}\" /T")

        # Auto refresh process list after killing
        time.sleep(0.3)
        try:
            procs = get_active_processes(limit=None)
            page = params.get('page', 1)
            send_result(chat_id, proc_list=procs, msg_id=params.get('msg_id'), page=page)
        except Exception:
            pass

    elif cmd_name == 'set_audio_device':
        device_index = params.get('device_index')
        device_id = params.get('device_id')
        try:
            devices = set_audio_device(device_index=device_index, device_id=device_id)
            send_result(chat_id, audio_devices=devices, msg_id=params.get('msg_id'))
            print(f"[+] Set audio device index={device_index} id={device_id}")
        except Exception as e:
            print(f"[-] set_audio_device error: {e}")
    else:
        print(f"[-] Unknown command: {cmd_name}")

def main():
    print("=" * 60)
    print("⚡ RONY PC LOCAL AGENT ONLINE ⚡")
    print(f"Server URL: {SERVER_URL}")
    print("Supports: browser_tab, browser_search, open_app(focus), media, ...")
    print("=" * 60)

    send_online_notification()

    while True:
        try:
            from urllib.parse import quote
            r = requests.get(f"{SERVER_URL}?agent_poll=1&pc_id={quote(PC_ID)}&pc_name={quote(PC_NAME)}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                commands = data.get('commands', [])
                for cmd in commands:
                    handle_command(cmd)
        except Exception as e:
            print(f"[-] Poll error: {e}")

        time.sleep(0.15)

if __name__ == '__main__':
    main()
