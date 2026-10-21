"""Tray icon: corner brackets that follow the Windows taskbar theme."""
import os
import winreg
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from snapclick import settings
from snapclick.capture import Capture, clipboard_version, restore_clipboard
from snapclick.draw import DrawWindow, draw_title
from snapclick.preview import Preview
from snapclick.stack import Stack
from snapclick.settings_window import SettingsWindow

DARK_TASKBAR_COLOR = "#FFB000"
LIGHT_TASKBAR_COLOR = "#7A4E00"
ICON_SIZES = (16, 20, 24, 32)


def taskbar_is_light():
    """Windows stores the taskbar theme in the registry (1 = light)."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        winreg.CloseKey(key)
        return value == 1
    except OSError:
        return False  # default Windows taskbar is dark


def draw_brackets(size, color):
    """Draw 4 L-shaped corners with whole-pixel rectangles so they stay crisp."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    margin = max(1, size // 16)
    stroke = max(2, size // 10)
    arm = round(size * 0.38)
    far = size - margin  # right/bottom edge

    p = QPainter(pixmap)
    c = QColor(color)
    # top-left
    p.fillRect(margin, margin, arm, stroke, c)
    p.fillRect(margin, margin, stroke, arm, c)
    # top-right
    p.fillRect(far - arm, margin, arm, stroke, c)
    p.fillRect(far - stroke, margin, stroke, arm, c)
    # bottom-left
    p.fillRect(margin, far - stroke, arm, stroke, c)
    p.fillRect(margin, far - arm, stroke, arm, c)
    # bottom-right
    p.fillRect(far - arm, far - stroke, arm, stroke, c)
    p.fillRect(far - stroke, far - arm, stroke, arm, c)
    p.end()
    return pixmap


def make_icon(light):
    color = LIGHT_TASKBAR_COLOR if light else DARK_TASKBAR_COLOR
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(draw_brackets(size, color))
    return icon


class Tray(QSystemTrayIcon):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.capture = None  # the running capture, if any
        self.settings_window = None
        self.preview = None
        self.draw_window = None  # the open draw window (§2c), if any
        self.stack = None  # the running stack (long capture), if any
        self.undo = None  # what the preview's Retake needs to undo the last capture
        self.hotkey = None  # GlobalHotkey, set by main
        self.light = taskbar_is_light()
        self.setIcon(make_icon(self.light))
        self.update_tooltip()
        self.setContextMenu(self._build_menu())
        self.activated.connect(self._on_click)

        # Check the taskbar theme every 2 s and swap the icon if it changed.
        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._check_theme)
        self.theme_timer.start(2000)

    def _build_menu(self):
        menu = QMenu()
        capture_action = QAction("Capture", menu)
        capture_action.triggered.connect(self.start_capture)
        menu.addAction(capture_action)
        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)
        folder_action = QAction("Open save folder", menu)
        folder_action.triggered.connect(self.open_save_folder)
        menu.addAction(folder_action)
        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)
        self._menu = menu  # keep a reference so Qt does not delete it
        return menu

    def update_tooltip(self):
        if self.hotkey and self.hotkey.registered:
            self.setToolTip(f"Snapclick — {self.hotkey.hotkey['name']} to capture")
        else:
            self.setToolTip("Snapclick — hotkey taken, click to capture")

    def _check_theme(self):
        light = taskbar_is_light()
        if light != self.light:
            self.light = light
            self.setIcon(make_icon(light))

    def _on_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # left-click
            self.start_capture()

    def start_capture(self, frozen=None):
        if self.capture:  # already capturing: ignore a second PrtSc
            return
        if self.stack:
            self.stack.finish()  # keep the stack so far
        self.close_preview()  # its Retake must not undo a newer capture
        self.capture = Capture(frozen)
        self.capture.captured.connect(self._captured)
        self.capture.finished.connect(self._capture_done)

    def _capture_done(self):
        self.capture = None

    def _captured(self, image):
        prefs = settings.load()
        saved_path = self.save_image(image, prefs) if prefs["auto_save"] else None
        if prefs["show_preview"]:
            c = self.capture
            self.undo = {
                "frozen": (c.image, c.origin),
                "clipboard": c.previous_clipboard,
                "clipboard_version": c.clipboard_version,
                "saved_path": saved_path,
                "frame": c.selection(),  # where piece 1 is on screen, for a stack
            }
            self.preview = Preview(image, can_save=not prefs["auto_save"],
                                   save_folder=prefs["save_folder"], saved_path=saved_path)
            self.preview.retake.connect(self.undo_and_retake)
            self.preview.save_requested.connect(self.save_from_preview)
            self.preview.add_below.connect(self.start_stack)
            self.preview.draw.connect(self.open_draw)
            self.preview.finish.connect(self.finish_stack)
            self.preview.closed.connect(self._preview_closed)

    def save_from_preview(self):
        path = self.save_image(self.preview.image, settings.load())
        if path:
            self.undo["saved_path"] = path  # Retake deletes it too
            self.preview.show_saved(path)
        else:
            self.preview.show_save_failed()

    def _preview_closed(self):
        self.undo = None  # free the frozen screen
        if self.draw_window:  # its picture belongs to this preview
            window, self.draw_window = self.draw_window, None
            window.closed.disconnect(self._draw_closed)
            window.close()

    def open_draw(self):
        """Mark up the captured picture in its own window (§2c)."""
        if self.draw_window:
            self.draw_window.raise_()
            self.draw_window.activateWindow()
            return
        p = self.preview
        p.hold(True)
        self.draw_window = DrawWindow(p.image, draw_title(p.mode, p.count, p.image), p.home)
        self.draw_window.done.connect(self.copy)
        self.draw_window.closed.connect(self._draw_closed)

    def _draw_closed(self):
        self.draw_window = None
        if self.preview:
            self.preview.hold(False)

    def close_preview(self):
        if self.preview:
            self.preview.close()
            self.preview = None

    def start_stack(self):
        undo = self.undo
        if undo["saved_path"]:  # auto-save keeps only the final joined image
            self.delete_file(undo["saved_path"])
            undo["saved_path"] = None
        self.preview.start_stack()
        self.stack = Stack(undo["frame"], self.preview.image, [self.preview])
        self.stack.changed.connect(self._stack_changed)
        self.stack.finished.connect(self._stack_finished)
        self.preview.raise_()  # above the stack overlay

    def _stack_changed(self):
        """A piece was added: the clipboard always holds the whole stack."""
        image = self.stack.image()
        self.copy(image)
        self.preview.set_stack(image, self.stack.count())

    def finish_stack(self):
        if self.stack:
            self.stack.finish()

    def _stack_finished(self):
        stack, self.stack = self.stack, None
        image = stack.image()
        self.copy(image, only_if_ours=True)
        prefs = settings.load()
        saved_path = self.save_image(image, prefs) if prefs["auto_save"] else None
        self.undo["saved_path"] = saved_path
        self.preview.finish_stack(image, stack.count(), saved_path)

    def copy(self, image, only_if_ours=False):
        """Put a stack or drawn image on the clipboard. `only_if_ours`: not if something
        else was copied since our last copy."""
        if only_if_ours and clipboard_version() != self.undo["clipboard_version"]:
            return
        QGuiApplication.clipboard().setImage(image)
        self.undo["clipboard_version"] = clipboard_version()

    def undo_and_retake(self):
        if self.stack and self.stack.count() > 1:  # while stacking: remove only the last piece
            self.stack.remove_last()
            image = self.stack.image()
            self.copy(image, only_if_ours=True)
            self.preview.set_stack(image, self.stack.count())
            return
        if self.stack:
            self.stack.close()
            self.stack = None
        undo = self.undo
        self.close_preview()
        if undo is None:
            return
        # Restore the clipboard only if nothing else was copied since.
        if clipboard_version() == undo["clipboard_version"]:
            restore_clipboard(undo["clipboard"])
        if undo["saved_path"]:
            self.delete_file(undo["saved_path"])
        self.start_capture(frozen=undo["frozen"])

    def delete_file(self, path):
        try:
            path.unlink()
        except OSError:
            pass  # already gone or locked: nothing more to do

    def save_image(self, image, prefs):
        """Save to the save folder. Returns the file path, or None if it failed."""
        try:
            folder = Path(prefs["save_folder"])
            folder.mkdir(parents=True, exist_ok=True)
            path = settings.new_file_path(folder, prefs["format"])
            if prefs["format"] == "jpg":
                ok = image.save(str(path), "JPG", 90)
            else:
                ok = image.save(str(path), "PNG")
        except OSError:
            ok = False
        if not ok:
            self.showMessage("Snapclick", f"Could not save to {prefs['save_folder']}.\n"
                             "The image is still in your clipboard.", QSystemTrayIcon.MessageIcon.Warning)
            return None
        return path

    def open_settings(self):
        if self.settings_window is None or not self.settings_window.isVisible():
            self.settings_window = SettingsWindow()
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def open_save_folder(self):
        folder = Path(settings.load()["save_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)
