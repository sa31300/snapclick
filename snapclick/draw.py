"""Draw window (docs/SPEC.md §2c): mark up a capture before it goes to the clipboard.

The window shows the captured picture at 100% (real pixels), with a header and
a toolbar. Drawings are kept as a list of shapes in picture pixels and painted on
top; ✓ done or Enter gives the picture back with them; Esc closes with no change.
"""
import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QPolygonF
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
LINE = 3  # px in the picture, for boxes and arrows
HEAD_LENGTH, HEAD_WIDTH = 16, 12  # arrow head, px in the picture
MIN_DRAG = 4  # px; a shorter drag is a stray click, not a drawing
MARK = QColor(255, 214, 0, 110)  # see-through yellow highlight, whatever color is picked
STEP_SIZE = 26  # px in the picture: the numbered circle

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


def paint_shapes(p, shapes):
    """Paint the drawings, in picture pixels. Shape: (kind, color, start, end).
    Steps are numbered 1, 2, 3... in the order they were placed."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    number = 0
    for kind, color, start, end in shapes:
        color = QColor(color)
        if kind == "mark":
            p.fillRect(QRectF(start, end).normalized(), MARK)
        elif kind == "step":
            number += 1
            circle = QRectF(0, 0, STEP_SIZE, STEP_SIZE)
            circle.moveCenter(start)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(circle)
            font = QFont("IBM Plex Sans")
            font.setPixelSize(round(STEP_SIZE * 0.6))
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor("white"))
            p.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(number))
        elif kind == "box":
            p.setPen(QPen(color, LINE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(start, end).normalized())
        elif kind == "arrow":
            angle = math.atan2(end.y() - start.y(), end.x() - start.x())
            along = QPointF(math.cos(angle), math.sin(angle))
            across = QPointF(-along.y(), along.x())
            base = end - along * HEAD_LENGTH
            p.setPen(QPen(color, LINE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(start, base + along * 2)  # the shaft ends inside the head
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawPolygon(QPolygonF([end, base + across * (HEAD_WIDTH / 2), base - across * (HEAD_WIDTH / 2)]))


def render(image, shapes):
    """The picture with the drawings on it, same size as the capture."""
    result = image.copy()
    p = QPainter(result)
    paint_shapes(p, shapes)
    p.end()
    return result


class Canvas(QWidget):
    """The picture at 100% (one image pixel = one screen pixel) and its drawings.
    Drag with box, arrow or mark to add one; click with step."""

    def __init__(self, owner, image, ratio):
        super().__init__()
        self.owner = owner  # the draw window: tool, color and the shapes list
        self.image = image
        self.ratio = ratio  # screen pixels per Qt point on this monitor
        self.drag = None  # the shape being drawn
        self.setFixedSize(QSize(round(image.width() / ratio), round(image.height() / ratio)))
        self.setCursor(Qt.CursorShape.CrossCursor)

    def to_picture(self, pos):
        """Widget point → picture pixel, kept inside the picture."""
        return QPointF(min(max(pos.x() * self.ratio, 0), self.image.width()),
                       min(max(pos.y() * self.ratio, 0), self.image.height()))

    def mousePressEvent(self, event):
        tool = self.owner.tool()
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self.to_picture(event.position())
        if tool in ("box", "arrow", "mark"):
            self.drag = (tool, self.owner.color(), point, point)
        elif tool == "step":
            self.owner.shapes.append(("step", self.owner.color(), point, point))
            self.update()

    def mouseMoveEvent(self, event):
        if self.drag:
            kind, color, start, _ = self.drag
            self.drag = (kind, color, start, self.to_picture(event.position()))
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drag:
            kind, color, start, end = self.drag
            self.drag = None
            if math.dist((start.x(), start.y()), (end.x(), end.y())) >= MIN_DRAG:
                self.owner.shapes.append((kind, color, start, end))
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.scale(1 / self.ratio, 1 / self.ratio)
        p.drawImage(0, 0, self.image)
        paint_shapes(p, self.owner.shapes + ([self.drag] if self.drag else []))


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
        self.shapes = []  # drawings, oldest first: (kind, color, start, end) in picture pixels
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
        undo = self.button("↶ undo")
        undo.clicked.connect(self.undo)
        row.addWidget(undo)
        row.addSpacing(8)
        done = self.button("✓ done", object_name="done")
        done.clicked.connect(self.finish)
        row.addWidget(done)

        scroll = QScrollArea()
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.canvas = Canvas(self, image, screen.devicePixelRatio())
        scroll.setWidget(self.canvas)

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

    def tool(self):
        return self.tools.checkedButton().property("name")

    def color(self):
        return COLORS[self.colors.checkedButton().property("name")]

    def undo(self):
        if self.shapes:
            self.shapes.pop()
            self.canvas.update()

    def finish(self):
        self.done.emit(render(self.image, self.shapes))
        self.close()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
