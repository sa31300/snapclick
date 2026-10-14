"""Snapclick entry point. Run with: python -m snapclick"""
import ctypes
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from snapclick import settings
from snapclick.hotkey import PrtScHotkey, snipping_tool_owns_prtsc
from snapclick.tray import Tray

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
    "the PrtSc key, so Snapclick can't use it.\n\n"
    "Close that app or change its hotkey, then restart Snapclick.\n\n"
    "Until then, left-click the Snapclick tray icon to capture."
)


def already_running():
    """A named mutex exists only once per user session."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, r"Local\SnapclickSingleInstance")
    return kernel32.GetLastError() == ERROR_ALREADY_EXISTS


def warn_once_if_prtsc_taken(hotkey):
    """Explain how to free PrtSc. Shown only the first time."""
    if snipping_tool_owns_prtsc():
        text = SNIPPING_TOOL_HELP
    elif not hotkey.registered:
        text = OTHER_APP_HELP
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

    app.setQuitOnLastWindowClosed(False)  # tray app: keep running with no windows
    tray = Tray(app)
    tray.show()

    hotkey = PrtScHotkey(app, tray.start_capture)
    app.aboutToQuit.connect(hotkey.unregister)
    warn_once_if_prtsc_taken(hotkey)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
