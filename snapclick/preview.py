"""Small thumbnail shown bottom-right after a capture, with Add below, Draw, Save
and Retake buttons. While stacking (§2b) it shows the joined image and Finish."""
import subprocess

from PySide6.QtCore import QRect, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from snapclick.capture import exclude_from_capture

MAX_SIZE = QSize(240, 160)
MIN_WIDTH = 220  # room for the label
PADDING = 6
LABEL_HEIGHT = 22
MARGIN = 16
SHOW_MS = 3000
BUTTON = 20
BUTTON_GAP = 4

PANEL = QColor("#15161A")
PANEL_BORDER = QColor("#2E3035")
BUTTON_BG = QColor("#0D0E10")
BUTTON_BORDER = QColor("#34363B")
ICON = QColor("#C9C9C4")
MUTED = QColor("#A3A39E")
TEXT = QColor("#E7E7E4")
AMBER = QColor("#FFB000")
BLUE = QColor("#8FD3FF")
GREEN = QColor("#3DDC97")
VIOLET = QColor("#B197FC")
HOVER_COLORS = {"retake": AMBER, "save": BLUE, "add": TEXT, "finish": GREEN, "draw": VIOLET}


def draw_icon(p, name, box, color):
    """Line icons drawn on a 20x20 grid."""
    p.save()
    p.translate(box.topLeft())
    p.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    if name == "retake":  # back arrow
        path.moveTo(5.5, 8)
        path.lineTo(11, 8)
        path.cubicTo(16, 8, 16, 15, 11, 15)
        path.lineTo(8, 15)
        path.moveTo(8.5, 5)
        path.lineTo(5.5, 8)
        path.lineTo(8.5, 11)
    elif name == "save":  # arrow into a tray
        path.moveTo(10, 4)
        path.lineTo(10, 11.5)
        path.moveTo(7, 8.5)
        path.lineTo(10, 11.5)
        path.lineTo(13, 8.5)
        path.moveTo(4.5, 11)
        path.lineTo(4.5, 15.5)
        path.lineTo(15.5, 15.5)
        path.lineTo(15.5, 11)
    elif name == "add":  # square with a plus under it
        path.addRect(5.5, 3.5, 9, 6)
        path.moveTo(10, 11.5)
        path.lineTo(10, 17)
        path.moveTo(7.25, 14.25)
        path.lineTo(12.75, 14.25)
    elif name == "draw":  # pen, tip bottom-left
        path.moveTo(12.5, 4.5)
        path.lineTo(15.5, 7.5)
        path.lineTo(7.5, 15.5)
        path.lineTo(4.5, 15.5)
        path.lineTo(4.5, 12.5)
        path.closeSubpath()
        path.moveTo(10.5, 6.5)
        path.lineTo(13.5, 9.5)
    elif name in ("check", "finish"):
        path.moveTo(5, 10.5)
        path.lineTo(8.5, 14)
        path.lineTo(15, 6.5)
    p.drawPath(path)
    p.restore()


class Preview(QWidget):
    retake = Signal()  # undo this capture (or the last stack piece) and select again
    save_requested = Signal()
    add_below = Signal()  # start a stack
    draw = Signal()  # open the draw window (§2c)
    finish = Signal()  # stop adding to the stack
    closed = Signal()

    def __init__(self, image, can_save, save_folder, saved_path=None):
        """`can_save`: show the Save button (auto-save is off).
        `saved_path`: the file auto-save already wrote, if any."""
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)  # for button hover
        self.image = image
        self.can_save = can_save
        self.save_folder = save_folder
        self.saved_path = saved_path  # file written by auto-save or the Save button
        self.save_state = None  # None, "saved" or "failed" (Save button only)
        self.hover = None  # a button name, "link" (the file name) or None
        self.mode = "single"  # "single", "stacking" or "stacked"
        self.count = 1  # stack pieces
        self.held = False  # stays open while the draw window is open
        self.drawn = False  # the image has drawings (§2c)
        self.home = QCursor.pos()  # the preview shows on this point's monitor

        self.label_font = QFont("JetBrains Mono")
        self.label_font.setPixelSize(11)
        self.badge_font = QFont(self.label_font)
        self.badge_font.setWeight(QFont.Weight.DemiBold)

        # Save feedback animations: white flash on the image, green glow pulse.
        self.flash = self.make_animation(250)
        self.glow = self.make_animation(700)

        # Close after 3 s, but not while the mouse is over the preview.
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(SHOW_MS)
        self.timer.timeout.connect(self.close)
        self.place()
        self.show()
        if not self.underMouse():
            self.timer.start()

    def button_names(self):
        """Buttons, left to right."""
        if self.mode == "stacking":
            return ["finish", "retake"]
        names = ["add", "draw"] if self.mode == "single" else ["draw"]
        if self.can_save:
            names.append("save")
        return names + ["retake"]

    def place(self):
        """Size the window for the image and buttons; keep it bottom-right."""
        # Look the monitor up each time: Qt may replace its screen objects.
        screen = QGuiApplication.screenAt(self.home) or QGuiApplication.primaryScreen()
        # Fit the image in MAX_SIZE (screen points), never enlarge it.
        real_size = self.image.size() / screen.devicePixelRatio()
        thumb = real_size.scaled(MAX_SIZE, Qt.AspectRatioMode.KeepAspectRatio) \
            if real_size.width() > MAX_SIZE.width() or real_size.height() > MAX_SIZE.height() else real_size
        self.thumb_size = thumb
        names = self.button_names()
        badge = 28 if self.mode == "stacking" else 0
        box = thumb.expandedTo(QSize(len(names) * (BUTTON + BUTTON_GAP) + BUTTON_GAP + badge,
                                     2 * BUTTON_GAP + BUTTON))
        width = max(box.width() + 2 * PADDING, MIN_WIDTH)
        if self.mode != "single":  # stack labels are long: make room for them
            hover, self.hover = self.hover, None
            text = self.label()[0]
            self.hover = hover
            width = max(width, QFontMetrics(self.label_font).horizontalAdvance(text) + 2 * PADDING + 8)
        self.resize(width, PADDING + box.height() + LABEL_HEIGHT)
        self.image_rect = QRect((width - box.width()) // 2, PADDING, box.width(), box.height())
        self.label_rect = QRect(PADDING + 2, self.image_rect.bottom() + 1, width - 2 * PADDING - 4, LABEL_HEIGHT)

        # Buttons sit in the top-right corner of the image, right to left.
        self.buttons = {}
        right = self.image_rect.right() + 1 - BUTTON_GAP
        for name in reversed(names):
            self.buttons[name] = QRect(right - BUTTON, self.image_rect.top() + BUTTON_GAP, BUTTON, BUTTON)
            right -= BUTTON + BUTTON_GAP

        corner = screen.availableGeometry().bottomRight()  # above the taskbar
        self.move(corner.x() - self.width() - MARGIN, corner.y() - self.height() - MARGIN)

    def make_animation(self, ms):
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(ms)
        animation.valueChanged.connect(self.update)
        return animation

    # --- results from the tray -------------------------------------------

    def show_saved(self, path):
        self.save_state = "saved"
        self.saved_path = path
        self.flash.start()
        self.glow.start()
        self.update()

    def show_save_failed(self):
        self.save_state = "failed"
        self.update()

    def hold(self, on):
        """No 3 s timer while the draw window is open."""
        self.held = on
        if on:
            self.timer.stop()
        elif not self.underMouse():
            self.timer.start()

    def show_drawn(self, image):
        """The picture now has drawings: show it, and say so."""
        self.image, self.drawn = image, True
        self.place()
        self.update()

    def start_stack(self):
        """Stay open, show Finish and Retake, never appear in screen reads."""
        self.mode = "stacking"
        self.saved_path = None
        self.timer.stop()
        exclude_from_capture(self)
        self.place()
        self.update()

    def set_stack(self, image, count):
        self.image, self.count = image, count
        self.place()
        self.update()

    def finish_stack(self, image, count, saved_path):
        self.image, self.count, self.saved_path = image, count, saved_path
        self.mode = "stacked"
        self.hover = None
        self.place()
        self.update()
        if not self.underMouse():
            self.timer.start()

    # --- mouse -------------------------------------------------------------

    def enterEvent(self, event):
        self.timer.stop()

    def leaveEvent(self, event):
        self.set_hover(None)
        if self.mode != "stacking" and not self.held:
            self.timer.start()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        hover = next((name for name, rect in self.buttons.items() if rect.contains(pos)), None)
        link = self.label_parts()[2]
        if hover is None and link and link.contains(pos):
            hover = "link"
        self.set_hover(hover)

    def set_hover(self, name):
        if name != self.hover:
            self.hover = name
            clickable = name is not None and not (name == "save" and self.save_state == "saved")
            self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        name = next((name for name, rect in self.buttons.items() if rect.contains(pos)), None)
        if name == "retake":
            self.retake.emit()
        elif name == "save" and self.save_state != "saved":
            self.save_requested.emit()
        elif name == "add":
            self.add_below.emit()
        elif name == "draw":
            self.draw.emit()
        elif name == "finish":
            self.finish.emit()
        elif name is None and self.label_parts()[2] and self.label_parts()[2].contains(pos):
            self.show_in_explorer()

    def show_in_explorer(self):
        """Open File Explorer with the saved file selected."""
        if self.saved_path.exists():
            subprocess.Popen(f'explorer /select,"{self.saved_path}"')
        else:
            subprocess.Popen(f'explorer "{self.saved_path.parent}"')

    def closeEvent(self, event):
        self.timer.stop()
        self.closed.emit()
        super().closeEvent(event)

    # --- drawing -----------------------------------------------------------

    def label(self):
        """(text, file name or None, color) for the line under the image."""
        if self.mode == "stacking":
            if self.hover == "finish":
                return "finish · stop adding", None, GREEN
            if self.hover == "retake" and self.count > 1:
                return f"retake · remove piece {self.count}", None, AMBER
            if self.hover != "retake":
                return f"stack · {self.count} · scroll, then click the end", None, AMBER
        if self.hover == "retake":
            return "retake · undo copy", None, AMBER
        if self.hover == "add":
            return "add below · start a stack", None, TEXT
        if self.hover == "draw":
            return "draw · mark up", None, VIOLET
        if self.save_state == "saved":
            return "saved ✓ ", self.saved_path.name, GREEN
        if self.save_state == "failed":
            return "save failed", None, MUTED
        if self.hover == "save":
            return self.save_folder, None, BLUE
        if self.drawn:
            return "copied · with drawings", None, GREEN
        if self.mode == "stacked":
            pieces = "piece" if self.count == 1 else "pieces"
            size = f"{self.image.width()}×{self.image.height()}"
            return f"copied · {self.count} {pieces} · {size}", None, GREEN
        if self.saved_path:  # auto-saved
            return "saved · ", self.saved_path.name, MUTED
        return "copied to clipboard", None, MUTED

    def label_parts(self):
        """What to draw: (text, file name as shown, rect of the file name link)."""
        text, name, _ = self.label()
        metrics = QFontMetrics(self.label_font)
        area = self.label_rect
        if not name:
            return metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, area.width()), None, None
        start = metrics.horizontalAdvance(text)
        shown = metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, area.width() - start)
        link = QRect(area.x() + start, area.y(), metrics.horizontalAdvance(shown), area.height())
        return text, shown, link

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), PANEL)
        p.setPen(PANEL_BORDER)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

        # The image, centered in its box (the box may be wider for the buttons).
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        image_rect = QRect(0, 0, round(self.thumb_size.width()), round(self.thumb_size.height()))
        image_rect.moveCenter(self.image_rect.center())
        p.drawImage(image_rect, self.image)
        if self.hover == "retake":
            p.fillRect(self.image_rect, QColor(255, 176, 0, 31))  # light amber tint (12%)
        if self.flash.state() == QVariantAnimation.State.Running:
            p.fillRect(self.image_rect, QColor(255, 255, 255, round(200 * (1 - self.flash.currentValue()))))

        if self.mode == "stacking":  # piece count, top-left
            metrics = QFontMetrics(self.badge_font)
            text = str(self.count)
            badge = QRect(self.image_rect.left() + BUTTON_GAP, self.image_rect.top() + BUTTON_GAP,
                          max(metrics.horizontalAdvance(text) + 8, BUTTON - 4), BUTTON - 4)
            p.fillRect(badge, AMBER)
            p.setPen(QColor("black"))
            p.setFont(self.badge_font)
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for name, rect in self.buttons.items():
            icon = name
            if name == "save" and self.save_state == "saved":
                icon, bg, color = "check", BUTTON_BG, GREEN
            elif self.hover == name:
                bg, color = HOVER_COLORS[name], QColor("black")
            else:
                bg, color = BUTTON_BG, ICON
            p.fillRect(rect, bg)
            if bg == BUTTON_BG:
                p.setPen(QPen(BUTTON_BORDER, 1))
                p.drawRect(QRect(rect).adjusted(0, 0, -1, -1))
            draw_icon(p, icon, rect, color)

        if self.glow.state() == QVariantAnimation.State.Running and "save" in self.buttons:
            t = self.glow.currentValue()
            ring = QColor(GREEN)
            ring.setAlpha(round(220 * (1 - t)))
            p.setPen(QPen(ring, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            grow = 1 + 4 * t
            p.drawRect(QRect(self.buttons["save"]).toRectF().adjusted(-grow, -grow, grow, grow))

        color = self.label()[2]
        text, name, link = self.label_parts()
        p.setPen(color)
        p.setFont(self.label_font)
        p.drawText(self.label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        if name:
            link_font = QFont(self.label_font)
            link_font.setUnderline(self.hover == "link")
            p.setFont(link_font)
            p.drawText(link, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)
