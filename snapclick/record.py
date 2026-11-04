"""Live area selection, short recordings and PNG frame sheets (§2d)."""
import ctypes
import time

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen, QRegion
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from snapclick import settings
from snapclick.capture import (Capture, DIM, Overlay, draw_magnifier, exclude_from_capture,
                               grab, magnifier_reach, physical_rect)
from snapclick.clicks import ClickMarks
from snapclick.frames import FrameBuffer, clock_text, make_sheet
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
        self.recording = False
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
        pen = QPen(RED, 1)
        if not self.recording:
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawRect(self.frame.adjusted(-1, -1, 0, 0))


class RecordBar(QWidget):
    def __init__(self, frame, cancel, start=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setWindowTitle("Snapclick · record")
        self.frame = QRect(frame)
        self.setStyleSheet('''
            QWidget { background: #0D0E10; color: #C9C9C4;
                      font-family: "JetBrains Mono"; font-size: 12px; }
            QPushButton { border: 1px solid #34363B; border-radius: 0; padding: 4px 8px; }
            QPushButton:hover { border-color: #FF6B6B; color: #FF6B6B; }
            QPushButton:disabled { color: #A3A39E; }
        ''')
        self.record = QPushButton("▶ record")
        self.record.setEnabled(start is not None)
        if start:
            self.record.clicked.connect(start)
        self.cancel = QPushButton("✕ cancel")
        self.cancel.clicked.connect(cancel)
        self.clock = QLabel()
        self.clock.hide()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)
        layout.addWidget(self.record)
        layout.addWidget(self.cancel)
        layout.addWidget(self.clock)
        self.place()
        exclude_from_capture(self)
        self.show()
        self.activateWindow()

    def place(self):
        # Qt sizes widgets in points; frame coordinates are physical screen pixels.
        frame = self.frame
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

    def show_recording(self, elapsed, limit):
        self.record.hide()
        self.cancel.setText("■ stop")
        self.cancel.setStyleSheet("color: #FF6B6B; border-color: #FF6B6B;")
        self.clock.show()
        self.update_clock(elapsed, limit)
        self.place()

    def update_clock(self, elapsed, limit):
        self.clock.setText(f"{clock_text(elapsed)} / {clock_text(limit)}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel.click()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.cancel.click()
        event.accept()


class Record(QObject):
    recorded = Signal(QImage, int, float)  # sheet, chosen frame count, elapsed seconds
    finished = Signal()

    def __init__(self, prefs=None):
        super().__init__()
        self.prefs = prefs if prefs is not None else settings.load()
        self.bar = None
        self.borders = []
        self.closed = False
        self.escape = None
        self.running = False
        self.buffer = None
        self.clicks = None
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.selection = LiveSelection()
        self.selection.selected.connect(self.ready)
        self.selection.finished.connect(self.selection_done)

    def selection_done(self):
        self.selection = None
        if self.bar is None:
            self.close()

    def ready(self, frame):
        self.frame = QRect(frame)
        self.borders = [RecordBorder(frame, screen) for screen in QGuiApplication.screens()]
        self.bar = RecordBar(frame, self.close, self.start)
        self.excluded = all([exclude_from_capture(w) for w in self.borders + [self.bar]])
        self.escape = GlobalHotkey(QGuiApplication.instance(), self.close,
                                  {"vk": 0x1B, "mods": 0, "name": "Esc"}, RECORD_ESCAPE_ID)

    def start(self):
        if self.running or self.closed:
            return
        self.buffer = FrameBuffer(self.frame.size(), self.prefs["record_frames"])
        self.started = time.monotonic()
        self.running = True
        self.clicks = ClickMarks()
        for border in self.borders:
            border.recording = True
            border.update()
        self.bar.show_recording(0, self.prefs["record_max_length"])
        self.read_frame(0)
        self.timer.start(200)  # about 5 frames per second

    def read_frame(self, elapsed, final=False):
        windows = self.borders + [self.bar]
        if not self.excluded:
            for window in windows:
                window.setWindowOpacity(0)
            ctypes.windll.dwmapi.DwmFlush()
        try:
            image = grab(self.frame, include_cursor=True)
        finally:
            if not self.excluded:
                for window in windows:
                    window.setWindowOpacity(1)
        self.clicks.draw(image, self.frame, elapsed)
        self.buffer.add(image, elapsed, final=final)

    def tick(self):
        elapsed = time.monotonic() - self.started
        if elapsed >= self.prefs["record_max_length"]:
            self.stop()
            return
        self.read_frame(elapsed)
        self.bar.update_clock(elapsed, self.prefs["record_max_length"])

    def stop(self):
        if not self.running or self.closed:
            return
        self.timer.stop()
        elapsed = min(time.monotonic() - self.started, self.prefs["record_max_length"])
        self.read_frame(elapsed, final=True)  # keep the last moment, even if it hasn't changed
        self.running = False
        frames = self.buffer.selected()
        sheet = make_sheet(frames)
        self.buffer = None
        self.close_windows()
        self.recorded.emit(sheet, len(frames), elapsed)
        self.finished.emit()

    def close(self):
        if self.closed:
            return
        if self.running:
            self.stop()  # Esc and closing the bar keep the recording
            return
        self.close_windows()
        self.finished.emit()

    def close_windows(self):
        self.closed = True
        self.clicks = None
        self.timer.stop()
        if self.escape:
            self.escape.close()
        if self.selection:
            self.selection.close()
        if self.bar:
            self.bar.close()
        for border in self.borders:
            border.close()
