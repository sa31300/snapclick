"""Small thumbnail shown bottom-right after a capture, with an undo-and-retake ✕."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

MAX_SIZE = QSize(240, 160)
PADDING = 6
MARGIN = 16
SHOW_MS = 3000
BUTTON = 18  # ✕ button size

ACCENT = QColor("#FFB000")
BUTTON_BG = QColor("#0D0E10")
BUTTON_BORDER = QColor("#34363B")
BUTTON_TEXT = QColor("#C9C9C4")


class Preview(QWidget):
    retake = Signal()  # the ✕ was clicked
    closed = Signal()

    def __init__(self, image):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)  # to highlight the ✕ on hover
        self.image = image
        self.hover_button = False

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        # Fit the image in MAX_SIZE (screen points), never enlarge it.
        real_size = image.size() / screen.devicePixelRatio()
        self.thumb = real_size.scaled(MAX_SIZE, Qt.AspectRatioMode.KeepAspectRatio) \
            if real_size.width() > MAX_SIZE.width() or real_size.height() > MAX_SIZE.height() else real_size
        # Never smaller than the ✕ button needs.
        self.thumb = self.thumb.expandedTo(QSize(BUTTON + 8, BUTTON + 8))
        self.resize(self.thumb + QSize(2 * PADDING, 2 * PADDING))
        self.button = QRect(self.width() - PADDING - BUTTON, PADDING, BUTTON, BUTTON)

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

    def enterEvent(self, event):
        self.timer.stop()

    def leaveEvent(self, event):
        self.set_hover(False)
        self.timer.start()

    def mouseMoveEvent(self, event):
        self.set_hover(self.button.contains(event.position().toPoint()))

    def set_hover(self, on):
        if on != self.hover_button:
            self.hover_button = on
            self.setCursor(Qt.CursorShape.PointingHandCursor if on else Qt.CursorShape.ArrowCursor)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.button.contains(event.position().toPoint()):
            self.retake.emit()

    def closeEvent(self, event):
        self.timer.stop()
        self.closed.emit()
        super().closeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#15161A"))
        p.setPen(QColor("#2E3035"))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.drawImage(self.rect().adjusted(PADDING, PADDING, -PADDING, -PADDING), self.image)

        # ✕ button: square, style B; accent with black ✕ on hover.
        p.fillRect(self.button, ACCENT if self.hover_button else BUTTON_BG)
        if not self.hover_button:
            p.setPen(BUTTON_BORDER)
            p.drawRect(self.button.adjusted(0, 0, -1, -1))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("black") if self.hover_button else BUTTON_TEXT, 1.5))
        cross = self.button.adjusted(6, 6, -6, -6)
        p.drawLine(cross.topLeft(), cross.bottomRight() + QPoint(1, 1))
        p.drawLine(cross.topRight() + QPoint(1, 0), cross.bottomLeft() + QPoint(0, 1))
