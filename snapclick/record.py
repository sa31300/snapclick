"""Record step 1: live area selection and a ready/cancel control bar (§2d)."""
import ctypes

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QRegion
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from snapclick.capture import (Capture, DIM, Overlay, draw_magnifier, exclude_from_capture,
                               grab, magnifier_reach, physical_rect)
from snapclick.hotkey import GlobalHotkey, RECORD_ESCAPE_ID

RED = QColor("#FF6B6B")


class LiveSelection(Capture):
    selected = Signal(QRect)

    def __init__(self):
        self.live_image = None
        self.live_origin = QPoint()
        super().__init__()
        self.excluded = all([exclude_from_capture(w) for w in self.overlays])
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(60)
        self.refresh()

    def make_overlay(self, screen):
        return LiveOverlay(self, screen)

    def refresh(self):
        if self.cursor is None:
            return
        scale = max(o.scale() for o in self.overlays)
        half = magnifier_reach(scale)
        area = QRect(self.cursor.x() - half, self.cursor.y() - half, 2 * half + 1, 2 * half + 1)
        # Only the magnifier needs a screen read; the selection itself is transparent.
        if not self.excluded:
            for overlay in self.overlays:
                overlay.setWindowOpacity(0)
            ctypes.windll.dwmapi.DwmFlush()
        try:
            self.live_image, self.live_origin = grab(area), area.topLeft()
        finally:
            if not self.excluded:
                for overlay in self.overlays:
                    overlay.setWindowOpacity(1)
        for overlay in self.overlays:
            overlay.update()

    def click(self, point):
        if self.first is None:
            self.first = point
            self.move(point)
            return
        self.cursor = point
        area = self.selection()
        if area.width() > 0 and area.height() > 0:
            self.close_overlays()
            self.selected.emit(area)
        self.close()

    def close(self):
        self.timer.stop()
        super().close()


class LiveOverlay(Overlay):
    def __init__(self, capture, screen):
        super().__init__(capture, screen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paint_background(self, p, selection):
        p.fillRect(self.area, QColor(0, 0, 0, 1))  # receive clicks even in the clear area
        outside = QRegion(self.area)
        if selection:
            outside -= QRegion(selection)
        p.setClipRegion(outside)
        p.fillRect(self.area, DIM)
        p.setClipping(False)

    def paint_magnifier(self, p, cursor):
        c = self.capture
        if c.live_image is not None:
            draw_magnifier(p, c.live_image, c.live_origin, cursor, self.area, self.scale())


class RecordBorder(QWidget):
    """A one-pixel border outside the selected area; all input passes through."""

    def __init__(self, frame, screen):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.frame = QRect(frame)
        self.area = physical_rect(screen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        exclude_from_capture(self)
        self.show()

    def paintEvent(self, event):
        p = QPainter(self)
        scale = self.area.width() / self.width()
        p.scale(1 / scale, 1 / scale)
        p.translate(-self.area.topLeft())
        pen = QPen(RED, 1, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawRect(self.frame.adjusted(-1, -1, 0, 0))


class RecordBar(QWidget):
    def __init__(self, frame, cancel):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setWindowTitle("Snapclick · record")
        self.setStyleSheet('''
            QWidget { background: #0D0E10; color: #C9C9C4;
                      font-family: "JetBrains Mono"; font-size: 12px; }
            QPushButton { border: 1px solid #34363B; border-radius: 0; padding: 4px 8px; }
            QPushButton:hover { border-color: #FF6B6B; color: #FF6B6B; }
            QPushButton:disabled { color: #A3A39E; }
        ''')
        self.record = QPushButton("▶ record")
        self.record.setEnabled(False)  # frame recording is the next build step
        self.cancel = QPushButton("✕ cancel")
        self.cancel.clicked.connect(cancel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)
        layout.addWidget(self.record)
        layout.addWidget(self.cancel)
        # Qt sizes widgets in points; frame coordinates are physical screen pixels.
        screen = next((s for s in QGuiApplication.screens() if physical_rect(s).contains(frame.center())),
                      QGuiApplication.primaryScreen())
        self.setScreen(screen)
        self.adjustSize()
        bounds = screen.availableGeometry()
        origin = physical_rect(screen).topLeft()
        ratio = screen.devicePixelRatio()
        x = origin.x() + round((frame.left() - origin.x()) / ratio)
        y = origin.y() + round((frame.y() + frame.height() - origin.y()) / ratio) + 6
        if y + self.height() > bounds.bottom() + 1:
            y = origin.y() + round((frame.top() - origin.y()) / ratio) - self.height() - 6
        self.move(max(bounds.left(), min(x, bounds.right() + 1 - self.width())),
                  max(bounds.top(), min(y, bounds.bottom() + 1 - self.height())))
        exclude_from_capture(self)
        self.show()
        self.activateWindow()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel.click()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.cancel.click()
        event.accept()


class Record(QObject):
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.bar = None
        self.borders = []
        self.closed = False
        self.escape = None
        self.selection = LiveSelection()
        self.selection.selected.connect(self.ready)
        self.selection.finished.connect(self.selection_done)

    def selection_done(self):
        self.selection = None
        if self.bar is None:
            self.close()

    def ready(self, frame):
        self.borders = [RecordBorder(frame, screen) for screen in QGuiApplication.screens()]
        self.bar = RecordBar(frame, self.close)
        self.escape = GlobalHotkey(QGuiApplication.instance(), self.close,
                                  {"vk": 0x1B, "mods": 0, "name": "Esc"}, RECORD_ESCAPE_ID)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.escape:
            self.escape.close()
        if self.selection:
            self.selection.close()
        if self.bar:
            self.bar.close()
        for border in self.borders:
            border.close()
        self.finished.emit()
