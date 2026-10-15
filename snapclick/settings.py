r"""Settings stored in %APPDATA%\Snapclick\settings.json, plus the helpers
that act on them (file names, start with Windows).

Test runs set SNAPCLICK_SETTINGS to another settings file. Then the Windows
startup list is never touched."""
import json
import os
import sys
import winreg
from datetime import datetime
from pathlib import Path

from snapclick.hotkey import DEFAULT_HOTKEY

TEST_SETTINGS = os.environ.get("SNAPCLICK_SETTINGS")  # test runs only
SETTINGS_FILE = Path(TEST_SETTINGS or Path(os.environ["APPDATA"]) / "Snapclick" / "settings.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULTS = {
    "auto_save": False,
    "save_folder": str(Path(os.environ["USERPROFILE"]) / "Pictures" / "Snapclick"),
    "format": "png",  # "png" or "jpg"
    "show_preview": False,
    "start_with_windows": False,
    "hotkey": DEFAULT_HOTKEY,  # fixed to PrtSc (see load)
}


def load():
    """Saved settings on top of the defaults."""
    settings = dict(DEFAULTS)
    try:
        settings.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    settings["hotkey"] = DEFAULT_HOTKEY  # the hotkey is not editable; ignore any saved one
    return settings


def save(settings):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def file_name(when, fmt):
    """e.g. 2026-10-14_18-12-05.png"""
    return when.strftime("%Y-%m-%d_%H-%M-%S") + "." + fmt


def new_file_path(folder, fmt, when=None):
    """A free file path in `folder`; adds _2, _3 if the second is already taken."""
    stem = Path(file_name(when or datetime.now(), fmt)).stem
    path = Path(folder) / f"{stem}.{fmt}"
    n = 2
    while path.exists():
        path = Path(folder) / f"{stem}_{n}.{fmt}"
        n += 1
    return path


def start_command():
    """The command Windows runs at sign-in to start Snapclick."""
    if getattr(sys, "frozen", False):  # the packaged .exe
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")  # no console window
    return f'"{pythonw}" "{Path(__file__).with_name("__main__.py")}"'


def set_start_with_windows(on):
    """Add or remove Snapclick in the Windows startup list.
    Returns False if Windows (or an antivirus) blocked it."""
    if TEST_SETTINGS:
        return True  # test run: only the test file changes
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, "Snapclick", 0, winreg.REG_SZ, start_command())
            else:
                try:
                    winreg.DeleteValue(key, "Snapclick")
                except FileNotFoundError:
                    pass
    except OSError:
        return False
    return True
