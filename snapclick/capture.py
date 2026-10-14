"""Capture: freeze all monitors, pick two corners, copy the area to the clipboard.

All selection math is done in real (physical) screen pixels, so it stays
correct on scaled screens (125%, 150%) and across mixed-scale monitors.
"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

# Style B (see docs/SPEC.md, section 2). Sizes are in screen points; they are
# multiplied by the monitor's scale when drawn.
ACCENT = QColor("#FFB000")
CROSSHAIR = QColor(255, 176, 0, round(255 * 0.6))  # accent at 60%
DIM = QColor(0, 0, 0, round(255 * 0.62))  # black at 62%
HINT_TEXT = QColor("#C9C9C4")
HINT_BG = QColor("#0D0E10")
HINT_BORDER = QColor("#34363B")
MONO = "JetBrains Mono"
FONT_SIZE = 12
MAGNIFIER_SIZE = 120
ZOOM = 4

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
# Declare Win32 handle types so 64-bit handles are passed correctly.
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.BitBlt.argtypes = [wintypes.HDC] + [ctypes.c_int] * 4 + [wintypes.HDC] + [ctypes.c_int] * 2 + [wintypes.DWORD]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]


def grab_desktop():
    """Screenshot of the whole virtual desktop in real pixels. Returns (image, origin)."""
    x, y = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)  # SM_X/YVIRTUALSCREEN
    w, h = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)  # SM_CX/CYVIRTUALSCREEN

    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, w, h)
    old = gdi32.SelectObject(mem_dc, bitmap)
    gdi32.BitBlt(mem_dc, 0, 0, w, h, screen_dc, x, y, 0x00CC0020 | 0x40000000)  # SRCCOPY | CAPTUREBLT

    # BITMAPINFOHEADER: 32-bit, top-down (negative height)
    header = (ctypes.c_uint32 * 10)(40, w, ctypes.c_uint32(-h).value, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, h, buffer, header, 0)

    gdi32.SelectObject(mem_dc, old)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(None, screen_dc)

    image = QImage(buffer.raw, w, h, w * 4, QImage.Format.Format_RGB32).copy()
    return image, QPoint(x, y)


def physical_rect(screen):
    """A monitor's area in real pixels. Qt keeps each screen's top-left in
    real pixels on Windows; only the size is scaled."""
    g = screen.geometry()
    ratio = screen.devicePixelRatio()
    return QRect(g.x(), g.y(), round(g.width() * ratio), round(g.height() * ratio))


class Capture(QObject):
    """One capture session: an overlay on every monitor sharing one selection."""

    finished = Signal()

    def __init__(self):
        super().__init__()
        self.image, self.origin = grab_desktop()  # freeze the screen first
        self.first = None  # corner 1, real pixels
        self.cursor = None  # mouse position, real pixels
        self.overlays = [Overlay(self, screen) for screen in QGuiApplication.screens()]
        for overlay in self.overlays:
            overlay.show()
        # Give keyboard focus to the overlay under the mouse, so Esc works.
        mouse_screen = QGuiApplication.screenAt(QCursor.pos())
        focused = next((o for o in self.overlays if o.screen() == mouse_screen), self.overlays[0])
        focused.activateWindow()
        focused.setFocus()
        self.move(focused.to_physical(focused.mapFromGlobal(QCursor.pos())))

    def selection(self):
        """Normalized rectangle between corner 1 and the cursor (any direction)."""
        if self.first is None or self.cursor is None:
            return None
        left, right = sorted((self.first.x(), self.cursor.x()))
        top, bottom = sorted((self.first.y(), self.cursor.y()))
        return QRect(left, top, right - left, bottom - top)

    def move(self, point):
        # Repaint only the monitors touched by the old or new cursor/selection.
        changed = [p for p in (self.cursor, point) if p is not None]
        if self.first is not None:
            changed = [QRect(self.first, p).normalized().adjusted(-1, -1, 1, 1) for p in changed]
        else:
            changed = [QRect(p, p) for p in changed]
        self.cursor = point
        for overlay in self.overlays:
            if any(overlay.area.intersects(rect) for rect in changed):
                overlay.update()

    def click(self, point):
        if self.first is None:
            self.first = point
            self.move(point)
            return
        self.cursor = point
        area = self.selection()
        if area.width() > 0 and area.height() > 0:  # 0 px cancels
            crop = self.image.copy(area.translated(-self.origin))
            QGuiApplication.clipboard().setImage(crop)
        self.close()

    def close(self):
        for overlay in self.overlays:
            overlay.close()
        self.finished.emit()


class Overlay(QWidget):
    """Full-screen window on one monitor, showing the frozen screen."""

    def __init__(self, capture, screen):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.capture = capture
        self.area = physical_rect(screen)  # this monitor, real pixels
        self.dimmed = capture.image.copy(self.area.translated(-capture.origin))
        p = QPainter(self.dimmed)
        p.fillRect(self.dimmed.rect(), DIM)
        p.end()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def scale(self):
        return self.area.width() / self.width()

    def to_physical(self, pos):
        s = self.scale()
        return QPoint(self.area.x() + int(pos.x() * s), self.area.y() + int(pos.y() * s))

    def font(self, semibold=False):
        font = QFont(MONO)
        font.setPixelSize(round(FONT_SIZE * self.scale()))
        if semibold:
            font.setWeight(QFont.Weight.DemiBold)
        return font

    def label(self, p, text, font, x, y, fg, bg, border=None):
        """Text in a box whose top-left is (x, y), kept inside this monitor."""
        s = self.scale()
        metrics = QFontMetrics(font)
        pad_x, pad_y = round(6 * s), round(3 * s)
        box = QRect(0, 0, metrics.horizontalAdvance(text) + 2 * pad_x, metrics.height() + 2 * pad_y)
        box.moveTo(min(max(x, self.area.left()), self.area.right() + 1 - box.width()),
                   min(max(y, self.area.top()), self.area.bottom() + 1 - box.height()))
        if bg:
            p.fillRect(box, bg)
        if border:
            p.setPen(QPen(border, 1))
            p.drawRect(box.adjusted(0, 0, -1, -1))
        p.setFont(font)
        p.setPen(fg)
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def draw_magnifier(self, p, cursor):
        s = self.scale()
        half = round(MAGNIFIER_SIZE / ZOOM / 2 * s)  # real pixels on each side of the cursor
        source = QRect(cursor.x() - half, cursor.y() - half, 2 * half + 1, 2 * half + 1)
        box_size = source.width() * ZOOM
        gap = round(24 * s)
        # Bottom-right of the cursor; flip to the other side near an edge.
        x = cursor.x() + gap
        if x + box_size > self.area.right():
            x = cursor.x() - gap - box_size
        y = cursor.y() + gap
        if y + box_size > self.area.bottom():
            y = cursor.y() - gap - box_size
        box = QRect(x, y, box_size, box_size)

        p.fillRect(box, HINT_BG)  # shows where the zoom goes past the desktop edge
        pixels = self.capture.image.copy(source.translated(-self.capture.origin))
        p.drawImage(box, pixels)  # no smoothing: each pixel becomes a sharp 4x4 square
        middle = half * ZOOM + ZOOM // 2
        p.setPen(QPen(ACCENT, 1))
        p.drawLine(x + middle, y, x + middle, y + box_size - 1)
        p.drawLine(x, y + middle, x + box_size - 1, y + middle)
        p.setPen(QPen(HINT_BORDER, 1))
        p.drawRect(box.adjusted(-1, -1, 0, 0))

    def paintEvent(self, event):
        # Draw on an image the size of the monitor in real pixels, so 1 px
        # lines stay sharp at any scaling. Coordinates are desktop pixels.
        s = self.scale()
        line = max(1, int(s))
        capture = self.capture
        area = self.area
        canvas = QImage(area.size(), QImage.Format.Format_RGB32)
        p = QPainter(canvas)
        p.translate(-area.topLeft())

        p.drawImage(area.topLeft(), self.dimmed)
        selection = capture.selection()
        if selection:
            p.drawImage(selection.topLeft(), capture.image, selection.translated(-capture.origin))

        cursor = capture.cursor
        cursor_here = cursor is not None and area.contains(cursor)
        if cursor_here:
            p.setPen(QPen(CROSSHAIR, line))
            p.drawLine(area.left(), cursor.y(), area.right(), cursor.y())
            p.drawLine(cursor.x(), area.top(), cursor.x(), area.bottom())

        if selection:
            pen = QPen(ACCENT, line, Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([4, 3])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(selection)

        first = capture.first
        if first is not None and area.contains(first):
            text = f"x {first.x() - capture.origin.x()}  y {first.y() - capture.origin.y()}"
            height = QFontMetrics(self.font()).height() + round(6 * s)
            self.label(p, text, self.font(), first.x() - round(6 * s), first.y() - height - round(4 * s),
                       ACCENT, None)

        if selection:
            corner = QPoint(selection.x() + selection.width(), selection.y() + selection.height())
            if area.contains(corner):
                text = f"{selection.width()}×{selection.height()}"
                font = self.font(semibold=True)
                width = QFontMetrics(font).horizontalAdvance(text) + round(12 * s)
                self.label(p, text, font, corner.x() - width, corner.y() + round(6 * s),
                           QColor("black"), ACCENT)

        if cursor_here:
            step = "2nd" if first is not None else "1st"
            margin = round(16 * s)
            self.label(p, f"[click] {step} corner   [esc] cancel", self.font(),
                       area.left() + margin, area.top() + margin, HINT_TEXT, HINT_BG, HINT_BORDER)
            self.draw_magnifier(p, cursor)

        p.end()
        QPainter(self).drawImage(QRectF(self.rect()), canvas)

    def mouseMoveEvent(self, event):
        self.capture.move(self.to_physical(event.position()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.capture.click(self.to_physical(event.position()))
        elif event.button() == Qt.MouseButton.RightButton:
            self.capture.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.capture.close()
