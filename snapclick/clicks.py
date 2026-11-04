"""Recording-only click circles, using frame-by-frame polling (§2d, step 2b)."""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QPainter, QPen

from snapclick.capture import ACCENT

VK_LBUTTON = 0x01
MARK_SECONDS = 0.4
DIAMETER = 24

user32 = ctypes.windll.user32
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]


class ClickMarks:
    """One short pulse per press, centered on the click in physical screen pixels."""

    def __init__(self):
        # Discard the click on Record and any presses from before recording.
        self.down = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        self.marks = []  # (seconds from recording start, screen point)

    def draw(self, image, frame, elapsed):
        state = user32.GetAsyncKeyState(VK_LBUTTON)
        down = bool(state & 0x8000)
        # The recent-press bit can also catch a quick click between frame reads.
        pressed = bool(state & 1) or (down and not self.down)
        self.down = down
        if pressed:
            cursor = wintypes.POINT()
            if user32.GetCursorPos(ctypes.byref(cursor)):
                point = QPoint(cursor.x, cursor.y)
                if frame.contains(point):
                    self.marks.append((elapsed, point))
        self.marks = [(when, point) for when, point in self.marks if elapsed - when < MARK_SECONDS]
        if not self.marks:
            return
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(ACCENT, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for when, point in self.marks:
            radius = DIAMETER / 2 + 3 * (elapsed - when) / MARK_SECONDS
            p.drawEllipse(QPointF(point - frame.topLeft()), radius, radius)
        p.end()
