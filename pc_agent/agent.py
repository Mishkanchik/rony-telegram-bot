import sys
import os
import time
import requests
import json
import subprocess
import socket
import pyautogui
import psutil
from PIL import ImageGrab
import io
import ctypes

# -------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------
SERVER_URL = os.environ.get("SERVER_URL", "https://rony-telegram-bot.onrender.com/").rstrip("/") + "/"
PC_NAME = os.environ.get("COMPUTERNAME", "UNKNOWN_PC")
PC_ID = f"{PC_NAME}"

# PyAutoGUI safety configuration
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

def get_mac_address():
    try:
        import uuid
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,8*6,8)][::-1])
        return mac
    except Exception:
        return "00:00:00:00:00:00"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def send_online_notification():
    try:
        ip = get_local_ip()
        mac = get_mac_address()
        payload = {
            'agent_online': '1',
            'pc_id': PC_ID,
            'pc_name': PC_NAME,
            'ip': ip,
            'mac': mac
        }
        r = requests.post(SERVER_URL, data=payload, timeout=5)
        if r.status_code == 200:
            print("[+] Online notification sent to hosting server.")
    except Exception as e:
        print(f"[-] Failed to send online notification: {e}")

def get_active_processes(limit=15):
    procs = []
    try:
        for p in psutil.process_iter(['pid', 'name']):
            try:
                # Filter out system/idle processes
                name = p.info['name']
                pid = p.info['pid']
                if not name or pid == 0 or name.lower() in ['system idle process', 'system', 'registry', 'smss.exe', 'csrss.exe']:
                    continue
                
                # Check for main window title if available
                title = name
                try:
                    # Windows specific process window title check via powershell or psutil
                    pass
                except Exception:
                    pass
                
                procs.append({
                    'pid': pid,
                    'name': name,
                    'title': title
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        print(f"[-] Error getting processes: {e}")

    # Sort processes by name
    procs = sorted(procs, key=lambda x: x['name'].lower())
    if limit:
        procs = procs[:limit]
    return procs

def get_audio_devices():
    devices = []
    try:
        # PowerShell script using IMMDeviceEnumerator via C# code dynamically compiled or WinRT/Com
        ps_script = """
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;

public class AudioDeviceFetcher {
    [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDeviceEnumerator {
        int EnumAudioEndpoints(int dataFlow, int stateMask, out IMMDeviceCollection devices);
        int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
    }

    [Guid("0BD6A3BA-3330-4830-8964-0888B07D0E86"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDeviceCollection {{
        int GetCount(out uint count);
        int Item(uint index, out IMMDevice device);
    }}

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

    [ComImport, Guid("BCDE0385-4944-460C-8564-65D99D075681")]
    public class MMDeviceEnumeratorComObject { }

    public static string GetDevicesJson() {
        var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
        IMMDevice defaultDev = null;
        string defaultId = "";
        try {
            enumerator.GetDefaultAudioEndpoint(0, 0, out defaultDev);
            if (defaultDev != null) defaultDev.GetId(out defaultId);
        } catch {}

        IMMDeviceCollection collection;
        enumerator.EnumAudioEndpoints(0, 1, out collection); // eRender = 0, DEVICE_STATE_ACTIVE = 1
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
            list.Add(string.Format("{{\"index\":{0},\"name\":\"{1}\",\"is_default\":{2}}}", i, name.Replace("\\\\", "\\\\").Replace("\"", "\\\""), isDef ? "true" : "false"));
        }
        return "[" + string.Join(",", list.ToArray()) + "]";
    }
}
"@
[AudioDeviceFetcher]::GetDevicesJson()
"""
        res = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            devices = json.loads(res.stdout.strip())
            return devices
    except Exception as e:
        print(f"[-] Error getting audio devices: {e}")
    
    # Fallback to SoundVolumeView or simple audio device check if PS fails
    return devices

def set_audio_device(device_index=None, device_id=None):
    try:
        if device_index is not None:
            ps_script = f"""
$code = @"
using System;
using System.Runtime.InteropServices;

public class AudioPolicyConfigWrapper {{
    [ComImport, Guid("87009F00-442B-4730-9079-A386C7B846A7")]
    public class PolicyConfigClient {{ }}

    [Guid("F8679F50-850A-41CF-9C72-430F736873EC"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPolicyConfig {{
        int GetPropertyValue();
        int SetPropertyValue();
        int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string deviceId, int role);
    }}
}}
"@
# Alternate method via nircmd or PowerShell SoundVolumeView if available
"""
            # Using NirCmd / PowerShell or nircmd substitute via PowerShell AudioDeviceCmdlets if installed or built-in script
            # Standard Windows Audio Device Switcher PowerShell snippet:
            ps_script_switch = f"""
$devs = Get-CimInstance Win32_PNPEntity | Where-Object {{ $_.PNPClass -eq "AudioEndpoint" }}
# Simple PowerShell audio switch script or standard device enumeration
"""
            # Best reliable way on Windows without 3rd party tools: standard AudioDeviceCmdlets or SendKeys/Control Panel or C# PolicyConfig
            ps_policy_config = f"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class AudioPolicy {{
    [ComImport, Guid("87009F00-442B-4730-9079-A386C7B846A7")]
    public class PolicyConfigClient {{ }}

    [Guid("F8679F50-850A-41CF-9C72-430F736873EC"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPolicyConfig {{
        int GetPropertyValue();
        int SetPropertyValue();
        int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string deviceId, int role);
    }}

    [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDeviceEnumerator {{
        int EnumAudioEndpoints(int dataFlow, int stateMask, out IMMDeviceCollection devices);
    }}

    [Guid("0BD6A3BA-3330-4830-8964-0888B07D0E86"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDeviceCollection {{
        int GetCount(out uint count);
        int Item(uint index, out IMMDevice device);
    }}

    [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDevice {{
        int OpenPropertyStore(int stgmAccess, out IPropertyStore properties);
        int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
    }}

    [Guid("886D8EEB-8CF2-4446-8D02-CDA103045D7E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPropertyStore {{ }}

    [ComImport, Guid("BCDE0385-4944-460C-8564-65D99D075681")]
    public class MMDeviceEnumeratorComObject {{ }}

    public static void SetDefault(int targetIndex) {{
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
    }}
}}
"@
[AudioPolicy]::SetDefault({device_index})
"""
            subprocess.run(["powershell", "-Command", ps_policy_config], capture_output=True, timeout=10)
    except Exception as e:
        print(f"[-] set_audio_device error: {e}")

    return get_audio_devices()

def take_screenshot_bytes():
    try:
        screenshot = ImageGrab.grab(all_screens=True)
        # Convert / Resize if image is too huge for fast transfer over network
        # Max resolution bound 1920x1080 to send instantly
        screenshot.thumbnail((1920, 1080))
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG', optimize=True, quality=85)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"[-] Screenshot error: {e}")
        return None

def send_result(chat_id, text=None, screenshot_bytes=None, proc_list=None, audio_devices=None, msg_id=None):
    try:
        payload = {
            'agent_result': '1',
            'pc_id': PC_ID,
            'chat_id': chat_id,
        }
        if msg_id:
            payload['msg_id'] = msg_id
        if text:
            payload['text'] = text
        
        files = None
        if screenshot_bytes:
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
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        status_text = (
            f"📊 *СТАН ПК {PC_NAME}*\n"
            f"───────────────────────────\n"
            f"💻 *Завантаження ЦП:* `{cpu}%`\n"
            f"🧠 *ОЗП:* `{ram}%` 사용 중\n"
            f"🌐 *IP:* `{get_local_ip()}`\n"
            f"⏱️ *Час оновлення:* `{time.strftime('%H:%m:%S')}`"
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
            # Open browser tab, type query and search
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            os.system(f'start "" "{search_url}"')

    elif cmd_name == 'open_app':
        app = params.get('app')
        yt_url = params.get('yt_url')
        if app == 'ytmusic' and yt_url:
            os.system(f'start "" "{yt_url}"')
        elif app == 'comet':
            os.system('start "" "comet.exe"')
        elif app == 'discord':
            os.system('start "" "discord.exe"')
        elif app == 'steam':
            os.system('start "" "steam.exe"')

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
        # Send key to wake screen
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