"""Global hotkey through the Win32 RegisterHotKey API (PrtSc by default)."""
import ctypes
import sys
import winreg
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
MOD_NOREPEAT = 0x4000  # holding the key down fires only once
VK_SNAPSHOT = 0x2C  # the PrtSc key
VK_F1, VK_F12 = 0x70, 0x7B
HOTKEY_ID = 1

# A hotkey as stored in settings.json: Win32 key code, modifier flags, display name.
DEFAULT_HOTKEY = {"vk": VK_SNAPSHOT, "mods": 0, "name": "PrtSc"}

# Keys Windows would name after the number pad (e.g. PgDn -> "Num 3").
KEY_NAMES = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x20: "Space", 0x21: "PgUp", 0x22: "PgDn",
    0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2D: "Insert", 0x2E: "Delete", 0x13: "Pause",
}

user32 = ctypes.windll.user32
user32.GetKeyNameTextW.argtypes = [wintypes.LONG, wintypes.LPWSTR, ctypes.c_int]
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT


def is_allowed(vk, mods):
    """PrtSc and F1-F12 always; any other key needs Ctrl, Alt or Win
    (Shift alone would block typing, e.g. Shift+A)."""
    if vk == VK_SNAPSHOT or VK_F1 <= vk <= VK_F12:
        return True
    return bool(mods & (MOD_CONTROL | MOD_ALT | MOD_WIN))


def key_name(vk):
    if vk == VK_SNAPSHOT:
        return "PrtSc"
    if VK_F1 <= vk <= VK_F1 + 23:  # F1-F24
        return f"F{vk - VK_F1 + 1}"
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:  # 0-9, A-Z
        return chr(vk)
    if vk in KEY_NAMES:
        return KEY_NAMES[vk]
    # Anything else: ask Windows for the key's name (e.g. "Page Down", "-").
    scan = user32.MapVirtualKeyW(vk, 4)  # MAPVK_VK_TO_VSC_EX: 0xE0xx = extended key
    lparam = ((scan & 0xFF) << 16) | ((1 << 24) if scan & 0xFF00 else 0)
    buffer = ctypes.create_unicode_buffer(32)
    if user32.GetKeyNameTextW(lparam, buffer, 32):
        return buffer.value
    return f"Key {vk}"


def combo_name(vk, mods):
    """e.g. Ctrl+Shift+S"""
    parts = [name for flag, name in ((MOD_CONTROL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift"),
                                     (MOD_WIN, "Win")) if mods & flag]
    return "+".join(parts + [key_name(vk)])


def snipping_tool_owns_prtsc():
    """True if Windows is set to open Snipping Tool on PrtSc."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Keyboard")
        value, _ = winreg.QueryValueEx(key, "PrintScreenKeyForSnippingEnabled")
        winreg.CloseKey(key)
        return value == 1
    except OSError:
        # Not set: Windows 11 22H2 (build 22621) and later default to "on".
        return sys.getwindowsversion().build >= 22621


class GlobalHotkey(QAbstractNativeEventFilter):
    """Calls `on_press` every time the hotkey is pressed, from any app."""

    def __init__(self, app, on_press, hotkey):
        super().__init__()
        self.on_press = on_press
        self.hotkey = hotkey
        self.registered = False
        app.installNativeEventFilter(self)
        self.register()

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.on_press()
                return True, 0
        return False, 0

    def register(self):
        self.unregister()
        self.registered = bool(user32.RegisterHotKey(None, HOTKEY_ID, self.hotkey["mods"] | MOD_NOREPEAT,
                                                     self.hotkey["vk"]))
        return self.registered

    def unregister(self):
        if self.registered:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self.registered = False

    def change(self, hotkey):
        """Switch to `hotkey`. If Windows refuses it, keep the old one and return False."""
        old = self.hotkey
        self.hotkey = hotkey
        if self.register():
            return True
        self.hotkey = old
        self.register()
        return False

    # While Settings records a new combo, the current hotkey must not fire.
    pause = unregister
    resume = register
