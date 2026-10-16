"""Stack: long captures made of several pieces (docs/SPEC.md §2b).

The screen is live. Snapclick reads the frame many times a second and keeps a
long image of everything that scrolled through it (see matcher.py). A click
below the captured part adds the part from its end down to the click; a click
above it adds the part from the click down to its start.

Reading runs in a background thread: a screen read waits for the next screen
refresh, and the overlay can be painted meanwhile.
"""
import ctypes
import threading
import time
from ctypes import wintypes

from PySide6.QtCore import (QAbstractNativeEventFilter, QCoreApplication, QObject, QPoint, QRect, QRectF, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from snapclick.capture import (ACCENT, CROSSHAIR, DIM, HINT_BG, HINT_BORDER, HINT_TEXT, draw_label, draw_magnifier,
                               exclude_from_capture, grab, label_width, mono_font, physical_rect)
from snapclick.matcher import LongImage, image_rows, rows_image

READ_MS = 40  # at most 25 screen reads per second (spec: at least 15)
LIVE_MARGIN = 160  # px around the mouse read with the frame, for the magnifier
LOST = QColor("#FF6B6B")
STRIPES = QColor(255, 176, 0, round(255 * 0.4))
SEE_THROUGH = QColor(0, 0, 0, 1)  # invisible, but the overlay still gets the mouse

GW_HWNDNEXT = 2
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WM_MOUSEWHEEL = 0x020A
DWMWA_CLOAKED = 14
CWP_SKIPINVISIBLE, CWP_SKIPTRANSPARENT = 0x1, 0x4
GA_ROOT = 2
WM_HOTKEY = 0x0312
VK_ESCAPE = 0x1B
ESC_HOTKEY_ID = 2  # 1 is PrtSc

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.ChildWindowFromPointEx.argtypes = [wintypes.HWND, wintypes.POINT, wintypes.UINT]
user32.ChildWindowFromPointEx.restype = wintypes.HWND
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
OWN_PID = ctypes.windll.kernel32.GetCurrentProcessId()


# --- passing the wheel on --------------------------------------------------

def is_target(hwnd, point):
    """A visible window of another app that is under `point`."""
    if not user32.IsWindowVisible(hwnd):
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == OWN_PID:
        return False
    cloaked = wintypes.DWORD()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), 4)
    if cloaked.value or user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_TRANSPARENT:
        return False
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom


def window_below(overlay_hwnd, point):
    """The deepest window under `point`, looking only below the overlay."""
    hwnd = user32.GetWindow(overlay_hwnd, GW_HWNDNEXT)
    while hwnd and not is_target(hwnd, point):
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
    while hwnd:
        local = wintypes.POINT(point.x, point.y)
        user32.ScreenToClient(hwnd, ctypes.byref(local))
        child = user32.ChildWindowFromPointEx(hwnd, local, CWP_SKIPINVISIBLE | CWP_SKIPTRANSPARENT)
        if not child or child == hwnd:
            break
        hwnd = child
    return hwnd


def pass_wheel(overlay_hwnd, delta):
    """Send a wheel turn to the window under the mouse, below the overlay."""
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    target = window_below(overlay_hwnd, point)
    if target:
        wparam = (delta & 0xFFFF) << 16  # no keys held
        lparam = ((point.y & 0xFFFF) << 16) | (point.x & 0xFFFF)
        user32.PostMessageW(target, WM_MOUSEWHEEL, wparam, lparam)


class EscapeKey(QAbstractNativeEventFilter):
    """Esc ends the stack while another app has the keyboard (see Stack)."""

    def __init__(self, on_press):
        super().__init__()
        self.on_press = on_press
        QCoreApplication.instance().installNativeEventFilter(self)
        self.registered = bool(user32.RegisterHotKey(None, ESC_HOTKEY_ID, 0, VK_ESCAPE))

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == ESC_HOTKEY_ID:
                QTimer.singleShot(0, self.on_press)
                return True, 0
        return False, 0

    def close(self):
        QCoreApplication.instance().removeNativeEventFilter(self)
        if self.registered:
            user32.UnregisterHotKey(None, ESC_HOTKEY_ID)
            self.registered = False


# --- the stack -------------------------------------------------------------

class Stack(QObject):
    """One stack session: overlays on every monitor over the live screen."""

    changed = Signal()  # a piece was added
    finished = Signal()  # Esc, right-click (or finish() from the preview)
    read_done = Signal()  # from the reading thread

    def __init__(self, frame, first, other_windows=()):
        """`frame` = piece 1's rectangle (real pixels), `first` = piece 1's image."""
        super().__init__()
        self.frame = frame
        self.long = LongImage(image_rows(first))
        # Pieces 2, 3...: ("below", end row) or ("above", start row). Rows are
        # counted from long.above, so they stay right when lines are added above.
        self.pieces = []
        self.cursor = None
        self.live = None  # (image, origin): the last screen read, frame and mouse area
        self.other_windows = list(other_windows)  # e.g. the preview
        self.overlays = [StackOverlay(self, screen) for screen in QGuiApplication.screens()]
        for overlay in self.overlays:
            overlay.show()
        self.excluded = all([exclude_from_capture(w) for w in self.overlays + self.other_windows])
        # Make the app under the frame the active window again, as it was when
        # piece 1 was taken: active and inactive windows have different title
        # bars and borders. The overlay never takes the keyboard, so Esc is a hotkey.
        center = wintypes.POINT(frame.center().x(), frame.center().y())
        target = window_below(int(self.overlays[0].winId()), center)
        if target:
            user32.SetForegroundWindow(user32.GetAncestor(target, GA_ROOT))
        self.escape = EscapeKey(self.finish)
        mouse_screen = QGuiApplication.screenAt(QCursor.pos())
        under_mouse = next((o for o in self.overlays if o.screen() == mouse_screen), self.overlays[0])
        self.cursor = under_mouse.to_physical(under_mouse.mapFromGlobal(QCursor.pos()))

        self.lock = threading.Lock()  # guards self.long and self.live
        self.shown = None  # the matcher state the overlay shows
        self.read_done.connect(self.show_read)
        self.running = True
        self.timer = None
        if self.excluded:
            self.reader = threading.Thread(target=self.read_loop, daemon=True)
            self.reader.start()
        else:  # hiding our windows for a read must happen in this thread
            self.timer = QTimer(self)
            self.timer.timeout.connect(lambda: (self.read(), self.show_read()))
            self.timer.start(READ_MS)

    def count(self):
        return 1 + len(self.pieces)

    def start(self):
        """Long-image row where the captured part starts (after the header)."""
        starts = [row for side, row in self.pieces if side == "above"]
        return min(starts, default=self.long.header) + self.long.above

    def end(self):
        """Long-image row where the captured part ends."""
        ends = [row for side, row in self.pieces if side == "below"]
        return max(ends) + self.long.above if ends else self.long.piece1_end

    def image(self):
        """All pieces joined into one image: header (title bar), then the captured part."""
        with self.lock:
            rows = self.long.rows
            return rows_image(rows[:self.long.header] + rows[self.start():self.end()], self.frame.width())

    def grab_live(self, rect):
        if self.excluded:
            return grab(rect)
        # Older Windows can't leave our windows out: hide them for the moment of the read.
        windows = self.overlays + self.other_windows
        for w in windows:
            w.setWindowOpacity(0)
        dwmapi.DwmFlush()
        image = grab(rect)
        for w in windows:
            w.setWindowOpacity(1)
        return image

    def read_loop(self):
        while self.running:
            start = time.perf_counter()
            self.read()
            if self.running:
                self.read_done.emit()
            time.sleep(max(0.0, READ_MS / 1000 - (time.perf_counter() - start)))

    def read(self):
        """Read the frame, and the area around the mouse for the magnifier, in one go:
        each screen read waits for the next screen refresh."""
        area = QRect(self.frame)
        cursor = self.cursor
        if cursor is not None:
            area = area.united(QRect(cursor.x() - LIVE_MARGIN, cursor.y() - LIVE_MARGIN,
                                     2 * LIVE_MARGIN + 1, 2 * LIVE_MARGIN + 1))
        image = self.grab_live(area)
        rows = image_rows(image.copy(self.frame.translated(-area.topLeft())))
        with self.lock:
            self.long.add_read(rows)
            self.live = (image, area.topLeft())

    def show_read(self):
        """Repaint the frame if the text moved (or got lost or found)."""
        long = self.long
        state = (long.pos, long.lost, long.top, long.bottom)
        if state != self.shown:
            self.shown = state
            self.update(self.frame)

    def content(self):
        """Top and bottom (exclusive) screen rows of the frame that show moving text."""
        top = self.frame.top() + self.long.top
        return top, self.frame.top() + self.long.height - self.long.bottom

    def start_y(self):
        """Screen row of the start line (may be off the frame)."""
        return self.frame.top() + self.start() - self.long.pos

    def end_y(self):
        """Screen row of the end line (may be off the frame)."""
        return self.frame.top() + self.end() - self.long.pos

    def move(self, point):
        old, self.cursor = self.cursor, point
        self.update(self.frame, QRect(point, point), QRect(old, old) if old else None)

    def click(self, point):
        with self.lock:  # uses the last read, which is what the overlay shows
            if self.long.lost:
                return
            long = self.long
            top, bottom = self.content()
            y = min(max(point.y(), top), bottom)  # outside the frame = its nearest edge
            row = min(max(long.pos + y - self.frame.top(), long.header), len(long.rows))
            if row > self.end():
                self.pieces.append(("below", row - long.above))
            elif row < self.start():
                self.pieces.append(("above", row - long.above))
            else:
                return  # inside the captured part
        self.update()
        self.changed.emit()

    def remove_last(self):
        if self.pieces:
            self.pieces.pop()
            self.update()

    def update(self, *areas):
        """Repaint the monitors that show these areas (all if none given)."""
        areas = [a for a in areas if a is not None]
        for overlay in self.overlays:
            if not areas or any(overlay.area.intersects(a.adjusted(-1, -1, 1, 1)) for a in areas):
                overlay.update()

    def close(self):
        """Stop without the finished signal."""
        self.running = False
        if self.timer:
            self.timer.stop()
        else:
            self.reader.join()
        self.escape.close()
        for overlay in self.overlays:
            overlay.close()
        self.overlays = []

    def finish(self):
        if self.running:  # Esc twice, or Esc and the Finish button: finish once
            self.close()
            self.finished.emit()


class StackOverlay(QWidget):
    """See-through window on one monitor: dims around the frame, shows the stack."""

    def __init__(self, stack, screen):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.stack = stack
        self.area = physical_rect(screen)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
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

    # --- input -------------------------------------------------------------

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            pass_wheel(int(self.winId()), delta)

    def mouseMoveEvent(self, event):
        self.stack.move(self.to_physical(event.position()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.stack.click(self.to_physical(event.position()))
        elif event.button() == Qt.MouseButton.RightButton:
            self.stack.finish()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.stack.finish()

    # --- drawing -----------------------------------------------------------

    def paintEvent(self, event):
        # Draw in real pixels (see capture.Overlay). See-through in the frame's
        # columns, top to bottom of the monitor that shows the frame.
        s = self.scale()
        line = max(1, int(s))
        stack, long, frame, area = self.stack, self.stack.long, self.stack.frame, self.area
        canvas = QImage(area.size(), QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(SEE_THROUGH)
        p = QPainter(canvas)
        p.translate(-area.topLeft())
        p.fillRect(area, DIM)
        strip = QRect(frame.left(), area.top(), frame.width(), area.height()) if area.intersects(frame) else frame
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(strip, SEE_THROUGH)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        top, bottom = stack.content()
        start_y, end_y = stack.start_y(), stack.end_y()
        cursor = stack.cursor
        shade_top = max(start_y, top)
        shade = QRect(frame.left(), shade_top, frame.width(), min(end_y, bottom) - shade_top)
        striped = not long.lost and shade.height() > 0
        if striped:
            self.draw_shade(p, shade, line)

        # Guide lines: only the strip's sides, top to bottom of the monitor.
        dash = QPen(ACCENT, line, Qt.PenStyle.CustomDashLine)
        dash.setDashPattern([4, 3])
        p.setPen(dash)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(strip.topLeft(), strip.bottomLeft())
        p.drawLine(strip.topRight(), strip.bottomRight())

        font, bold = mono_font(s), mono_font(s, semibold=True)
        tag_x, tag_y = frame.left() + round(6 * s), top + round(6 * s)
        if long.lost:
            draw_label(p, "jumped too far · scroll back to the shade", font, tag_x, tag_y, LOST, HINT_BG,
                       area, s, LOST)
        else:
            height = round(mono_font(s).pixelSize() * 1.4 + 6 * s)  # of a tag
            if top <= end_y <= bottom:
                p.setPen(QPen(ACCENT, line))
                p.drawLine(frame.left(), end_y, frame.right(), end_y)
                text = "already captured ↑"
                draw_label(p, text, bold, frame.right() + 1 - label_width(text, bold, s), end_y - height,
                           QColor("black"), ACCENT, area, s)
            elif end_y < top:
                draw_label(p, f"↑ + {top - end_y} px above, recorded while scrolling", font, tag_x, tag_y,
                           ACCENT, HINT_BG, area, s, ACCENT)
            if top < start_y <= bottom:  # scrolled up: the start of the captured part is on screen
                p.setPen(QPen(ACCENT, line))
                p.drawLine(frame.left(), start_y, frame.right(), start_y)
                text = "already captured ↓"
                draw_label(p, text, bold, frame.right() + 1 - label_width(text, bold, s), start_y + line,
                           QColor("black"), ACCENT, area, s)
            elif start_y > bottom:
                draw_label(p, f"↓ + {start_y - bottom} px below, recorded while scrolling", font, tag_x,
                           bottom - height - round(6 * s), ACCENT, HINT_BG, area, s, ACCENT)
            if cursor is not None:
                self.draw_next_piece(p, cursor, top, bottom, start_y, end_y, dash, bold)

        if cursor is not None and area.contains(cursor):
            p.setPen(QPen(CROSSHAIR, line))
            p.drawLine(area.left(), cursor.y(), area.right(), cursor.y())
            p.drawLine(cursor.x(), area.top(), cursor.x(), area.bottom())
            if long.lost:
                hint = "[wheel] scroll back   [esc] done"
            else:
                hint = f"[wheel] scroll   [click] end of piece {stack.count() + 1}   [esc] done"
            margin = round(16 * s)
            draw_label(p, hint, font, area.left() + margin, area.top() + margin, HINT_TEXT, HINT_BG, area, s,
                       HINT_BORDER)
            if stack.live:
                draw_magnifier(p, *stack.live, cursor, area, s)  # from the last screen read

        p.end()
        QPainter(self).drawImage(QRectF(self.rect()), canvas)

    def draw_shade(self, p, shade, line):
        """Already captured: dim plus thin diagonal stripes."""
        p.fillRect(shade, DIM)
        p.save()
        p.setClipRect(shade)
        p.setPen(QPen(STRIPES, line))
        step = round(8 * self.scale())
        x = shade.left() - shade.height()
        while x < shade.right():
            p.drawLine(x, shade.bottom(), x + shade.height(), shade.top())
            x += step
        p.restore()

    def draw_next_piece(self, p, cursor, top, bottom, start_y, end_y, dash, bold):
        """Dashed box from the end line down to the mouse (or from the mouse down to
        the start line), with the piece's full height. No edge where the piece
        goes on off screen."""
        frame, s = self.stack.frame, self.scale()
        mouse_y = min(max(cursor.y(), top), bottom)
        if mouse_y > max(end_y, top):  # below the captured part
            piece = QRect(frame.left(), max(end_y, top), frame.width(), mouse_y - max(end_y, top))
            open_top, open_bottom = end_y < top, False
            size = mouse_y - end_y
            badge_y = piece.bottom() + 1 + round(6 * s)
        elif mouse_y < min(start_y, bottom):  # above it
            piece = QRect(frame.left(), mouse_y, frame.width(), min(start_y, bottom) - mouse_y)
            open_top, open_bottom = False, start_y > bottom
            size = start_y - mouse_y
            badge_y = piece.top() - round(mono_font(s).pixelSize() * 1.4 + 12 * s)
        else:
            return
        p.setPen(dash)
        p.drawLine(piece.topLeft(), piece.bottomLeft())
        p.drawLine(piece.topRight(), piece.bottomRight())
        if not open_top:
            p.drawLine(piece.topLeft(), piece.topRight())
        if not open_bottom:
            p.drawLine(piece.bottomLeft(), piece.bottomRight())
        text = f"{frame.width()}×{size}"
        draw_label(p, text, bold, piece.right() + 1 - label_width(text, bold, s), badge_y,
                   QColor("black"), ACCENT, self.area, s)
