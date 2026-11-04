r"""Build dist\Snapclick.exe (one file, no Python needed on the target PC).

    .venv\Scripts\pip install -r requirements-dev.txt
    .venv\Scripts\python build.py
"""
import os
import struct
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication

from snapclick.tray import DARK_TASKBAR_COLOR, draw_brackets

ROOT = Path(__file__).resolve().parent
ICON = ROOT / "build" / "snapclick.ico"
# 16-32 for the tray/taskbar (spec), 48 and 256 for Explorer's bigger views.
ICON_SIZES = (16, 20, 24, 32, 48, 256)


def build_environment():
    """Keep unrelated tools' DLLs out of the packaged app."""
    env = dict(os.environ)
    windows = Path(os.environ["SystemRoot"])
    env["PATH"] = os.pathsep.join((str(Path(sys.executable).parent), sys.base_prefix,
                                  str(windows / "System32"), str(windows)))
    env["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build" / "pyinstaller-cache")
    return env


def make_ico(path):
    """Write a .ico with one hand-drawn image per size, so every size is crisp."""
    images = []
    for size in ICON_SIZES:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        draw_brackets(size, DARK_TASKBAR_COLOR).save(buffer, "PNG")
        images.append((size, bytes(buffer.data())))

    header = struct.pack("<HHH", 0, 1, len(images))  # reserved, type 1 = icon, count
    offset = len(header) + 16 * len(images)
    entries, data = b"", b""
    for size, png in images:
        side = size % 256  # 0 means 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(header + entries + data)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    make_ico(ICON)
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "snapclick" / "__main__.py"),
        "--name", "Snapclick",
        "--onefile",
        "--windowed",  # no console window
        "--icon", str(ICON),
        "--add-data", f"{ROOT / 'snapclick' / 'fonts'};fonts",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--noconfirm",
        "--clean",
    ], env=build_environment(), check=True)
