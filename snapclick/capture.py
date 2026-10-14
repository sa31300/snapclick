"""Capture: freeze all monitors, pick two corners, copy the area to the clipboard.

All selection math is done in real (physical) screen pixels, so it stays
correct on scaled screens (125%, 150%) and across mixed-scale monitors.
"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

ACCENT = QColor("#FFB000")
DIM = QColor(0, 0, 0, round(255 * 0.62))  # black at 62%

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

    def selection(self):
        """Normalized rectangle between corner 1 and the cursor (any direction)."""
        if self.first is None or self.cursor is None:
            return None
        left, right = sorted((self.first.x(), self.cursor.x()))
        top, bottom = sorted((self.first.y(), self.cursor.y()))
        return QRect(left, top, right - left, bottom - top)

    def move(self, point):
        self.cursor = point
        for overlay in self.overlays:
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
        self.frozen = capture.image.copy(self.area.translated(-capture.origin))
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

    def to_local(self, rect):
        """Real-pixel rectangle -> this window's coordinates."""
        s = self.scale()
        r = rect.translated(-self.area.topLeft())
        return QRectF(r.x() / s, r.y() / s, r.width() / s, r.height() / s)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(QRectF(self.rect()), self.frozen)
        p.fillRect(self.rect(), DIM)
        area = self.capture.selection()
        if area and area.intersects(self.area):
            part = area.intersected(self.area)
            p.drawImage(self.to_local(part), self.frozen, QRectF(part.translated(-self.area.topLeft())))
            p.setPen(QPen(ACCENT, 1))
            p.drawRect(self.to_local(area))

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
