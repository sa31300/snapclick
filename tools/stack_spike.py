"""Spike for the Stack (docs/SPEC.md §2b, build order step 1).

Tests two things before the real stack is built:
1. Wheel pass-through: the overlay catches the mouse wheel and passes it to
   the window under it, so that window scrolls.
2. Capture exclusion: Snapclick's own windows are left out of screen reads.

Run:   .venv\\Scripts\\python tools\\stack_spike.py
Click two corners to set the frame, then scroll over it.
[M] switches the wheel method (post / sendinput), [Esc] or right-click quits.
A summary is printed when it closes.
"""
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from snapclick.__main__ import load_fonts
from snapclick.capture import ACCENT, DIM, HINT_BG, HINT_BORDER, HINT_TEXT, MONO, grab, physical_rect

WDA_EXCLUDEFROMCAPTURE = 0x11  # Windows 10 2004+
GW_HWNDNEXT = 2
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WM_MOUSEWHEEL = 0x020A
DWMWA_CLOAKED = 14
CWP_SKIPINVISIBLE, CWP_SKIPTRANSPARENT = 0x1, 0x4
INPUT_MOUSE = 0
MOUSEEVENTF_WHEEL = 0x0800
READ_INTERVAL_MS = 50  # 20 reads per second (spec: at least 15)
MARKER = 8  # size of the test square drawn by the overlay inside the frame

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.ChildWindowFromPointEx.argtypes = [wintypes.HWND, wintypes.POINT, wintypes.UINT]
user32.ChildWindowFromPointEx.restype = wintypes.HWND
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]  # MOUSEINPUT is the largest union member


def cursor_pos():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point


def class_name(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def is_target(hwnd, point, own_pid):
    """A visible window of another app that is under `point`."""
    if not user32.IsWindowVisible(hwnd):
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == own_pid:
        return False
    cloaked = wintypes.DWORD()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), 4)
    if cloaked.value or user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_TRANSPARENT:
        return False
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom


def window_below(overlay_hwnd, point, own_pid):
    """The deepest window under `point`, looking only below the overlay."""
    hwnd = user32.GetWindow(overlay_hwnd, GW_HWNDNEXT)
    while hwnd and not is_target(hwnd, point, own_pid):
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
    while hwnd:
        local = wintypes.POINT(point.x, point.y)
        user32.ScreenToClient(hwnd, ctypes.byref(local))
        child = user32.ChildWindowFromPointEx(hwnd, local, CWP_SKIPINVISIBLE | CWP_SKIPTRANSPARENT)
        if not child or child == hwnd:
            break
        hwnd = child
    return hwnd


class SpikeOverlay(QWidget):
    """See-through overlay on the monitor under the mouse."""

    def __init__(self, screen):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.area = physical_rect(screen)
        self.own_pid = ctypes.windll.kernel32.GetCurrentProcessId()

        self.first = None  # corner 1 of the frame, real pixels
        self.cursor = None
        self.frame = None  # QRect, real pixels
        self.read = None  # latest screen read of the frame
        self.method = "post"
        self.excluded = None  # True if SetWindowDisplayAffinity worked
        self.marker_in_reads = 0
        self.reads = 0
        self.read_times = []
        self.wheels = {"post": 0, "sendinput": 0}
        self.targets = set()
        self.last_target = "-"

        self.read_timer = QTimer(self, interval=READ_INTERVAL_MS, timeout=self.read_frame)

    def showEvent(self, event):
        hwnd = int(self.winId())
        self.excluded = bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
        affinity = wintypes.DWORD()
        user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(affinity))
        self.excluded = self.excluded and affinity.value == WDA_EXCLUDEFROMCAPTURE

    # --- geometry ---------------------------------------------------------

    def scale(self):
        return self.area.width() / self.width()

    def to_physical(self, pos):
        s = self.scale()
        return QPoint(self.area.x() + int(pos.x() * s), self.area.y() + int(pos.y() * s))

    def marker_rect(self):
        return QRect(self.frame.x() + 4, self.frame.y() + 4, MARKER, MARKER)

    # --- screen reads -----------------------------------------------------

    def read_frame(self):
        self.read = grab(self.frame)
        self.reads += 1
        now = time.perf_counter()
        self.read_times = [t for t in self.read_times if now - t < 1] + [now]
        # If our own overlay got into the read, the orange marker shows up in it.
        middle = self.read.pixelColor(4 + MARKER // 2, 4 + MARKER // 2)
        if middle.rgb() == ACCENT.rgb():
            self.marker_in_reads += 1
        self.update()

    # --- wheel pass-through -----------------------------------------------

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if not delta:
            return
        point = cursor_pos()
        target = window_below(int(self.winId()), point, self.own_pid)
        self.last_target = class_name(target) if target else "(none)"
        self.targets.add(self.last_target)
        if self.method == "post":
            if target:
                wparam = (delta & 0xFFFF) << 16  # no keys held
                lparam = ((point.y & 0xFFFF) << 16) | (point.x & 0xFFFF)
                user32.PostMessageW(target, WM_MOUSEWHEEL, wparam, lparam)
        else:
            self.send_wheel(delta)
        self.wheels[self.method] += 1
        self.update()

    def send_wheel(self, delta):
        """Let the mouse fall through the overlay for a moment and replay the wheel."""
        hwnd = int(self.winId())
        style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT)
        wheel = INPUT(INPUT_MOUSE, MOUSEINPUT(0, 0, ctypes.c_uint32(delta).value, MOUSEEVENTF_WHEEL, 0, 0))
        user32.SendInput(1, ctypes.byref(wheel), ctypes.sizeof(INPUT))
        QTimer.singleShot(150, lambda: user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style))

    # --- mouse and keys ---------------------------------------------------

    def mouseMoveEvent(self, event):
        self.cursor = self.to_physical(event.position())
        if self.frame is None:
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.close()
        elif event.button() == Qt.MouseButton.LeftButton and self.frame is None:
            point = self.to_physical(event.position())
            if self.first is None:
                self.first = point
            else:
                frame = QRect(self.first, point).normalized()
                if frame.width() > 2 * MARKER and frame.height() > 2 * MARKER:
                    self.frame = frame
                    self.read_timer.start()
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_M:
            self.method = "sendinput" if self.method == "post" else "post"
            self.update()

    def closeEvent(self, event):
        self.read_timer.stop()
        print_summary(self)
        QApplication.quit()

    # --- drawing ----------------------------------------------------------

    def font(self):
        font = QFont(MONO)
        font.setPixelSize(round(12 * self.scale()))
        return font

    def status_lines(self):
        ok = lambda good: "OK" if good else "FAILED"
        lines = [f"exclude from capture: {ok(self.excluded)}"]
        if self.frame is None:
            lines.append("[click] [click] set the frame   [esc] quit")
            return lines
        lines += [
            f"reads/s: {len(self.read_times)}   reads: {self.reads}",
            f"overlay seen in reads: {self.marker_in_reads}  (must stay 0)",
            f"wheel method: {self.method}   [M] switch",
            f"wheels passed: post {self.wheels['post']}, sendinput {self.wheels['sendinput']}",
            f"window under mouse: {self.last_target}",
            "[wheel] scroll   [esc] quit",
        ]
        return lines

    def paintEvent(self, event):
        s = self.scale()
        line = max(1, int(s))
        area = self.area
        canvas = QImage(area.size(), QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(QColor(0, 0, 0, 1))  # almost invisible, but still catches the mouse
        p = QPainter(canvas)
        p.translate(-area.topLeft())
        dash = QPen(ACCENT, line, Qt.PenStyle.CustomDashLine)
        dash.setDashPattern([4, 3])

        if self.frame is not None:
            p.fillRect(area, DIM)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(self.frame, QColor(0, 0, 0, 1))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setPen(dash)
            p.drawRect(self.frame)
            p.fillRect(self.marker_rect(), ACCENT)  # must NOT show up in the reads
            self.draw_read(p)
        elif self.first is not None and self.cursor is not None:
            p.setPen(dash)
            p.drawRect(QRect(self.first, self.cursor).normalized())

        # Status box, top-left.
        font = self.font()
        metrics = QFontMetrics(font)
        lines = self.status_lines()
        pad = round(8 * s)
        box = QRect(area.left() + round(16 * s), area.top() + round(16 * s),
                    max(metrics.horizontalAdvance(t) for t in lines) + 2 * pad,
                    metrics.height() * len(lines) + 2 * pad)
        p.fillRect(box, HINT_BG)
        p.setPen(QPen(HINT_BORDER, 1))
        p.drawRect(box.adjusted(0, 0, -1, -1))
        p.setFont(font)
        p.setPen(HINT_TEXT)
        for i, text in enumerate(lines):
            p.drawText(box.left() + pad, box.top() + pad + metrics.ascent() + i * metrics.height(), text)
        p.end()
        QPainter(self).drawImage(QRectF(self.rect()), canvas)

    def draw_read(self, p):
        """The latest screen read, small, on the side away from the frame."""
        if self.read is None:
            return
        s = self.scale()
        thumb = self.read.scaled(round(360 * s), round(360 * s), Qt.AspectRatioMode.KeepAspectRatio)
        margin = round(16 * s)
        left_side = self.frame.center().x() > self.area.center().x()
        x = self.area.left() + margin if left_side else self.area.right() - margin - thumb.width()
        y = self.area.bottom() - margin - thumb.height()
        p.drawImage(x, y, thumb)
        p.setPen(QPen(HINT_BORDER, 1))
        p.drawRect(QRect(x - 1, y - 1, thumb.width() + 1, thumb.height() + 1))
        p.setFont(self.font())
        p.setPen(HINT_TEXT)
        p.drawText(x, y - round(6 * s), "live read (no orange square = good)")


def print_summary(overlay):
    rate = len(overlay.read_times)
    print("Stack spike results")
    print(f"  exclude from capture: {'OK' if overlay.excluded else 'FAILED'}")
    print(f"  reads: {overlay.reads}, last second: {rate}/s")
    print(f"  overlay seen in reads: {overlay.marker_in_reads} (must be 0)")
    print(f"  wheels passed: {overlay.wheels}")
    print(f"  windows under the mouse: {', '.join(sorted(overlay.targets)) or '-'}")


def main():
    app = QApplication(sys.argv)
    load_fonts()
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    overlay = SpikeOverlay(screen)
    overlay.show()
    overlay.activateWindow()
    overlay.setFocus()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
