"""Capture full images of one fixed rectangle, only on request (§2e)."""
import ctypes

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

from snapclick.capture import ACCENT, exclude_from_capture, grab
from snapclick.hotkey import GlobalHotkey, REPEAT_ESCAPE_ID
from snapclick.record import RecordBorder

REFERENCE_HEIGHT = 40  # real pixels: a few lines, without shrinking the text
REFERENCE_GAP = 6
REFERENCE_TINT = QColor(ACCENT)
REFERENCE_TINT.setAlphaF(0.18)


def reference_strips(frame, image):
    """Last bottom above the box, last top below it; both stay outside the capture."""
    height = min(REFERENCE_HEIGHT, image.height())
    width = image.width()
    return [
        (QRect(frame.x(), frame.y() - REFERENCE_GAP - height, width, height),
         image.copy(0, image.height() - height, width, height)),
        (QRect(frame.x(), frame.y() + frame.height() + REFERENCE_GAP, width, height),
         image.copy(0, 0, width, height)),
    ]


class RepeatBorder(RecordBorder):
    """Reuse the passive border window for two small, static reference strips."""

    def __init__(self, frame, screen, references):
        self.references = references
        super().__init__(frame, screen, color=ACCENT)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        scale = self.area.width() / self.width()
        painter.scale(1 / scale, 1 / scale)
        painter.translate(-self.area.topLeft())
        # The window clips at monitor edges; no strip is moved inside the box.
        painter.setPen(QPen(ACCENT, 1))
        for rect, image in self.references:
            painter.drawImage(rect.topLeft(), image)
            painter.fillRect(rect, REFERENCE_TINT)
            painter.drawRect(rect.adjusted(-1, -1, 0, 0))
        painter.end()


class RepeatArea(QObject):
    changed = Signal()
    finished = Signal()

    def __init__(self, frame, first, other_windows):
        super().__init__()
        self.frame = QRect(frame)
        self.pieces = [first.copy()]
        self.closed = False
        references = reference_strips(self.frame, first)
        self.borders = [RepeatBorder(self.frame, screen, references) for screen in QGuiApplication.screens()]
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
        self.update_references()
        self.changed.emit()

    def update_references(self):
        piece = self.pieces[-1]
        references = reference_strips(self.frame, piece)
        for border in self.borders:
            border.references = references
            border.update()

    def remove_last(self):
        if not self.closed and self.count() > 1:
            self.pieces.pop()
            self.update_references()

    def close(self):
        """Release the border and hotkey without saving a discarded session."""
        if self.closed:
            return
        self.closed = True
        self.escape.close()
        for border in self.borders:
            border.close()

    def finish(self):
        if not self.closed:
            self.close()
            self.finished.emit()
