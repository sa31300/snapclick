"""Capture full images of one fixed rectangle, only on request (§2e)."""
import ctypes

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPainter

from snapclick.capture import ACCENT, exclude_from_capture, grab
from snapclick.hotkey import GlobalHotkey, REPEAT_ESCAPE_ID
from snapclick.record import RecordBorder


class RepeatArea(QObject):
    changed = Signal()
    finished = Signal()

    def __init__(self, frame, first, other_windows):
        super().__init__()
        self.frame = QRect(frame)
        self.pieces = [first.copy()]
        self.closed = False
        self.borders = [RecordBorder(self.frame, screen, color=ACCENT) for screen in QGuiApplication.screens()]
        self.windows = self.borders + other_windows
        self.excluded = all([exclude_from_capture(w) for w in self.windows])
        # Finish outside the native filter callback so it can safely unregister itself.
        self.escape = GlobalHotkey(QGuiApplication.instance(), lambda: QTimer.singleShot(0, self.finish),
                                  {"vk": 0x1B, "mods": 0, "name": "Esc"}, REPEAT_ESCAPE_ID)

    def count(self):
        return len(self.pieces)

    def image(self):
        """Join whole images in capture order, including unchanged/repeated rows."""
        image = QImage(self.frame.width(), self.frame.height() * self.count(), QImage.Format.Format_RGB32)
        painter = QPainter(image)
        for index, piece in enumerate(self.pieces):
            painter.drawImage(0, index * self.frame.height(), piece)
        painter.end()
        return image

    def add(self):
        if self.closed:
            return
        # On older Windows, hide our windows for this one read, then restore them.
        hidden = [] if self.excluded else [(w, w.windowOpacity()) for w in self.windows]
        try:
            for window, _ in hidden:
                window.setWindowOpacity(0)
            if hidden:
                ctypes.windll.dwmapi.DwmFlush()
            piece = grab(self.frame)
        finally:
            for window, opacity in hidden:
                window.setWindowOpacity(opacity)
        self.pieces.append(piece)
        self.changed.emit()

    def finish(self):
        if self.closed:
            return
        self.closed = True
        self.escape.close()
        for border in self.borders:
            border.close()
        self.finished.emit()
