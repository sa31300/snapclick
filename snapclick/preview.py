"""Small thumbnail shown bottom-right for 3 s after a capture."""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

MAX_SIZE = QSize(240, 160)
PADDING = 6
MARGIN = 16
SHOW_MS = 3000


class Preview(QWidget):
    def __init__(self, image):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.image = image

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        # Fit the image in MAX_SIZE (screen points), never enlarge it.
        real_size = image.size() / screen.devicePixelRatio()
        self.thumb = real_size.scaled(MAX_SIZE, Qt.AspectRatioMode.KeepAspectRatio) \
            if real_size.width() > MAX_SIZE.width() or real_size.height() > MAX_SIZE.height() else real_size
        self.resize(self.thumb + QSize(2 * PADDING, 2 * PADDING))

        corner = screen.availableGeometry().bottomRight()  # above the taskbar
        self.move(corner.x() - self.width() - MARGIN, corner.y() - self.height() - MARGIN)
        self.show()
        QTimer.singleShot(SHOW_MS, self.close)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#15161A"))
        p.setPen(QColor("#2E3035"))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.drawImage(self.rect().adjusted(PADDING, PADDING, -PADDING, -PADDING), self.image)
