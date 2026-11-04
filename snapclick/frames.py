"""Choose recording frames and lay them out as one numbered PNG sheet (§2d)."""
import math

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QImage, QPainter

from snapclick.capture import ACCENT, HINT_BG, mono_font

COLUMNS = 4
GAP = 8
TAG_HEIGHT = 24
MAX_SIDE = 2400


def clock_text(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class FrameBuffer:
    """Keep changed frames at sheet resolution, so full desktop images don't accumulate."""

    def __init__(self, size, count):
        self.count = count
        rows = math.ceil(count / COLUMNS)
        limit = QSize((MAX_SIDE - GAP * (COLUMNS + 1)) // COLUMNS,
                      (MAX_SIDE - GAP * (rows + 1)) // rows - TAG_HEIGHT)
        self.size = size if size.width() <= limit.width() and size.height() <= limit.height() else size.scaled(
            limit, Qt.AspectRatioMode.KeepAspectRatio)
        self.size = QSize(max(1, self.size.width()), max(1, self.size.height()))
        self.frames = []  # (seconds from start, image)

    def add(self, image, elapsed, final=False):
        if image.size() != self.size:
            image = image.scaled(self.size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        if not self.frames or final or image != self.frames[-1][1]:
            self.frames.append((elapsed, image))

    def selected(self):
        if len(self.frames) <= self.count:
            return list(self.frames)
        last = len(self.frames) - 1
        return [self.frames[round(i * last / (self.count - 1))] for i in range(self.count)]


def make_sheet(frames):
    """Four columns, labels above the pictures, and no enlargement of the pictures."""
    font = mono_font(1, semibold=True)
    metrics = QFontMetrics(font)
    labels = [f"{i + 1} · {clock_text(elapsed)}" for i, (elapsed, _) in enumerate(frames)]
    tile_width = max(frames[0][1].width(), max(metrics.horizontalAdvance(label) + 12 for label in labels))
    tile_height = frames[0][1].height() + TAG_HEIGHT
    rows = math.ceil(len(frames) / COLUMNS)
    image = QImage(COLUMNS * tile_width + (COLUMNS + 1) * GAP,
                   rows * tile_height + (rows + 1) * GAP, QImage.Format.Format_RGB32)
    image.fill(HINT_BG)
    p = QPainter(image)
    p.setFont(font)
    for i, ((_, frame), label) in enumerate(zip(frames, labels)):
        x = GAP + (i % COLUMNS) * (tile_width + GAP)
        y = GAP + (i // COLUMNS) * (tile_height + GAP)
        tag = QRect(x, y, metrics.horizontalAdvance(label) + 12, TAG_HEIGHT)
        p.fillRect(tag, ACCENT)
        p.setPen(QColor("black"))
        p.drawText(tag, Qt.AlignmentFlag.AlignCenter, label)
        p.drawImage(x, y + TAG_HEIGHT, frame)
    p.end()
    return image
