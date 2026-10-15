r"""Make docs/demo.gif and docs/stack.gif: the real overlay code, run on a
neutral demo screen with made-up content (no real screen is shown).

    .venv\Scripts\python tools\make_demo_gif.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPolygon
from PySide6.QtWidgets import QApplication

from snapclick import capture, stack
from snapclick.__main__ import load_fonts
from snapclick.preview import Preview

DOCS = Path(__file__).resolve().parent.parent / "docs"
OUT = DOCS / "demo.gif"
STACK_OUT = DOCS / "stack.gif"
W, H = 960, 640  # GIF size (tall enough for the magnifier)
SAVE_FOLDER = r"C:\Users\you\Pictures\Snapclick"  # a neutral folder name


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


def keycap(image, text, width=96):
    p = QPainter(image)
    p.setFont(QFont("JetBrains Mono", 14, QFont.Weight.DemiBold))
    box = QRect(24, H - 64, width, 40)
    p.fillRect(box, QColor("#0D0E10"))
    p.setPen(QColor("#FFB000"))
    p.drawRect(box.adjusted(0, 0, -1, -1))
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
    p.end()


def to_pil(image):
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    return Image.frombytes("RGB", (image.width(), image.height()), bytes(image.constBits())[: image.sizeInBytes()],
                           "raw", "RGB", image.bytesPerLine())


def save_gif(frames, path):
    images = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f, _ in frames]
    images[0].save(path, save_all=True, append_images=images[1:], duration=[ms for _, ms in frames],
                   loop=0, optimize=True)
    print(f"{path} — {len(frames)} frames, {path.stat().st_size // 1024} KB")


def make_capture_gif(app):
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
    preview = Preview(result, can_save=True, save_folder=SAVE_FOLDER)

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
    capture.grab_desktop = real_grab
    save_gif(frames, OUT)


# --- the stack GIF ---------------------------------------------------------

LINE_HEIGHT = 20
WINDOW = QRect(40, 40, 620, 540)  # the made-up terminal, in GIF pixels
TEXT_TOP = WINDOW.top() + 40
TEXT_BOTTOM = WINDOW.bottom() - 10
FRAME = QRect(60, 88, 560, 400)  # piece 1, inside the text


def log_lines():
    """A made-up test run, every line different."""
    names = ["parser", "cache", "export", "layout", "colors", "fonts", "config", "images", "history", "sync"]
    lines = ["$ make test"]
    for i in range(1, 140):
        lines.append(f"{i:03d}  PASS  tests/test_{names[i % 10]}.py::case_{(i * 7) % 50:02d}")
    return lines


def draw_terminal(scroll):
    """The demo screen with the terminal scrolled down by `scroll` px."""
    image = QImage(W, H, QImage.Format.Format_RGB32)
    p = QPainter(image)
    p.fillRect(image.rect(), QColor("#2B3A4A"))  # wallpaper
    p.fillRect(WINDOW, QColor("#0C0C0C"))
    p.fillRect(WINDOW.x(), WINDOW.y(), WINDOW.width(), 30, QColor("#202124"))
    p.setPen(QColor("#C9C9C4"))
    p.setFont(QFont("IBM Plex Sans", 10))
    p.drawText(QRect(WINDOW.x() + 14, WINDOW.y(), 300, 30), Qt.AlignmentFlag.AlignVCenter, "Terminal")
    p.setClipRect(QRect(WINDOW.x(), TEXT_TOP, WINDOW.width(), TEXT_BOTTOM - TEXT_TOP))
    font = QFont("JetBrains Mono")
    font.setPixelSize(13)
    p.setFont(font)
    char = p.fontMetrics().horizontalAdvance("0")
    for i, line in enumerate(log_lines()):
        y = TEXT_TOP + 8 + i * LINE_HEIGHT - scroll
        if TEXT_TOP - LINE_HEIGHT < y < TEXT_BOTTOM + LINE_HEIGHT:
            x = WINDOW.x() + 20
            if "PASS" in line:
                for start, text, color in ((0, line[:5], "#A3A39E"), (5, "PASS", "#3DDC97"), (11, line[11:], "#E7E7E4")):
                    p.setPen(QColor(color))
                    p.drawText(x + start * char, y + 14, text)
            else:
                p.setPen(QColor("#E7E7E4"))
                p.drawText(x, y + 14, line)
    p.end()
    return image


def make_stack_gif(app):
    """Piece 1 is taken; Add below, scroll, click twice, Finish."""
    screen = min(QApplication.screens(), key=lambda s: s.devicePixelRatio())  # sharpest text
    area = capture.physical_rect(screen)
    crop = QRect(area.topLeft(), QRect(0, 0, W, H).size())  # top-left, so the hint shows
    scroll = {"px": 0}

    def fake_grab(rect):
        """Screen reads see the demo screen, not the real one."""
        image = QImage(rect.size(), QImage.Format.Format_RGB32)
        image.fill(QColor("#2B3A4A"))
        p = QPainter(image)
        p.drawImage(crop.topLeft() - rect.topLeft(), draw_terminal(scroll["px"]))
        p.end()
        return image

    real_grab, real_below = stack.grab, stack.window_below
    stack.grab = fake_grab
    stack.window_below = lambda *args: None  # leave real windows alone
    frames = []
    first = draw_terminal(0).copy(FRAME)
    preview = Preview(first, can_save=True, save_folder=SAVE_FOLDER)
    preview.timer.stop()
    state = {"stack": None, "mouse": QPoint(700, 140), "key": None}

    def compose(ms=70):
        app.processEvents()
        image = draw_terminal(scroll["px"])
        p = QPainter(image)
        s = state["stack"]
        if s and s.overlays:
            overlay = next(o for o in s.overlays if o.area == area)
            p.drawImage(0, 0, overlay.grab().toImage().copy(QRect(0, 0, W, H)))
        thumb = preview.grab().toImage()
        thumb.setDevicePixelRatio(1)
        thumb = thumb.scaled(preview.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        state["thumb_at"] = QPoint(W - thumb.width() - 16, H - thumb.height() - 16)
        p.drawImage(state["thumb_at"], thumb)
        p.end()
        if state["key"]:
            keycap(image, state["key"], 150)
        pointer(image, state["mouse"])
        frames.append((to_pil(image), ms))

    def glide(end, steps):
        start = state["mouse"]
        for i in range(1, steps + 1):
            t = i / steps
            t = t * t * (3 - 2 * t)  # ease in/out
            state["mouse"] = start + (end - start) * t
            if state["stack"]:
                state["stack"].move(crop.topLeft() + state["mouse"])
            compose()

    def button(name):
        return state["thumb_at"] + preview.buttons[name].center() + QPoint(2, 3)

    def wheel(notches):
        state["key"] = "wheel ↓"
        for _ in range(notches):
            scroll["px"] += 3 * LINE_HEIGHT  # 3 lines per notch
            s = state["stack"]
            s.read()
            s.show_read()
            compose(110)
        state["key"] = None
        compose(300)

    def click_frame_bottom():
        state["stack"].click(crop.topLeft() + state["mouse"])
        compose(900)

    compose(900)  # piece 1 taken: "copied to clipboard"
    glide(button("add"), 14)
    preview.set_hover("add")  # "add below · start a stack"
    compose(1300)
    preview.set_hover(None)
    preview.start_stack()
    s = stack.Stack(FRAME.translated(crop.topLeft()), first, [preview])
    s.changed.connect(lambda: preview.set_stack(s.image(), s.count()))
    state["stack"] = s
    s.read()
    s.show_read()
    glide(QPoint(330, 300), 12)
    compose(900)
    wheel(3)
    glide(QPoint(330, FRAME.bottom() - 4), 10)
    compose(700)
    click_frame_bottom()  # piece 2
    wheel(9)  # past the frame: the end line is now above the screen
    glide(QPoint(330, FRAME.bottom() - 4), 6)
    compose(1400)  # "↑ + ... px above, recorded while scrolling"
    click_frame_bottom()  # piece 3
    glide(QPoint(450, 300), 6)
    glide(button("finish"), 12)
    preview.set_hover("finish")  # "finish · stop adding"
    compose(1100)
    s.finish()
    state["stack"] = None
    preview.set_hover(None)
    result = s.image()
    preview.finish_stack(result, s.count(), None)  # "copied · 3 pieces · ..."
    compose(2000)

    # The result: one tall image.
    image = QImage(W, H, QImage.Format.Format_RGB32)
    image.fill(QColor("#2B3A4A"))
    tall = result.scaledToHeight(H - 80, Qt.TransformationMode.SmoothTransformation)
    p = QPainter(image)
    p.drawImage((W - tall.width()) // 2, 24, tall)
    p.setPen(QColor("#FFB000"))
    p.drawRect(QRect((W - tall.width()) // 2 - 1, 23, tall.width() + 1, tall.height() + 1))
    p.setFont(QFont("JetBrains Mono", 13))
    p.drawText(QRect(0, H - 48, W, 30), Qt.AlignmentFlag.AlignCenter,
               f"3 pieces → one image, {result.width()}×{result.height()}")
    p.end()
    frames.append((to_pil(image), 2600))
    preview.close()
    stack.grab, stack.window_below = real_grab, real_below
    save_gif(frames, STACK_OUT)


def main():
    app = QApplication(sys.argv)
    load_fonts()
    make_capture_gif(app)
    make_stack_gif(app)


if __name__ == "__main__":
    main()
