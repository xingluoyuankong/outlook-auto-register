"""
OS-Level Input Module

Provides OS-native mouse/keyboard input to bypass browser automation detection.
On Windows: uses ctypes Win32 API (SendInput).
On Linux: uses xdotool.

This is the key difference from Selenium's ActionChains which goes through
the WebDriver protocol and is detectable by anti-bot systems.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import platform
import random
import subprocess
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# ── Windows SendInput structures ──
if IS_WINDOWS:
    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_ABSOLUTE = 0x8000
    KEYEVENTF_KEYUP = 0x0002

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.wintypes.LONG),
            ("dy", ctypes.wintypes.LONG),
            ("mouseData", ctypes.wintypes.DWORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.wintypes.WORD),
            ("wScan", ctypes.wintypes.WORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.wintypes.DWORD),
            ("union", _INPUT_UNION),
        ]

    def _send_input(*inputs: INPUT):
        n = len(inputs)
        array = (INPUT * n)(*inputs)
        ctypes.windll.user32.SendInput(n, ctypes.byref(array), ctypes.sizeof(INPUT))

    def _get_screen_size() -> tuple[int, int]:
        return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)

    def _move_to(x: int, y: int):
        """Move mouse to absolute screen coordinates."""
        screen_w, screen_h = _get_screen_size()
        # Convert to 0-65535 range
        abs_x = int(x * 65535 / screen_w)
        abs_y = int(y * 65535 / screen_h)
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = abs_x
        inp.union.mi.dy = abs_y
        inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        _send_input(inp)

    def _mouse_down(button: str = "left"):
        inp = INPUT()
        inp.type = INPUT_MOUSE
        flag = MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN
        inp.union.mi.dwFlags = flag
        _send_input(inp)

    def _mouse_up(button: str = "left"):
        inp = INPUT()
        inp.type = INPUT_MOUSE
        flag = MOUSEEVENTF_LEFTUP if button == "left" else MOUSEEVENTF_RIGHTUP
        inp.union.mi.dwFlags = flag
        _send_input(inp)

    def _key_down(vk: int):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        _send_input(inp)

    def _key_up(vk: int):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.dwFlags = KEYEVENTF_KEYUP
        _send_input(inp)


def os_click(x: float, y: float, button: str = "left"):
    """
    Click at screen coordinates using OS-native input.
    This bypasses all browser-level automation detection.
    """
    x, y = int(x), int(y)
    logger.debug("[OS_INPUT] Click at (%d, %d) button=%s", x, y, button)

    if IS_WINDOWS:
        _move_to(x, y)
        time.sleep(random.uniform(0.02, 0.06))
        _mouse_down(button)
        time.sleep(random.uniform(0.03, 0.08))
        _mouse_up(button)
    elif IS_LINUX:
        button_map = {"left": "1", "middle": "2", "right": "3"}
        btn = button_map.get(button, "1")
        subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=False)
        time.sleep(random.uniform(0.02, 0.06))
        subprocess.run(["xdotool", "click", btn], check=False)
    else:
        raise RuntimeError(f"Unsupported OS: {platform.system()}")


def os_long_press(x: float, y: float, duration: float = 3.5):
    """
    Long-press at screen coordinates using OS-native input.
    Used for hsprotect CAPTCHA (press-and-hold).
    """
    x, y = int(x), int(y)
    actual_duration = duration + random.uniform(-0.3, 0.5)
    actual_duration = max(2.0, actual_duration)

    logger.info("[OS_INPUT] Long-press at (%d, %d) for %.1fs", x, y, actual_duration)

    if IS_WINDOWS:
        _move_to(x, y)
        time.sleep(random.uniform(0.05, 0.15))
        _mouse_down("left")
        time.sleep(actual_duration)
        _mouse_up("left")
    elif IS_LINUX:
        subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=False)
        time.sleep(random.uniform(0.05, 0.15))
        subprocess.run(["xdotool", "mousedown", "1"], check=False)
        time.sleep(actual_duration)
        subprocess.run(["xdotool", "mouseup", "1"], check=False)

    logger.info("[OS_INPUT] Long-press completed")


def os_type_text(text: str, delay_ms: int = 80):
    """Type text using OS-native keyboard input."""
    logger.debug("[OS_INPUT] Type text (%d chars)", len(text))

    if IS_WINDOWS:
        for char in text:
            vk = _char_to_vk(char)
            if vk:
                _key_down(vk)
                time.sleep(random.uniform(delay_ms * 0.5, delay_ms * 1.5) / 1000)
                _key_up(vk)
            else:
                # Fallback: use Unicode input
                _type_unicode_char(char)
                time.sleep(random.uniform(delay_ms * 0.5, delay_ms * 1.5) / 1000)
    elif IS_LINUX:
        subprocess.run(["xdotool", "type", "--delay", str(delay_ms), text], check=False)


def os_press_enter():
    """Press Enter key."""
    if IS_WINDOWS:
        vk = 0x0D  # VK_RETURN
        _key_down(vk)
        time.sleep(0.05)
        _key_up(vk)
    elif IS_LINUX:
        subprocess.run(["xdotool", "key", "Return"], check=False)


def os_press_tab():
    """Press Tab key."""
    if IS_WINDOWS:
        vk = 0x09  # VK_TAB
        _key_down(vk)
        time.sleep(0.05)
        _key_up(vk)
    elif IS_LINUX:
        subprocess.run(["xdotool", "key", "Tab"], check=False)


def os_press_escape():
    """Press Escape key."""
    if IS_WINDOWS:
        vk = 0x1B  # VK_ESCAPE
        _key_down(vk)
        time.sleep(0.05)
        _key_up(vk)
    elif IS_LINUX:
        subprocess.run(["xdotool", "key", "Escape"], check=False)


def os_dismiss_webauthn_dialog(timeout: float = 5.0) -> bool:
    """
    Dismiss the Windows WebAuthn / Passkey system dialog.
    
    The Windows WebAuthn dialog (triggered by navigator.credentials.create())
    is a system-level modal that JS/CDP cannot interact with.
    
    Strategy:
    1. Find the "Windows Security" / "Windows 安全中心" dialog window via Win32 API
    2. Send WM_CLOSE or press Escape specifically to that window
    3. If window not found, fall back to sending Escape to foreground window
    
    Returns True if dialog was found and dismissed, False otherwise.
    """
    if not IS_WINDOWS:
        return False
    
    import ctypes.wintypes
    
    # Win32 API constants
    WM_CLOSE = 0x0010
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    VK_ESCAPE = 0x1B
    
    user32 = ctypes.windll.user32
    
    # Callback for EnumWindows - find the WebAuthn dialog
    found_hwnd = []
    
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def enum_callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        
        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        
        # Get window class name
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        cls = cls_buf.value
        
        # Match Windows Security / WebAuthn dialog
        # Class: "Credential Dialog Xaml Host" or "#32770" (standard dialog)
        # Title: "Windows Security", "Windows 安全中心", "Windows Hello", etc.
        title_lower = title.lower()
        is_webauthn = (
            # Known WebAuthn dialog class
            cls in ("Credential Dialog Xaml Host", "Credential Dialog Xaml Host Window", 
                    "#32770", "WindowsForms10.Window") or
            # Known dialog titles
            "windows security" in title_lower or
            "windows 安全" in title_lower or
            "windows hello" in title_lower or
            "passkey" in title_lower or
            "通行密钥" in title_lower or
            "security key" in title_lower or
            "选择保存通行密钥" in title_lower or
            "保存通行密钥" in title_lower
        )
        
        # Also check: it must be a dialog/popup, not a main window
        # WebAuthn dialogs are typically small (< 800x600)
        if is_webauthn:
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            # WebAuthn dialog is typically 400-700px wide and 300-600px tall
            if 200 < w < 900 and 150 < h < 800:
                logger.info("[OS_INPUT] Found WebAuthn dialog: title='%s' class='%s' size=%dx%d",
                           title[:50], cls, w, h)
                found_hwnd.append(hwnd)
                return True  # Keep looking in case there are multiple
        
        return True
    
    deadline = time.monotonic() + timeout
    
    while time.monotonic() < deadline:
        found_hwnd.clear()
        user32.EnumWindows(enum_callback, 0)
        
        if found_hwnd:
            for hwnd in found_hwnd:
                # Strategy 1: Send WM_CLOSE to the dialog
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                logger.info("[OS_INPUT] Sent WM_CLOSE to WebAuthn dialog hwnd=%d", hwnd)
            
            time.sleep(0.5)
            
            # Check if dialog was closed
            still_visible = any(user32.IsWindowVisible(h) for h in found_hwnd)
            if not still_visible:
                logger.info("[OS_INPUT] WebAuthn dialog dismissed successfully")
                return True
            
            # If still visible, try sending Escape to that specific window
            for hwnd in found_hwnd:
                user32.PostMessageW(hwnd, WM_KEYDOWN, VK_ESCAPE, 0)
                time.sleep(0.05)
                user32.PostMessageW(hwnd, WM_KEYUP, VK_ESCAPE, 0)
                logger.info("[OS_INPUT] Sent Escape to WebAuthn dialog hwnd=%d", hwnd)
            
            time.sleep(0.5)
            
            still_visible = any(user32.IsWindowVisible(h) for h in found_hwnd)
            if not still_visible:
                logger.info("[OS_INPUT] WebAuthn dialog dismissed via Escape")
                return True
            
            # Last resort: Tab to "Cancel" button + Enter
            for hwnd in found_hwnd:
                # Set foreground and send Tab + Enter
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.2)
            
            _key_down(0x09)  # VK_TAB
            time.sleep(0.05)
            _key_up(0x09)
            time.sleep(0.2)
            _key_down(0x0D)  # VK_RETURN
            time.sleep(0.05)
            _key_up(0x0D)
            time.sleep(0.5)
            
            still_visible = any(user32.IsWindowVisible(h) for h in found_hwnd)
            if not still_visible:
                logger.info("[OS_INPUT] WebAuthn dialog dismissed via Tab+Enter")
                return True
            
            logger.warning("[OS_INPUT] WebAuthn dialog still visible after all attempts")
            return False
        
        # Dialog not found yet, wait and retry
        time.sleep(0.5)
    
    # Dialog never appeared or was already dismissed
    logger.info("[OS_INPUT] No WebAuthn dialog found (timeout=%.0fs)", timeout)
    return False


def _char_to_vk(char: str) -> int | None:
    """Convert character to Windows Virtual Key code."""
    char_map = {
        'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
        'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
        'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
        'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
        'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59,
        'z': 0x5A,
        '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
        '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
        ' ': 0x20, '-': 0xBD, '=': 0xBB, '[': 0xDB, ']': 0xDD,
        '\\': 0xDC, ';': 0xBA, "'": 0xDE, ',': 0xBC, '.': 0xBE,
        '/': 0xBF, '`': 0xC0,
    }
    lower = char.lower()
    if lower in char_map:
        vk = char_map[lower]
        # Handle shift for uppercase and symbols
        if char.isupper() or char in '!@#$%^&*()_+{}|:"<>?~':
            shift_chars = {
                '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
                '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
                '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\',
                ':': ';', '"': "'", '<': ',', '>': '.', '?': '/',
                '~': '`',
            }
            if char in shift_chars:
                vk = char_map.get(shift_chars[char])
            if vk:
                _key_down(0xA0)  # VK_LSHIFT
                _key_down(vk)
                _key_up(vk)
                _key_up(0xA0)
                return None  # Already handled
        return vk
    return None


def _type_unicode_char(char: str):
    """Type a Unicode character using SendInput with KEYEVENTF_UNICODE."""
    if not IS_WINDOWS:
        return

    for code_point in [ord(char)]:
        # Key down with Unicode
        inp_down = INPUT()
        inp_down.type = INPUT_KEYBOARD
        inp_down.union.ki.wVk = 0
        inp_down.union.ki.wScan = code_point
        inp_down.union.ki.dwFlags = 0x0004  # KEYEVENTF_UNICODE

        inp_up = INPUT()
        inp_up.type = INPUT_KEYBOARD
        inp_up.union.ki.wVk = 0
        inp_up.union.ki.wScan = code_point
        inp_up.union.ki.dwFlags = 0x0004 | KEYEVENTF_KEYUP  # KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

        _send_input(inp_down, inp_up)


@dataclass
class ScreenCoords:
    """Screen coordinates with confidence."""
    x: float
    y: float
    width: float = 0
    height: float = 0


def browser_to_screen_coords(browser_x: float, browser_y: float,
                              browser_width: float, browser_height: float,
                              window_x: int = 0, window_y: int = 0,
                              device_pixel_ratio: float = 1.0) -> ScreenCoords:
    """
    Convert browser viewport coordinates to screen coordinates.
    
    Args:
        browser_x, browser_y: Element position in browser viewport
        browser_width, browser_height: Element size in browser viewport
        window_x, window_y: Browser window position on screen
        device_pixel_ratio: Display scaling factor
    """
    # Account for window chrome (title bar, borders)
    CHROME_HEIGHT = 85  # Approximate Chrome title bar + tab bar
    BORDER_WIDTH = 0

    screen_x = window_x + BORDER_WIDTH + browser_x * device_pixel_ratio
    screen_y = window_y + CHROME_HEIGHT + browser_y * device_pixel_ratio

    return ScreenCoords(
        x=screen_x,
        y=screen_y,
        width=browser_width * device_pixel_ratio,
        height=browser_height * device_pixel_ratio,
    )


def get_browser_window_position(debug_port: int = 0) -> tuple[int, int]:
    """Get the position of the Chrome browser window on screen.
    
    并发安全: 如果指定 debug_port，只返回监听该端口的 Chrome 窗口位置。
    """
    if IS_WINDOWS:
        try:
            import subprocess
            if debug_port > 0:
                # 按 debug port 查找特定 Chrome 进程的窗口
                ps_cmd = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    f"$cmdline = (Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                    f"Where-Object {{$_.CommandLine -like '*remote-debugging-port={debug_port}*'}}).ProcessId; "
                    f"if ($cmdline) {{ "
                    f"  $p = Get-Process -Id $cmdline -ErrorAction SilentlyContinue; "
                    f"  if ($p -and $p.MainWindowHandle -ne 0) {{ "
                    f"    $rect = New-Object System.Drawing.Rectangle; "
                    f"    [Win32]::GetWindowRect($p.MainWindowHandle, [ref]$rect); "
                    f"    Write-Output \"$($rect.X),$($rect.Y)\" "
                    f"  }} "
                    f"}} else {{ Write-Output '0,0' }}"
                )
                result = subprocess.run(
                    ["powershell", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=5
                )
            else:
                # 原始行为: 找第一个 Chrome 窗口
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Add-Type -AssemblyName System.Windows.Forms; "
                     "$p = Get-Process chrome -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowHandle -ne 0} | Select-Object -First 1; "
                     "if ($p) { "
                     "  $rect = New-Object System.Drawing.Rectangle; "
                     "  [Win32]::GetWindowRect($p.MainWindowHandle, [ref]$rect); "
                     "  Write-Output \"$($rect.X),$($rect.Y)\" "
                     "} else { Write-Output '0,0' }"],
                    capture_output=True, text=True, timeout=5
                )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) == 2:
                    return int(parts[0]), int(parts[1])
        except Exception:
            pass
    return 0, 0
