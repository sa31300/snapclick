"""Tray icon: corner brackets that follow the Windows taskbar theme."""
import winreg

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

DARK_TASKBAR_COLOR = "#FFB000"
LIGHT_TASKBAR_COLOR = "#7A4E00"
ICON_SIZES = (16, 20, 24, 32)
TOOLTIP = "Snapclick — PrtSc to capture"


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
        self.light = taskbar_is_light()
        self.setIcon(make_icon(self.light))
        self.setToolTip(TOOLTIP)
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
        # Settings and Open save folder are wired up in later steps.
        for label in ("Settings…", "Open save folder"):
            action = QAction(label, menu)
            action.setEnabled(False)
            menu.addAction(action)
        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)
        self._menu = menu  # keep a reference so Qt does not delete it
        return menu

    def _check_theme(self):
        light = taskbar_is_light()
        if light != self.light:
            self.light = light
            self.setIcon(make_icon(light))

    def _on_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # left-click
            self.start_capture()

    def start_capture(self):
        # Placeholder until the capture overlay is built in step 3.
        self.showMessage("Snapclick", "Capture started (overlay comes in step 3).")
