"""Global PrtSc hotkey through the Win32 RegisterHotKey API."""
import ctypes
import sys
import winreg
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
VK_SNAPSHOT = 0x2C  # the PrtSc key
MOD_NOREPEAT = 0x4000  # holding the key down fires only once
HOTKEY_ID = 1

user32 = ctypes.windll.user32


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


class PrtScHotkey(QAbstractNativeEventFilter):
    """Calls `on_press` every time PrtSc is pressed, from any app."""

    def __init__(self, app, on_press):
        super().__init__()
        self.on_press = on_press
        self.registered = bool(user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, VK_SNAPSHOT))
        app.installNativeEventFilter(self)

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.on_press()
                return True, 0
        return False, 0

    def unregister(self):
        if self.registered:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self.registered = False
