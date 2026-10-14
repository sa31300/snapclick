r"""Make docs/demo.gif: the real overlay code, run on a neutral demo screen.

    .venv\Scripts\python tools\make_demo_gif.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPolygon
from PySide6.QtWidgets import QApplication

from snapclick import capture
from snapclick.__main__ import load_fonts
from snapclick.preview import Preview

OUT = Path(__file__).resolve().parent.parent / "docs" / "demo.gif"
W, H = 960, 640  # GIF size (tall enough for the magnifier)


def draw_scene(image, at):
    """A plain 'report' window with a bar chart, drawn at `at` (desktop pixels)."""
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.fillRect(image.rect(), QColor("#2B3A4A"))  # wallpaper
    p.translate(at)
    p.fillRect(60, 40, 840, 460, QColor("white"))
    p.fillRect(60, 40, 840, 34, QColor("#EDEDED"))
    p.setPen(QColor("#333"))
    p.setFont(QFont("IBM Plex Sans", 11))
    p.drawText(QRect(76, 40, 600, 34), Qt.AlignmentFlag.AlignVCenter, "Q3 sales report")
    for i, width in enumerate((520, 600, 440)):  # text lines
        p.fillRect(100, 100 + i * 22, width, 9, QColor("#D5D5D5"))
    p.setFont(QFont("IBM Plex Sans", 13, QFont.Weight.Medium))
    p.drawText(130, 205, "Revenue by region")
    p.setPen(QColor("#CCC"))
    p.drawLine(130, 420, 590, 420)
    p.setFont(QFont("IBM Plex Sans", 10))
    for i, (name, value, color) in enumerate([("North", 150, "#3B6FD4"), ("South", 95, "#3B6FD4"),
                                              ("East", 175, "#E07B39"), ("West", 120, "#3B6FD4")]):
        x = 160 + i * 110
        p.fillRect(x, 420 - value, 60, value, QColor(color))
        p.setPen(QColor("#555"))
        p.drawText(QRect(x - 10, 426, 80, 20), Qt.AlignmentFlag.AlignHCenter, name)
    for i, width in enumerate((200, 160, 220, 180)):  # notes on the right
        p.fillRect(650, 240 + i * 22, width, 9, QColor("#D5D5D5"))
    p.end()


def pointer(image, at):
    """A plain arrow mouse pointer with its tip at `at`."""
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor("black"))
    p.setBrush(QColor("white"))
    shape = [(0, 0), (0, 17), (4, 13), (7, 20), (10, 19), (7, 12), (12, 12)]
    p.drawPolygon(QPolygon([at + QPoint(x, y) for x, y in shape]))
    p.end()


def keycap(image, text):
    p = QPainter(image)
    p.setFont(QFont("JetBrains Mono", 14, QFont.Weight.DemiBold))
    box = QRect(24, H - 64, 96, 40)
    p.fillRect(box, QColor("#0D0E10"))
    p.setPen(QColor("#FFB000"))
    p.drawRect(box.adjusted(0, 0, -1, -1))
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
    p.end()


def to_pil(image):
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    return Image.frombytes("RGB", (image.width(), image.height()), bytes(image.constBits())[: image.sizeInBytes()],
                           "raw", "RGB", image.bytesPerLine())


def main():
    app = QApplication(sys.argv)
    load_fonts()

    # Use the real overlay, but on the demo screen instead of a real screenshot.
    real_grab = capture.grab_desktop
    desktop, origin = real_grab()
    screen = min(QApplication.screens(), key=lambda s: s.devicePixelRatio())  # sharpest text
    area = capture.physical_rect(screen)
    crop = QRect(area.x() + (area.width() - W) // 2, area.y() + (area.height() - H) // 2, W, H)
    demo = QImage(desktop.size(), QImage.Format.Format_RGB32)
    draw_scene(demo, crop.topLeft() - origin)
    capture.grab_desktop = lambda: (demo, origin)

    frames = []  # (image, ms)

    def add(image, ms=70):
        frames.append((to_pil(image), ms))

    still = demo.copy(crop.translated(-origin))
    add(still, 700)
    pressed = still.copy()
    keycap(pressed, "PrtSc")
    add(pressed, 600)

    c = capture.Capture()
    overlay = next(o for o in c.overlays if o.area == area)
    local = crop.translated(-area.topLeft())

    def shot(ms=70):
        app.processEvents()
        add(overlay.grab().toImage().copy(local), ms)

    def glide(start, end, steps):
        for i in range(1, steps + 1):
            t = i / steps
            t = t * t * (3 - 2 * t)  # ease in/out
            c.move(crop.topLeft() + start + (end - start) * t)
            shot()

    corner1, corner2 = QPoint(116, 176), QPoint(610, 455)
    c.move(crop.topLeft() + QPoint(720, 120))
    shot(300)
    glide(QPoint(720, 120), corner1, 12)
    c.first = crop.topLeft() + corner1
    shot(400)
    glide(corner1, corner2, 16)
    shot(900)
    selection = c.selection()
    result = c.image.copy(selection.translated(-origin))
    c.close()

    # After click 2: back to the normal screen, with the real preview thumbnail.
    # A neutral folder name, and no real file is written.
    preview = Preview(result, can_save=True, save_folder=r"C:\Users\you\Pictures\Snapclick")

    def with_preview(ms, mouse=False):
        thumb = preview.grab().toImage()
        corner = QPoint(W - thumb.width() - 16, H - thumb.height() - 16)
        frame = still.copy()
        p = QPainter(frame)
        p.drawImage(corner, thumb)
        p.end()
        if mouse:
            pointer(frame, corner + preview.buttons["save"].center() + QPoint(2, 3))
        add(frame, ms)

    with_preview(900)  # "copied to clipboard"
    preview.set_hover("save")  # Save turns baby blue, label shows the folder
    with_preview(1100, mouse=True)
    preview.show_saved(Path("2026-10-14_18-12-05.png"))  # flash, green check, glow
    for ms in (0, 60, 120, 200, 300, 420, 560):
        preview.flash.setCurrentTime(ms)
        preview.glow.setCurrentTime(ms)
        with_preview(60, mouse=True)
    preview.flash.stop()
    preview.glow.stop()
    preview.set_hover(None)
    with_preview(2200)  # "saved ✓ 2026-10-14_18-12-05.png"
    preview.close()

    images = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f, _ in frames]
    images[0].save(OUT, save_all=True, append_images=images[1:], duration=[ms for _, ms in frames],
                   loop=0, optimize=True)
    print(f"{OUT} — {len(frames)} frames, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
