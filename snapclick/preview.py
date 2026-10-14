"""Small thumbnail shown bottom-right after a capture, with Save and Retake buttons."""
from PySide6.QtCore import QRect, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

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
AMBER = QColor("#FFB000")
BLUE = QColor("#8FD3FF")
GREEN = QColor("#3DDC97")


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
    elif name == "check":
        path.moveTo(5, 10.5)
        path.lineTo(8.5, 14)
        path.lineTo(15, 6.5)
    p.drawPath(path)
    p.restore()


class Preview(QWidget):
    retake = Signal()  # undo this capture and select again
    save_requested = Signal()
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
        self.saved_name = saved_path.name if saved_path else None
        self.save_state = None  # None, "saved" or "failed" (Save button only)
        self.hover = None  # "save", "retake" or None

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        # Fit the image in MAX_SIZE (screen points), never enlarge it.
        real_size = image.size() / screen.devicePixelRatio()
        thumb = real_size.scaled(MAX_SIZE, Qt.AspectRatioMode.KeepAspectRatio) \
            if real_size.width() > MAX_SIZE.width() or real_size.height() > MAX_SIZE.height() else real_size
        thumb = thumb.expandedTo(QSize(1, 2 * BUTTON_GAP + BUTTON))
        width = max(thumb.width() + 2 * PADDING, MIN_WIDTH)
        self.resize(width, PADDING + thumb.height() + LABEL_HEIGHT)
        self.image_rect = QRect((width - thumb.width()) // 2, PADDING, thumb.width(), thumb.height())
        self.label_rect = QRect(PADDING + 2, self.image_rect.bottom() + 1, width - 2 * PADDING - 4, LABEL_HEIGHT)

        # Buttons sit in the top-right corner of the image: Retake, Save to its left.
        right = self.image_rect.right() + 1 - BUTTON_GAP
        self.buttons = {"retake": QRect(right - BUTTON, self.image_rect.top() + BUTTON_GAP, BUTTON, BUTTON)}
        if can_save:
            self.buttons["save"] = self.buttons["retake"].translated(-(BUTTON + BUTTON_GAP), 0)

        self.label_font = QFont("JetBrains Mono")
        self.label_font.setPixelSize(11)

        # Save feedback animations: white flash on the image, green glow pulse.
        self.flash = self.make_animation(250)
        self.glow = self.make_animation(700)

        corner = screen.availableGeometry().bottomRight()  # above the taskbar
        self.move(corner.x() - self.width() - MARGIN, corner.y() - self.height() - MARGIN)

        # Close after 3 s, but not while the mouse is over the preview.
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(SHOW_MS)
        self.timer.timeout.connect(self.close)
        self.show()
        if not self.underMouse():
            self.timer.start()

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
        self.saved_name = path.name
        self.flash.start()
        self.glow.start()
        self.update()

    def show_save_failed(self):
        self.save_state = "failed"
        self.update()

    # --- mouse -------------------------------------------------------------

    def enterEvent(self, event):
        self.timer.stop()

    def leaveEvent(self, event):
        self.set_hover(None)
        self.timer.start()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        self.set_hover(next((name for name, rect in self.buttons.items() if rect.contains(pos)), None))

    def set_hover(self, name):
        if name != self.hover:
            self.hover = name
            clickable = name == "retake" or (name == "save" and self.save_state != "saved")
            self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if self.buttons["retake"].contains(pos):
            self.retake.emit()
        elif "save" in self.buttons and self.buttons["save"].contains(pos) and self.save_state != "saved":
            self.save_requested.emit()

    def closeEvent(self, event):
        self.timer.stop()
        self.closed.emit()
        super().closeEvent(event)

    # --- drawing -----------------------------------------------------------

    def label(self):
        """(text, color) for the line under the image."""
        if self.hover == "retake":
            return "retake · undo copy", AMBER
        if self.save_state == "saved":
            return f"saved ✓ {self.saved_name}", GREEN
        if self.save_state == "failed":
            return "save failed", MUTED
        if self.hover == "save":
            return self.save_folder, BLUE
        if self.saved_name:  # auto-saved
            return f"saved · {self.saved_name}", MUTED
        return "copied to clipboard", MUTED

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), PANEL)
        p.setPen(PANEL_BORDER)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(self.image_rect, self.image)
        if self.hover == "retake":
            p.fillRect(self.image_rect, QColor(255, 176, 0, 31))  # light amber tint (12%)
        if self.flash.state() == QVariantAnimation.State.Running:
            p.fillRect(self.image_rect, QColor(255, 255, 255, round(200 * (1 - self.flash.currentValue()))))

        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for name, rect in self.buttons.items():
            icon = name
            if name == "save" and self.save_state == "saved":
                icon, bg, color = "check", BUTTON_BG, GREEN
            elif self.hover == name:
                bg, color = (AMBER if name == "retake" else BLUE), QColor("black")
            else:
                bg, color = BUTTON_BG, ICON
            p.fillRect(rect, bg)
            if bg == BUTTON_BG:
                p.setPen(QPen(BUTTON_BORDER, 1))
                p.drawRect(QRect(rect).adjusted(0, 0, -1, -1))
            draw_icon(p, icon, rect, color)

        if self.glow.state() == QVariantAnimation.State.Running:
            t = self.glow.currentValue()
            ring = QColor(GREEN)
            ring.setAlpha(round(220 * (1 - t)))
            p.setPen(QPen(ring, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            grow = 1 + 4 * t
            p.drawRect(QRect(self.buttons["save"]).toRectF().adjusted(-grow, -grow, grow, grow))

        text, color = self.label()
        p.setFont(self.label_font)
        p.setPen(color)
        text = QFontMetrics(self.label_font).elidedText(text, Qt.TextElideMode.ElideMiddle, self.label_rect.width())
        p.drawText(self.label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
