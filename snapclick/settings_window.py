"""Settings window (style B). Every change is saved immediately."""
import ctypes
from datetime import datetime

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget)

from snapclick import settings
from snapclick.hotkey import (DEFAULT_HOTKEY, MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, combo_name,
                              is_allowed)

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
QLabel#chip:hover {{ border-color: {TEXT_MUTED}; }}
QLabel#chip[recording="true"] {{ color: {ACCENT}; border-color: {ACCENT}; }}
QLabel#warning {{ color: {ACCENT}; font-size: 12px; }}
QPushButton#small {{ padding: 2px 8px; font-size: 12px; color: {TEXT_MUTED}; }}
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


class HotkeyChip(QLabel):
    """Shows the hotkey. Click it, then press a new key combo; Esc cancels."""

    started = Signal()
    recorded = Signal(int, int)  # Win32 key code, modifier flags
    cancelled = Signal()

    MODIFIER_KEYS = (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr)

    def __init__(self, text):
        super().__init__(text)
        self.setObjectName("chip")
        self.setFixedHeight(26)  # room for the mono text plus padding at any scaling
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recording = False
        self.shown = text

    def show_hotkey(self, text):
        """Stop recording and show `text`."""
        if self.recording:
            self.recording = False
            self.releaseKeyboard()
            self.set_recording_style(False)
        self.shown = text
        self.setText(text)

    def set_recording_style(self, on):
        self.setProperty("recording", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if not self.recording:
            self.recording = True
            self.setText("press keys…")
            self.set_recording_style(True)
            self.setFocus()
            self.grabKeyboard()  # get every key, even ones the window would use
            self.started.emit()

    def keyPressEvent(self, event):
        if not self.recording:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
        elif event.key() not in self.MODIFIER_KEYS:  # wait for the real key
            self.finish(event)

    def keyReleaseEvent(self, event):
        # Windows sends PrtSc only on key release.
        if self.recording and event.key() == Qt.Key.Key_Print:
            self.finish(event)

    def focusOutEvent(self, event):
        if self.recording:
            self.cancel()
        super().focusOutEvent(event)

    def finish(self, event):
        mods = 0
        for qt_flag, win_flag in ((Qt.KeyboardModifier.ControlModifier, MOD_CONTROL),
                                  (Qt.KeyboardModifier.AltModifier, MOD_ALT),
                                  (Qt.KeyboardModifier.ShiftModifier, MOD_SHIFT),
                                  (Qt.KeyboardModifier.MetaModifier, MOD_WIN)):  # Meta = Win key
            if event.modifiers() & qt_flag:
                mods |= win_flag
        self.show_hotkey(self.shown)
        self.recorded.emit(event.nativeVirtualKey(), mods)

    def cancel(self):
        self.show_hotkey(self.shown)
        self.cancelled.emit()


class SettingsWindow(QWidget):
    hotkey_changed = Signal()

    def __init__(self, hotkey):
        """`hotkey`: the app's GlobalHotkey, so a new combo can be tried right away."""
        super().__init__()
        self.hotkey = hotkey
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

        # Hotkey: click the chip to record a new combo; Reset = PrtSc
        self.chip = HotkeyChip(self.hotkey.hotkey["name"])
        self.chip.started.connect(self.hotkey.pause)  # so pressing it now doesn't capture
        self.chip.started.connect(lambda: self.show_hotkey_warning(""))
        self.chip.cancelled.connect(self.hotkey.resume)
        self.chip.recorded.connect(self.record_hotkey)
        reset = QPushButton("Reset")
        reset.setObjectName("small")
        reset.setFixedHeight(26)
        reset.setToolTip("Back to PrtSc")
        reset.clicked.connect(lambda: self.apply_hotkey(dict(DEFAULT_HOTKEY)))
        self.hotkey_warning = QLabel()
        self.hotkey_warning.setObjectName("warning")
        self.hotkey_warning.hide()
        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        chip_row.addWidget(self.chip)
        chip_row.addWidget(reset)
        hotkey_box = QVBoxLayout()
        hotkey_box.setSpacing(4)
        hotkey_box.addLayout(chip_row)
        hotkey_box.addWidget(self.hotkey_warning, 0, Qt.AlignmentFlag.AlignRight)
        self.add_row(rows, "Hotkey", hotkey_box)

        # Preview
        preview = Toggle(self.prefs["show_preview"])
        preview.toggled.connect(lambda on: self.set("show_preview", on))
        self.add_row(rows, "Show preview after capture", preview)

        # Start with Windows
        self.startup = Toggle(self.prefs["start_with_windows"])
        self.startup.toggled.connect(self.set_startup)
        self.add_row(rows, "Start with Windows", self.startup, last=True)

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

    def record_hotkey(self, vk, mods):
        if not is_allowed(vk, mods):
            self.hotkey.resume()
            self.show_hotkey_warning("not allowed — add Ctrl, Alt or Win")
            return
        self.apply_hotkey({"vk": vk, "mods": mods, "name": combo_name(vk, mods)})

    def apply_hotkey(self, new):
        """Use `new` if Windows accepts it; otherwise keep the old one."""
        if self.hotkey.change(new):
            self.set("hotkey", new)
            self.show_hotkey_warning("")
        else:
            self.show_hotkey_warning("taken by another app")
        self.chip.show_hotkey(self.hotkey.hotkey["name"])
        self.hotkey_changed.emit()

    def show_hotkey_warning(self, text):
        self.hotkey_warning.setText(text)
        self.hotkey_warning.setVisible(bool(text))
        self.setFixedHeight(self.sizeHint().height())  # grow/shrink for the message line

    def set_startup(self, on):
        if not settings.set_start_with_windows(on):
            QMessageBox.warning(self, "Snapclick", "Windows (or your antivirus) blocked changing the startup list.")
            self.startup.blockSignals(True)
            self.startup.setChecked(not on)  # show what really happened
            self.startup.blockSignals(False)
            return
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
