"""Settings window (style B). Every change is saved immediately."""
import ctypes
from datetime import datetime

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QVBoxLayout, QWidget)

from snapclick import settings

# Design tokens (docs/SPEC.md, section 5)
BACKGROUND = "#0D0E10"
PANEL = "#15161A"
BORDER = "#2E3035"
DIVIDER = "#24262A"
TEXT = "#E7E7E4"
TEXT_MUTED = "#A3A39E"
ACCENT = "#FFB000"

STYLE = f"""
QWidget {{ background: {BACKGROUND}; color: {TEXT}; font-family: "IBM Plex Sans"; font-size: 13px; }}
QLabel {{ background: transparent; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDER}; }}
QFrame#divider {{ background: {DIVIDER}; border: none; max-height: 1px; min-height: 1px; }}
QLabel#title {{ font-size: 15px; font-weight: 500; }}
QLabel#muted {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#mono, QLabel#chip {{ font-family: "JetBrains Mono"; font-size: 12px; color: {TEXT_MUTED}; }}
QLabel#chip {{ color: {TEXT}; border: 1px solid {BORDER}; padding: 2px 8px; background: {BACKGROUND}; }}
QLineEdit {{ background: {BACKGROUND}; border: 1px solid {BORDER}; border-radius: 0; padding: 4px 6px;
             font-family: "JetBrains Mono"; font-size: 12px; }}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QPushButton {{ background: {BACKGROUND}; border: 1px solid {BORDER}; border-radius: 0; padding: 4px 10px; }}
QPushButton:hover {{ border-color: {TEXT_MUTED}; }}
QPushButton:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: black; font-weight: 500; }}
"""


class Toggle(QAbstractButton):
    """A square on/off switch."""

    def __init__(self, checked):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        return QSize(34, 18)

    def paintEvent(self, event):
        p = QPainter(self)
        track = QRect(0, 0, 34, 18)
        knob = QRect(0, 0, 12, 12)
        if self.isChecked():
            p.fillRect(track, QColor(ACCENT))
            knob.moveTo(track.right() - 14, 3)
            p.fillRect(knob, QColor(BACKGROUND))
        else:
            p.fillRect(track, QColor(BACKGROUND))
            p.setPen(QColor(BORDER))
            p.drawRect(track.adjusted(0, 0, -1, -1))
            knob.moveTo(3, 3)
            p.fillRect(knob, QColor(TEXT_MUTED))


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.prefs = settings.load()
        self.setWindowTitle("Snapclick settings")
        self.setStyleSheet(STYLE)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)

        title = QLabel("Settings")
        title.setObjectName("title")

        panel = QFrame()
        panel.setObjectName("panel")
        rows = QVBoxLayout(panel)
        rows.setContentsMargins(14, 6, 14, 6)
        rows.setSpacing(0)

        # Auto-save
        self.auto_save = Toggle(self.prefs["auto_save"])
        self.auto_save.toggled.connect(lambda on: self.set("auto_save", on))
        self.add_row(rows, "Auto-save each capture", self.auto_save)

        # Save folder: text + Browse
        self.folder = QLineEdit(self.prefs["save_folder"])
        self.folder.setCursorPosition(0)  # show the start of the path
        self.folder.editingFinished.connect(lambda: self.set("save_folder", self.folder.text().strip()))
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        self.add_row(rows, "Save folder", folder_row, stacked=True)

        # File name preview
        self.file_name = QLabel()
        self.file_name.setObjectName("mono")
        self.add_row(rows, "File name", self.file_name)

        # Format: PNG / JPG
        format_row = QHBoxLayout()
        format_row.setSpacing(0)
        self.formats = QButtonGroup(self)
        for fmt in ("png", "jpg"):
            button = QPushButton(fmt.upper())
            button.setCheckable(True)
            button.setChecked(self.prefs["format"] == fmt)
            button.clicked.connect(lambda _, f=fmt: self.set("format", f))
            self.formats.addButton(button)
            format_row.addWidget(button)
        self.add_row(rows, "Format", format_row)

        # Hotkey (not editable in v1)
        chip = QLabel("PrtSc")
        chip.setObjectName("chip")
        self.add_row(rows, "Hotkey", chip)

        # Preview
        preview = Toggle(self.prefs["show_preview"])
        preview.toggled.connect(lambda on: self.set("show_preview", on))
        self.add_row(rows, "Show preview after capture", preview)

        # Start with Windows
        startup = Toggle(self.prefs["start_with_windows"])
        startup.toggled.connect(self.set_startup)
        self.add_row(rows, "Start with Windows", startup, last=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(panel)
        hint = QLabel("Changes are saved automatically.")
        hint.setObjectName("muted")
        layout.addWidget(hint)

        self.update_file_name()
        self.setFixedWidth(380)
        self.setFixedHeight(self.sizeHint().height())

    def add_row(self, rows, text, control, stacked=False, last=False):
        """One setting: label on the left, control on the right (or below)."""
        row = QVBoxLayout() if stacked else QHBoxLayout()
        row.setContentsMargins(0, 9, 0, 9)
        row.setSpacing(6)
        row.addWidget(QLabel(text))
        if not stacked:
            row.addStretch()
        if isinstance(control, QWidget):
            row.addWidget(control)
        else:
            row.addLayout(control)
        rows.addLayout(row)
        if not last:
            divider = QFrame()
            divider.setObjectName("divider")
            rows.addWidget(divider)

    def set(self, key, value):
        self.prefs[key] = value
        settings.save(self.prefs)
        self.update_file_name()

    def set_startup(self, on):
        settings.set_start_with_windows(on)
        self.set("start_with_windows", on)

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Save folder", self.folder.text())
        if folder:
            self.folder.setText(folder.replace("/", "\\"))
            self.set("save_folder", self.folder.text())

    def update_file_name(self):
        self.file_name.setText(settings.file_name(datetime.now(), self.prefs["format"]))

    def showEvent(self, event):
        super().showEvent(event)
        # Dark title bar to match the window (DWMWA_USE_IMMERSIVE_DARK_MODE = 20).
        on = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(on), ctypes.sizeof(on))
