import os
import sys
import time
import requests
import pyautogui
import json
import subprocess
import shutil
import ctypes
from urllib.parse import quote

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
SERVER_URL = os.environ.get("SERVER_URL", "https://rony-telegram-bot.onrender.com/").rstrip("/") + "/"
PC_NAME = os.environ.get("COMPUTERNAME", "UNKNOWN_PC")
PC_ID = f"{PC_NAME}"

pyautogui.FAILSAFE = False

def get_local_ip():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def focus_window_by_keywords(keywords):
    """
    Finds a visible window matching any of the keywords in process name or title,
    and brings it to the foreground (restoring if minimized).
    """
    user32 = ctypes.windll.user32
    target_hwnd = None

    def enum_windows_callback(hwnd, lParam):
        nonlocal target_hwnd
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                title_buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, title_buf, length + 1)
                title = title_buf.value.lower()

                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                proc_name = ""
                try:
                    import psutil
                    proc_name = psutil.Process(pid.value).name().lower()
                except Exception:
                    pass

                for kw in keywords:
                    kw_lower = kw.lower()
                    if kw_lower in title or kw_lower in proc_name:
                        target_hwnd = hwnd
                        return False
        return True

    try:
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

        if target_hwnd:
            fore_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
            app_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            if fore_thread != app_thread:
                user32.AttachThreadInput(fore_thread, app_thread, True)

            if user32.IsIconic(target_hwnd):
                user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
            else:
                user32.ShowWindow(target_hwnd, 5)  # SW_SHOW
            user32.SetForegroundWindow(target_hwnd)

            if fore_thread != app_thread:
                user32.AttachThreadInput(fore_thread, app_thread, False)
            return True
    except Exception as e:
        print(f"[-] focus_window_by_keywords error: {e}")

    return False

# ---------------------------------------------------------
# C# Audio Devices Helper (MMDeviceEnumerator & IPolicyConfig)
# ---------------------------------------------------------
AUDIO_CSHARP_CODE = '''
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;

public class AudioDeviceHelper {
    [ComImport, Guid("BCDE0385-4944-460C-8564-65D99D075681")]
    public class MMDeviceEnumeratorComObject { }

    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDeviceEnumerator {
        int EnumAudioEndpoints(int dataFlow, int stateMask, out IMMDeviceCollection devices);
        int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
    }

    [Guid("0BD6A3BA-3330-4830-8964-0888B07D0E86"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDeviceCollection {
        int GetCount(out uint count);
        int Item(uint index, out IMMDevice device);
    }

    [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDevice {
        int OpenPropertyStore(int stgmAccess, out IPropertyStore properties);
        int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
    }

    [Guid("886D8EEB-8CF2-4446-8D02-CDA103045D7E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPropertyStore {
        int GetCount(out uint count);
        int GetAt(uint index, out PROPERTYKEY key);
        int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PROPERTYKEY {
        public Guid fmtid;
        public uint pid;
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct PROPVARIANT {
        [FieldOffset(0)] public ushort vt;
        [FieldOffset(8)] public IntPtr pwszVal;
    }

    [Guid("f8679f50-850a-41cf-9c72-430f60f290c0"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPolicyConfig {
        int GetMixFormat();
        int GetDeviceFormat();
        int ResetDeviceFormat();
        int SetDeviceFormat();
        int GetProcessingPeriod();
        int SetProcessingPeriod();
        int GetShareMode();
        int SetShareMode();
        int GetPropertyValue();
        int SetPropertyValue();
        int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string deviceId, int role);
    }

    [ComImport, Guid("87086544-460C-4264-A4B0-8DA2F2637568")]
    public class PolicyConfigClient { }

    public static string GetDevicesJson() {
        try {
            var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
            IMMDevice defaultDev = null;
            string defaultId = "";
            try {
                enumerator.GetDefaultAudioEndpoint(0, 0, out defaultDev);
                if (defaultDev != null) defaultDev.GetId(out defaultId);
            } catch {}

            IMMDeviceCollection collection;
            enumerator.EnumAudioEndpoints(0, 1, out collection);
            uint count;
            collection.GetCount(out count);

            var list = new List<string>();
            PROPERTYKEY PKEY_Device_FriendlyName = new PROPERTYKEY { fmtid = new Guid("a45c254e-df1c-4efd-8020-67d146a850e0"), pid = 14 };

            for (uint i = 0; i < count; i++) {
                IMMDevice dev;
                collection.Item(i, out dev);
                string id;
                dev.GetId(out id);
                IPropertyStore store;
                dev.OpenPropertyStore(0, out store);
                PROPVARIANT prop;
                store.GetValue(ref PKEY_Device_FriendlyName, out prop);
                string name = Marshal.PtrToStringUni(prop.pwszVal);
                bool isDef = (id == defaultId);
                string cleanName = (name != null) ? name.Replace("\\\\", "/").Replace("\"", "'") : "Audio Device";
                list.Add(string.Format("{{\"index\":{0},\"name\":\"{1}\",\"is_default\":{2}}}", i, cleanName, isDef ? "true" : "false"));
            }
            return "[" + string.Join(",", list.ToArray()) + "]";
        } catch (Exception ex) {
            return "[]";
        }
    }

    public static int SetDefault(int targetIndex) {
        try {
            var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
            IMMDeviceCollection collection;
            enumerator.EnumAudioEndpoints(0, 1, out collection);
            IMMDevice dev;
            collection.Item((uint)targetIndex, out dev);
            string id;
            dev.GetId(out id);

            var policy = (IPolicyConfig)(new PolicyConfigClient());
            policy.SetDefaultEndpoint(id, 0); // eConsole
            policy.SetDefaultEndpoint(id, 1); // eMultimedia
            policy.SetDefaultEndpoint(id, 2); // eCommunications
            return 0;
        } catch (Exception ex) {
            Console.WriteLine(ex);
            return -1;
        }
    }
}
'''

def get_audio_devices():
    try:
        ps_command = f'''
$code = @'
{AUDIO_CSHARP_CODE}
'@
Add-Type -TypeDefinition $code
[AudioDeviceHelper]::GetDevicesJson()
'''
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True, text=True, timeout=10)
        output = res.stdout.strip()
        if output and output.startswith("["):
            return json.loads(output)
    except Exception as e:
        print(f"[-] Error fetching audio devices: {e}")
    return []

def set_audio_device(device_index=None, device_id=None):
    if device_index is not None:
        try:
            idx = int(device_index)
            ps_command = f'''
$code = @'
{AUDIO_CSHARP_CODE}
'@
Add-Type -TypeDefinition $code
[AudioDeviceHelper]::SetDefault({idx})
'''
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True, text=True, timeout=10)
            time.sleep(0.5)
        except Exception as e:
            print(f"[-] Error setting audio device: {e}")
    return get_audio_devices()

def get_active_processes(limit=None):
    procs = []
    try:
        ps_script = '''
Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object Id, ProcessName, MainWindowTitle | ConvertTo-Json -Compress
'''
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=10)
        output = res.stdout.strip()
        if output:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                procs.append({
                    'pid': item.get('Id'),
                    'name': item.get('ProcessName', ''),
                    'title': item.get('MainWindowTitle', '')
                })
    except Exception as e:
        print(f"[-] PowerShell process fetch failed: {e}")

    if not procs:
        try:
            import psutil
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    name = p.info['name'] or ''
                    if any(x in name.lower() for x in ['chrome', 'browser', 'telegram', 'discord', 'steam', 'spotify', 'code', 'vlc']):
                        procs.append({
                            'pid': p.info['pid'],
                            'name': name,
                            'title': name
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"[-] psutil process fetch failed: {e}")

    return procs

def send_online_notification():
    try:
        payload = {
            'pc_id': PC_ID,
            'pc_name': PC_NAME,
            'status': 'online',
            'ip': get_local_ip()
        }
        r = requests.post(SERVER_URL, data=payload, timeout=10)
        if r.status_code == 200:
            print("[+] Online notification sent to hosting server.")
        else:
            print(f"[-] Hosting returned status code {r.status_code}")
    except Exception as e:
        print(f"[-] Failed to send online notification: {e}")

def take_screenshot_bytes():
    try:
        from PIL import ImageGrab
        import io
        img = ImageGrab.grab()
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG', optimize=True)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"[-] Screenshot error: {e}")
        return None

def send_result(chat_id, text=None, screenshot_bytes=None, proc_list=None, audio_devices=None, msg_id=None):
    try:
        payload = {
            'pc_id': PC_ID,
            'chat_id': chat_id
        }
        if msg_id:
            payload['msg_id'] = msg_id

        files = None
        if text:
            payload['type'] = 'text'
            payload['text'] = text

        if screenshot_bytes:
            payload['type'] = 'screenshot'
            files = {'screenshot': ('screenshot.png', screenshot_bytes, 'image/png')}
        
        if proc_list is not None:
            payload['type'] = 'processes'
            payload['procs_json'] = json.dumps(proc_list)

        if audio_devices is not None:
            payload['type'] = 'audio_devices'
            payload['audio_devices_json'] = json.dumps(audio_devices)

        r = requests.post(SERVER_URL, data=payload, files=files, timeout=15)
        if r.status_code == 200:
            print(f"[+] Result sent to server for chat_id={chat_id}")
        else:
            print(f"[-] Server returned status code {r.status_code}")
    except Exception as e:
        print(f"[-] Failed to send result: {e}")

def get_system_status():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        status_text = (
            f"📊 *СТАН ПК {PC_NAME}*\n"
            f"───────────────────────────\n"
            f"💻 *Завантаження ЦП:* `{cpu}%`\n"
            f"🧠 *ОЗП:* `{ram}%`\n"
            f"🌐 *IP:* `{get_local_ip()}`\n"
            f"⏱️ *Час оновлення:* `{time.strftime('%H:%M:%S')}`"
        )
        return status_text
    except Exception as e:
        return f"📊 *СТАН ПК {PC_NAME}*\nОфлайн або помилка: {e}"

def handle_command(cmd):
    cmd_id = cmd.get('id')
    cmd_name = cmd.get('command')
    chat_id = cmd.get('chat_id')
    params = cmd.get('params', {})

    print(f"[*] Executing command: {cmd_name} with params: {params}")

    if cmd_name == 'screenshot':
        img_bytes = take_screenshot_bytes()
        if img_bytes:
            send_result(chat_id, screenshot_bytes=img_bytes, msg_id=params.get('msg_id'))
        else:
            send_result(chat_id, text="❌ Помилка створення скріншота.", msg_id=params.get('msg_id'))

    elif cmd_name == 'get_processes':
        procs = get_active_processes(limit=None)
        send_result(chat_id, proc_list=procs, msg_id=params.get('msg_id'))

    elif cmd_name == 'get_audio_devices':
        devices = get_audio_devices()
        send_result(chat_id, audio_devices=devices, msg_id=params.get('msg_id'))

    elif cmd_name == 'status':
        st_text = get_system_status()
        send_result(chat_id, text=st_text, msg_id=params.get('msg_id'))

    elif cmd_name == 'browser_tab':
        action = params.get('action')
        if action == 'next':
            pyautogui.hotkey('ctrl', 'tab')
        elif action == 'prev':
            pyautogui.hotkey('ctrl', 'shift', 'tab')
        elif action == 'new':
            pyautogui.hotkey('ctrl', 't')
        elif action == 'close':
            pyautogui.hotkey('ctrl', 'w')

    elif cmd_name == 'browser_search':
        query = params.get('query', '')
        if query:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            os.system(f'start "" "{search_url}"')

    elif cmd_name == 'open_app':
        app = params.get('app', '').lower()
        yt_url = params.get('yt_url')

        if app == 'comet':
            # Focus running Comet or Browser window first
            if not focus_window_by_keywords(['comet', 'chrome', 'msedge', 'brave', 'opera', 'firefox']):
                # If not open, launch Comet executable directly
                comet_path = os.path.expandvars(r"%LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe")
                if os.path.exists(comet_path):
                    os.system(f'start "" "{comet_path}"')
                else:
                    os.system('start comet')

        elif app == 'discord':
            # Focus running Discord window first
            if not focus_window_by_keywords(['discord']):
                # Try protocol handler first
                os.system('start discord://')
                time.sleep(0.5)
                if not focus_window_by_keywords(['discord']):
                    # Search for Discord executable / launcher
                    discord_update = os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe")
                    if os.path.exists(discord_update):
                        subprocess.Popen([discord_update, "--processStart", "Discord.exe"])
                    else:
                        import glob
                        app_exes = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"))
                        if app_exes:
                            os.system(f'start "" "{app_exes[0]}"')
                        else:
                            os.system('start "" "discord.exe"')

        elif app == 'steam':
            # Focus running Steam window first
            if not focus_window_by_keywords(['steam']):
                os.system('start steam://open/main')

        elif app == 'ytmusic':
            if yt_url:
                os.system(f'start "" "{yt_url}"')
            else:
                if not focus_window_by_keywords(['youtube', 'music', 'ytmusic', 'comet', 'chrome', 'msedge', 'brave', 'opera', 'firefox']):
                    os.system('start https://music.youtube.com')

        else:
            # Generic fallback: try to focus process matching app name, or start it
            if not focus_window_by_keywords([app]):
                os.system(f'start "" "{app}"')

    elif cmd_name == 'media':
        action = params.get('action')
        if action in ['play', 'music_play']:
            pyautogui.press('playpause')
        elif action in ['next', 'music_next']:
            pyautogui.press('nexttrack')
        elif action in ['prev', 'music_prev']:
            pyautogui.press('prevtrack')
        elif action == 'vup':
            pyautogui.press('volumeup', presses=5)
        elif action == 'vdown':
            pyautogui.press('volumedown', presses=5)
        elif action == 'mute':
            pyautogui.press('volumemute')
        elif action == 'rewind':
            pyautogui.press('left')
        elif action == 'forward':
            pyautogui.press('right')
        elif action == 'fullscreen':
            pyautogui.press('f')
        elif action == 'scroll_up':
            pyautogui.scroll(300)
        elif action == 'scroll_down':
            pyautogui.scroll(-300)

    elif cmd_name == 'shutdown':
        os.system("shutdown /s /f /t 5")

    elif cmd_name == 'sleep':
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    elif cmd_name == 'lock':
        ctypes.windll.user32.LockWorkStation()

    elif cmd_name == 'unlock':
        pyautogui.press('space')

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
                import psutil
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
            os.system(f'taskkill /F /IM "{target}" /T')

        time.sleep(0.3)
        try:
            procs = get_active_processes(limit=None)
            send_result(chat_id, proc_list=procs, msg_id=params.get('msg_id'))
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
    print("Supports: browser_tab, browser_search, open_app(focus), media, screenshot, get_processes, get_audio_devices...")
    print("=" * 60)

    send_online_notification()

    while True:
        try:
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