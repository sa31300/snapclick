"""Draw window (docs/SPEC.md §2c): mark up a capture before it goes to the clipboard.

The window shows the captured picture at 100% (real pixels), with a header and
a toolbar. ✓ done or Enter gives the picture back; Esc closes it with no change.
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

BG = "#0D0E10"
PANEL = "#15161A"
BORDER = "#34363B"
TEXT = "#C9C9C4"
MUTED = "#A3A39E"
VIOLET = "#B197FC"
GREEN = "#3DDC97"
TOOLS = [("arrow", "→ arrow"), ("box", "□ box"), ("mark", "▬ mark"), ("text", "T text"), ("blur", "▦ blur"),
         ("step", "1 step")]
COLORS = {"red": "#E5383B", "blue": "#2F80ED", "green": "#27AE60"}
SCREEN_PART = 0.9  # the window is at most 90% of the monitor

STYLE = f"""
QWidget#draw {{ background: {BG}; border: 1px solid {BORDER}; }}
QWidget#header, QWidget#toolbar {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}
QLabel {{ color: {MUTED}; font-family: "JetBrains Mono"; font-size: 12px; }}
QPushButton {{ color: {TEXT}; background: transparent; border: none; padding: 5px 9px;
               font-family: "JetBrains Mono"; font-size: 12px; }}
QPushButton:hover {{ background: {PANEL}; }}
QPushButton:checked {{ background: {VIOLET}; color: black; }}
QPushButton#color {{ border: 2px solid transparent; padding: 0; min-width: 14px; max-width: 14px;
                     min-height: 14px; max-height: 14px; }}
QPushButton#color:checked {{ border: 2px solid white; }}
QPushButton#done {{ color: {GREEN}; border: 1px solid {GREEN}; padding: 5px 14px; }}
QScrollArea {{ background: {BG}; border: none; }}
QScrollBar {{ background: {BG}; width: 10px; height: 10px; }}
QScrollBar::handle {{ background: {BORDER}; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
"""


def draw_title(mode, count, image):
    """The header's right side: `shot · 810×282` or `stack · 3 pieces · 810×1050`."""
    size = f"{image.width()}×{image.height()}"
    if mode == "single":
        return f"shot · {size}"
    return f"stack · {count} {'piece' if count == 1 else 'pieces'} · {size}"


class Canvas(QWidget):
    """The picture at 100%: one image pixel = one screen pixel."""

    def __init__(self, image, ratio):
        super().__init__()
        self.image = image
        self.ratio = ratio  # screen pixels per Qt point on this monitor
        self.setFixedSize(QSize(round(image.width() / ratio), round(image.height() / ratio)))

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(self.rect(), self.image)


class DrawWindow(QWidget):
    done = Signal(object)  # the picture (QImage), from ✓ done or Enter
    closed = Signal()  # closed by ✓ done, Enter or Esc

    def __init__(self, image, title, home):
        """`home`: a point on the monitor to open on (the preview's)."""
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setObjectName("draw")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.image = image
        screen = QGuiApplication.screenAt(home) or QGuiApplication.primaryScreen()

        header = QWidget(objectName="header")
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 6, 12, 6)
        row.addWidget(QLabel("snapclick · draw"))
        row.addStretch()
        row.addWidget(QLabel(title))

        toolbar = QWidget(objectName="toolbar")
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(2)
        self.tools = QButtonGroup(self)
        for name, text in TOOLS:
            row.addWidget(self.button(text, name, self.tools, checked=name == "box"))
        row.addSpacing(10)
        self.colors = QButtonGroup(self)
        for name, color in COLORS.items():
            swatch = self.button("", name, self.colors, checked=name == "red", object_name="color")
            swatch.setStyleSheet(f"background: {color};")
            row.addWidget(swatch)
            row.addSpacing(4)
        row.addStretch()
        row.addWidget(self.button("↶ undo"))
        row.addSpacing(8)
        done = self.button("✓ done", object_name="done")
        done.clicked.connect(self.finish)
        row.addWidget(done)

        scroll = QScrollArea()
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setWidget(Canvas(image, screen.devicePixelRatio()))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(toolbar)
        layout.addWidget(scroll)

        # As big as the picture, at most 90% of the monitor; centered on it.
        area = screen.availableGeometry()
        chrome = header.sizeHint().height() + toolbar.sizeHint().height() + 2
        bar = 12  # room for a scrollbar
        width = max(toolbar.sizeHint().width() + 2, scroll.widget().width() + bar)
        height = chrome + scroll.widget().height() + bar
        self.resize(min(width, int(area.width() * SCREEN_PART)), min(height, int(area.height() * SCREEN_PART)))
        self.move(area.center() - self.rect().center())
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def button(self, text, name=None, group=None, checked=False, object_name=None):
        button = QPushButton(text)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Enter and Esc always reach the window
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if object_name:
            button.setObjectName(object_name)
        if group:
            button.setCheckable(True)
            button.setChecked(checked)
            group.addButton(button)
            button.setProperty("name", name)
        return button

    def finish(self):
        self.done.emit(self.image)
        self.close()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
