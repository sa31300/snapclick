"""Snapclick entry point. Run with: python -m snapclick"""
import ctypes
import sys
from pathlib import Path

if not __package__:  # started as a plain script (Start with Windows, .exe)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox

from snapclick import settings
from snapclick.hotkey import VK_SNAPSHOT, GlobalHotkey, snipping_tool_owns_prtsc
from snapclick.tray import Tray, make_icon

ERROR_ALREADY_EXISTS = 183

SNIPPING_TOOL_HELP = (
    "Windows is using the PrtSc key for its own Snipping Tool, "
    "so Snapclick can't use it.\n\n"
    "To fix it, open:\n"
    "Settings → Accessibility → Keyboard →\n"
    "\"Use the Print screen key to open screen capture\" → Off\n\n"
    "Until then, left-click the Snapclick tray icon to capture."
)

OTHER_APP_HELP = (
    "Another app (for example Greenshot, ShareX or Lightshot) is already using "
    "{name}, so Snapclick can't use it.\n\n"
    "Pick another hotkey in Snapclick → Settings, or close that app and restart Snapclick.\n\n"
    "Until then, left-click the Snapclick tray icon to capture."
)


def load_fonts():
    """Register the bundled fonts so the app looks the same on every PC."""
    for font_file in (Path(__file__).parent / "fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font_file))


def already_running():
    """A named mutex exists only once per user session."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, r"Local\SnapclickSingleInstance")
    return kernel32.GetLastError() == ERROR_ALREADY_EXISTS


def warn_once_if_hotkey_taken(hotkey):
    """Explain how to free the hotkey. Shown only the first time."""
    is_prtsc = hotkey.hotkey["vk"] == VK_SNAPSHOT and hotkey.hotkey["mods"] == 0
    if is_prtsc and snipping_tool_owns_prtsc():
        text = SNIPPING_TOOL_HELP
    elif not hotkey.registered:
        text = OTHER_APP_HELP.format(name=hotkey.hotkey["name"])
    else:
        return
    prefs = settings.load()
    if prefs.get("prtsc_warning_shown"):
        return
    QMessageBox.information(None, "Snapclick", text)
    prefs["prtsc_warning_shown"] = True
    settings.save(prefs)


def main():
    app = QApplication(sys.argv)
    if already_running():
        QMessageBox.information(None, "Snapclick", "Snapclick is already running (see the tray).")
        return

    load_fonts()
    app.setWindowIcon(make_icon(light=False))  # amber icon for windows (dark title bars)
    app.setQuitOnLastWindowClosed(False)  # tray app: keep running with no windows
    tray = Tray(app)
    tray.show()

    tray.hotkey = GlobalHotkey(app, tray.start_capture, settings.load()["hotkey"])
    tray.update_tooltip()
    app.aboutToQuit.connect(tray.hotkey.unregister)
    warn_once_if_hotkey_taken(tray.hotkey)
    if settings.load()["start_with_windows"]:
        settings.set_start_with_windows(True)  # keep the path current if the app moved

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
