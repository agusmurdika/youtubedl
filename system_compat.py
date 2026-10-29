#!/usr/bin/env python3
"""
Cross-Platform System Compatibility Module
Ensures seamless execution across Windows, macOS, and Linux desktop environments.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import shutil
import platform
import subprocess
from typing import Dict, Any


def init_system():
    """
    Initializes terminal encoding to UTF-8 and enables ANSI color
    processing on Windows terminals (cmd.exe / PowerShell).
    """
    # 1. Force UTF-8 stdout/stderr to prevent charmap encoding errors on Windows
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # 2. Enable Windows 10/11 Virtual Terminal Processing for ANSI colors
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # STD_OUTPUT_HANDLE = -11, STD_ERROR_HANDLE = -12
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            for handle_id in (-11, -12):
                h = kernel32.GetStdHandle(handle_id)
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(h, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
        except Exception:
            pass


def get_os_info() -> Dict[str, Any]:
    """
    Detects detailed host operating system information, architecture,
    desktop session, and availability of system utilities.
    """
    sys_name = platform.system()
    machine = platform.machine() or "unknown"

    if sys_name == "Windows":
        os_type = "Windows"
        release = platform.release()
        os_name = f"Windows {release} ({machine})"
        desktop_env = "Windows Desktop"
        clip_backend = "Win32 API (Native Ctypes)"
        notif_backend = "Windows Toast Notification"
    elif sys_name == "Darwin":
        os_type = "macOS"
        mac_ver = platform.mac_ver()[0] or platform.release()
        os_name = f"macOS {mac_ver} ({machine})"
        desktop_env = "Aqua"
        clip_backend = "pbpaste (macOS)"
        notif_backend = "macOS Notification Center"
    elif sys_name == "Linux":
        os_type = "Linux"
        distro = "Linux"
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            distro = line.split("=", 1)[1].strip().strip('"')
                            break
        except Exception:
            pass
        os_name = f"{distro} ({machine})"
        is_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        is_x11 = bool(os.environ.get("DISPLAY"))
        desktop_env = "Wayland" if is_wayland else ("X11" if is_x11 else "Headless/TTY")

        if is_wayland and shutil.which("wl-paste"):
            clip_backend = "wl-paste (Wayland)"
        elif shutil.which("xclip"):
            clip_backend = "xclip (X11)"
        elif shutil.which("xsel"):
            clip_backend = "xsel (X11)"
        elif shutil.which("wl-paste"):
            clip_backend = "wl-paste"
        else:
            clip_backend = "Tkinter / Generic"

        notif_backend = "notify-send (Desktop)" if shutil.which("notify-send") else "Nonaktif"
    else:
        os_type = sys_name
        os_name = f"{sys_name} ({machine})"
        desktop_env = "Unknown"
        clip_backend = "Generic"
        notif_backend = "Nonaktif"

    # Check FFmpeg and FFprobe
    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    ffmpeg_ok = bool(ffmpeg_bin and ffprobe_bin)
    ffmpeg_ver = "Tidak ditemukan"
    if ffmpeg_ok:
        try:
            res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=2)
            first_line = res.stdout.split("\n")[0] if res.stdout else ""
            parts = first_line.split()
            if len(parts) >= 3:
                ffmpeg_ver = parts[2]
            else:
                ffmpeg_ver = "Terpasang"
        except Exception:
            ffmpeg_ver = "Terpasang"

    return {
        "os_type": os_type,
        "os_name": os_name,
        "machine": machine,
        "desktop_env": desktop_env,
        "clip_backend": clip_backend,
        "notif_backend": notif_backend,
        "ffmpeg_available": ffmpeg_ok,
        "ffmpeg_version": ffmpeg_ver,
    }


def get_clipboard_text() -> str:
    """
    Reads clipboard text quickly and reliably across Windows, macOS, and Linux.
    """
    sys_name = platform.system()

    # 1. Windows: Native Win32 API via ctypes (instant, 0% CPU, no cmd window popup)
    if sys_name == "Windows":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            CF_UNICODETEXT = 13
            if user32.OpenClipboard(None):
                try:
                    h_glb = user32.GetClipboardData(CF_UNICODETEXT)
                    if h_glb:
                        kernel32.GlobalLock.restype = ctypes.c_void_p
                        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                        p_data = kernel32.GlobalLock(h_glb)
                        if p_data:
                            try:
                                text = ctypes.c_wchar_p(p_data).value or ""
                                return text.strip()
                            finally:
                                kernel32.GlobalUnlock(h_glb)
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

        # Fallback via PowerShell
        if shutil.which("powershell.exe") or shutil.which("powershell"):
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                    capture_output=True, text=True, timeout=1
                )
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass

    # 2. macOS: pbpaste
    elif sys_name == "Darwin":
        if shutil.which("pbpaste"):
            try:
                res = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass

    # 3. Linux / BSD: Wayland & X11
    else:
        # Wayland
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
            try:
                res = subprocess.run(["wl-paste", "-n"], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass

        # X11 xclip
        if shutil.which("xclip"):
            try:
                res = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, text=True, timeout=1
                )
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass

        # X11 xsel
        if shutil.which("xsel"):
            try:
                res = subprocess.run(
                    ["xsel", "--clipboard", "-o"],
                    capture_output=True, text=True, timeout=1
                )
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass

        # Fallback to wl-paste even if WAYLAND_DISPLAY not set
        if shutil.which("wl-paste"):
            try:
                res = subprocess.run(["wl-paste", "-n"], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass

    # 4. Universal Fallback: tkinter
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        text = r.clipboard_get()
        r.destroy()
        return text.strip()
    except Exception:
        pass

    return ""


def send_notification(title: str, message: str, urgency: str = "normal", expire_ms: int = 4000):
    """
    Sends native desktop notification across Windows, macOS, and Linux.
    """
    sys_name = platform.system()

    # 1. Linux / BSD: notify-send
    if sys_name == "Linux" or sys_name.startswith("FreeBSD"):
        if shutil.which("notify-send"):
            cmd = [
                "notify-send",
                "-a", "YouTube Downloader",
                "-u", urgency,
                "-t", str(expire_ms),
                "-i", "video-x-generic",
                title,
                message
            ]
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass

    # 2. macOS: AppleScript osascript
    elif sys_name == "Darwin":
        if shutil.which("osascript"):
            clean_title = title.replace('"', '\\"')
            clean_msg = message.replace('"', '\\"')
            script = f'display notification "{clean_msg}" with title "{clean_title}"'
            try:
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return
            except Exception:
                pass

    # 3. Windows: PowerShell Toast / Balloon Tip
    elif sys_name == "Windows":
        ps_bin = shutil.which("powershell.exe") or shutil.which("powershell")
        if ps_bin:
            safe_title = title.replace('"', '`"').replace("'", "''")
            safe_msg = message.replace('"', '`"').replace("'", "''")
            ps_cmd = (
                '[reflection.assembly]::loadwithpartialname("System.Windows.Forms") | Out-Null; '
                '$n = New-Object System.Windows.Forms.NotifyIcon; '
                '$n.Icon = [System.Drawing.SystemIcons]::Information; '
                '$n.Visible = $true; '
                f'$n.ShowBalloonTip({expire_ms}, "{safe_title}", "{safe_msg}", [System.Windows.Forms.ToolTipIcon]::Info);'
            )
            try:
                subprocess.Popen(
                    [ps_bin, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return
            except Exception:
                pass


def open_in_browser(url: str):
    """
    Opens URL in the default desktop web browser cross-platform.
    """
    import webbrowser
    try:
        if webbrowser.open(url):
            return
    except Exception:
        pass

    sys_name = platform.system()
    try:
        if sys_name == "Windows":
            os.startfile(url)
        elif sys_name == "Darwin":
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


_TITLE_CACHE: Dict[str, str] = {}
_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads", ".title_cache.json")


def sanitize_filename(name: str) -> str:
    """
    Sanitizes string for cross-platform file system compatibility (Windows/NTFS/exFAT/Linux/macOS).
    Replaces illegal characters with safe equivalents.
    """
    replacements = {
        "/": "-",
        "\\": "-",
        ":": " -",
        "*": "",
        "?": "？",
        "\"": "'",
        "<": "(",
        ">": ")",
        "|": "-",
    }
    res = name
    for bad, good in replacements.items():
        res = res.replace(bad, good)
    # Remove leading/trailing spaces and dots
    res = res.strip(" .")
    # Collapse consecutive spaces
    res = re.sub(r'\s+', ' ', res)
    return res or "Video"


def _load_title_cache():
    global _TITLE_CACHE
    if os.path.isfile(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                _TITLE_CACHE = json.load(f)
        except Exception:
            _TITLE_CACHE = {}


def _save_title_cache():
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        tmp = _CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_TITLE_CACHE, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _CACHE_PATH)
    except Exception:
        pass


def translate_to_indonesian(text: str) -> str:
    """
    Translates title/text to Indonesian using Google Translate API.
    Uses local cache to minimize network calls and ensure 0ms latency on repeat calls.
    Returns original text if translation fails or if text is already Indonesian.
    """
    if not text or not text.strip():
        return text

    clean_text = text.strip()

    if not _TITLE_CACHE:
        _load_title_cache()

    if clean_text in _TITLE_CACHE:
        return _TITLE_CACHE[clean_text]

    try:
        encoded = urllib.parse.quote(clean_text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=id&dt=t&q={encoded}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            translated = "".join([part[0] for part in data[0] if part and part[0]]).strip()
            if translated:
                _TITLE_CACHE[clean_text] = translated
                _save_title_cache()
                return translated
    except Exception:
        pass

    return clean_text

