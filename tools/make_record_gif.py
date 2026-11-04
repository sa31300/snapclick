"""Make docs/record.gif from fake content and the app's real selection, bar and preview widgets."""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

W, H = 960, 640
AREA = QRect(116, 150, 240, 184)
AMBER = QColor("#FFB000")
RED = QColor("#FF6B6B")


def scene(stage):
    """A made-up ledger and its File → Export flow; no screen reads."""
    image = QImage(W, H, QImage.Format.Format_RGB32)
    image.fill(QColor("#2B3A4A"))
    p = QPainter(image)
    p.fillRect(QRect(80, 88, 620, 380), QColor("#F6F6F4"))
    p.fillRect(QRect(80, 88, 620, 36), QColor("#E5E8EB"))
    p.setPen(QColor("#202124"))
    p.setFont(QFont("IBM Plex Sans", 12, QFont.Weight.Medium))
    p.drawText(96, 112, "Demo Ledger")
    p.setFont(QFont("IBM Plex Sans", 10))
    p.drawText(96, 141, "Demo invoices")
    p.fillRect(QRect(116, 150, 240, 26), QColor("#ECEFEE"))
    for x, text in ((128, "File"), (190, "View"), (260, "Help")):
        p.drawText(x, 168, text)
    p.setFont(QFont("IBM Plex Sans", 10, QFont.Weight.Medium))
    p.drawText(126, 197, "Invoice")
    p.drawText(270, 197, "Amount")
    p.setFont(QFont("IBM Plex Sans", 10))
    for i, (invoice, amount) in enumerate((("INV-1001", "125.00"), ("INV-1002", "84.50"), ("INV-1003", "230.00"))):
        y = 220 + i * 25
        p.setPen(QColor("#202124"))
        p.drawText(126, y, invoice)
        p.drawText(270, y, amount)
        p.setPen(QColor("#D8DAD8"))
        p.drawLine(126, y + 7, 342, y + 7)
    p.setPen(QColor("#467056") if stage == 5 else QColor("#777B78"))
    p.drawText(126, 316, "Demo export complete" if stage == 5 else "3 demo invoices")
    if stage in (1, 2):
        p.fillRect(QRect(120, 176, 220, 132), QColor("#FFFFFF"))
        p.setPen(QColor("#A3A39E"))
        p.drawRect(QRect(120, 176, 220, 132))
        for i, text in enumerate(("New demo", "Open demo", "Export…", "Cancel")):
            row = QRect(122, 179 + 30 * i, 216, 28)
            if i == 2 and stage == 2:
                p.fillRect(row, QColor("#DBE9FC"))
            p.setPen(QColor("#202124"))
            p.drawText(row.adjusted(10, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, text)
    if stage in (3, 4):
        p.fillRect(QRect(120, 178, 230, 145), QColor("#FFFFFF"))
        p.setPen(QColor("#A3A39E"))
        p.drawRect(QRect(120, 178, 230, 145))
        p.setPen(QColor("#202124"))
        p.drawText(132, 201, "Export demo")
        p.drawText(132, 229, "Format: PNG")
        p.drawText(132, 255, "demo-ledger.png")
        p.fillRect(QRect(259, 280, 78, 27), QColor("#2F80ED" if stage == 3 else "#2468C3"))
        p.setPen(QColor("white"))
        p.drawText(QRect(259, 280, 78, 27), Qt.AlignmentFlag.AlignCenter, "Export")
    p.end()
    return image


def widget_image(widget):
    image = widget.grab().toImage()
    image.setDevicePixelRatio(1)
    return image.scaled(widget.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


def make_gif(app, save_folder):
    from make_demo_gif import keycap, pointer, save_gif, scene_label, to_pil
    from snapclick.capture import Capture, DIM, Overlay
    from snapclick.frames import FrameBuffer, make_sheet
    from snapclick.preview import Preview
    from snapclick.record import RecordBar

    frames = []
    screen = app.primaryScreen()
    cap = SimpleNamespace(image=scene(0), origin=QPoint(), first=None, cursor=QPoint(680, 140))
    cap.selection = lambda: Capture.selection(cap)
    cap.move = lambda point: setattr(cap, "cursor", point)
    cap.close = lambda: None
    overlay = Overlay(cap, screen)
    overlay.area = QRect(0, 0, W, H)
    overlay.setGeometry(0, 0, W, H)
    overlay.dimmed = cap.image.copy()
    p = QPainter(overlay.dimmed)
    p.fillRect(overlay.dimmed.rect(), DIM)
    p.end()
    overlay.show()

    state = {"stage": 0, "mouse": QPoint(680, 140), "overlay": False, "bar": None,
             "recording": False, "preview": None, "label": "1 · press Insert"}
    bar_at = QPoint(AREA.x(), AREA.y() + AREA.height() + 6)

    def compose(ms=70, key=None):
        app.processEvents()
        image = widget_image(overlay) if state["overlay"] else scene(state["stage"])
        p = QPainter(image)
        if state["bar"]:
            pen = QPen(RED, 1)
            if not state["recording"]:
                pen.setStyle(Qt.PenStyle.CustomDashLine)
                pen.setDashPattern([4, 3])
            p.setPen(pen)
            p.drawRect(AREA.adjusted(-1, -1, 0, 0))
            p.drawImage(bar_at, widget_image(state["bar"]))
        if state["preview"]:
            thumb = widget_image(state["preview"])
            state["thumb_at"] = QPoint(W - thumb.width() - 16, H - thumb.height() - 16)
            p.drawImage(state["thumb_at"], thumb)
        p.setFont(QFont("JetBrains Mono", 9))
        p.setPen(QColor("#C9C9C4"))
        p.drawText(QRect(600, H - 30, 340, 20), Qt.AlignmentFlag.AlignRight, "demo · fake data")
        p.end()
        scene_label(image, state["label"])
        if key:
            keycap(image, key, 120)
        pointer(image, state["mouse"])
        frames.append((to_pil(image), ms))

    def glide(end, steps=7):
        start = state["mouse"]
        for i in range(1, steps + 1):
            t = i / steps
            t = t * t * (3 - 2 * t)
            state["mouse"] = start + (end - start) * t
            if state["overlay"]:
                cap.cursor = state["mouse"]
                overlay.update()
            compose()

    compose(600)
    compose(700, "Insert")
    state["overlay"], state["label"] = True, "2 · select the area"
    glide(AREA.topLeft(), 10)
    cap.first = AREA.topLeft()
    overlay.update()
    compose(350)
    glide(AREA.topLeft() + QPoint(AREA.width(), AREA.height()), 12)
    compose(650)
    state["overlay"] = False
    overlay.close()

    bar = RecordBar(AREA, lambda: None, lambda: None)
    state["bar"], state["label"] = bar, "3 · click Record"
    compose(600)
    glide(bar_at + bar.record.mapTo(bar, bar.record.rect().center()))
    bar.record.setDown(True)
    compose(180)
    bar.record.setDown(False)
    bar.show_recording(0, 30)
    state["recording"], state["label"] = True, "4 · work normally"

    buffer = FrameBuffer(AREA.size(), 12)
    moments = [(0, 0, QPoint(330, 310), False), (1, 1, QPoint(136, 162), True),
               (3, 2, QPoint(170, 251), False), (5, 3, QPoint(170, 251), True),
               (7, 4, QPoint(294, 292), True), (9, 5, QPoint(325, 310), False)]
    for elapsed, stage, mouse, clicked in moments:
        glide(mouse, 5)
        state["stage"] = stage
        bar.update_clock(elapsed, 30)
        # Only the output frames get click circles; no live-screen click overlay.
        piece = scene(stage).copy(AREA)
        local = mouse - AREA.topLeft()
        pointer(piece, local)
        if clicked:
            p = QPainter(piece)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(AMBER, 2))
            p.drawEllipse(QPointF(local), 12, 12)
            p.end()
        buffer.add(piece, elapsed, final=elapsed == 9)
        compose(700)

    state["label"] = "5 · stop the recording"
    glide(bar_at + bar.cancel.mapTo(bar, bar.cancel.rect().center()))
    bar.cancel.setDown(True)
    compose(250)
    bar.cancel.setDown(False)
    bar.close()
    state["bar"], state["recording"] = None, False
    selected = buffer.selected()
    sheet = make_sheet(selected)
    preview = Preview(sheet, can_save=True, save_folder=str(save_folder),
                      mode="recorded", count=len(selected), elapsed=9)
    preview.timer.stop()
    state["preview"], state["label"] = preview, "6 · paste the PNG sheet"
    compose(1400)
    compose(700, "Ctrl+V")
    preview.close()

    image = QImage(W, H, QImage.Format.Format_RGB32)
    image.fill(QColor("#0D0E10"))
    shown = sheet.scaled(QSize(W - 64, H - 180), Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    p = QPainter(image)
    p.setFont(QFont("JetBrains Mono", 13, QFont.Weight.DemiBold))
    p.setPen(AMBER)
    p.drawText(QRect(0, 24, W, 36), Qt.AlignmentFlag.AlignCenter, "One PNG · numbered frames and times")
    p.drawImage((W - shown.width()) // 2, 100, shown)
    p.setFont(QFont("JetBrains Mono", 11))
    p.setPen(QColor("#C9C9C4"))
    p.drawText(QRect(0, H - 84, W, 28), Qt.AlignmentFlag.AlignCenter,
               "Ctrl+V into an AI chat · click circles show where you clicked")
    p.drawText(QRect(0, H - 45, W, 24), Qt.AlignmentFlag.AlignCenter, "demo · fake data")
    p.end()
    frames.append((to_pil(image), 3600))
    save_gif(frames, ROOT / "docs" / "record.gif")


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_SCALE_FACTOR"] = "1"
    with tempfile.TemporaryDirectory(prefix="snapclick-record-demo-") as folder:
        path = Path(folder)
        os.environ["SNAPCLICK_SETTINGS"] = str(path / "settings.json")
        (path / "settings.json").write_text(json.dumps({"save_folder": str(path / "captures"),
                                                       "start_with_windows": False}), encoding="utf-8")
        from snapclick.__main__ import load_fonts
        app = QApplication(sys.argv)
        load_fonts()
        make_gif(app, path / "captures")


if __name__ == "__main__":
    main()
