"""Make docs/repeat.gif from fake notes and the real selection, border and preview widgets."""
import json
import os
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

W, H = 960, 640
AREA = QRect(96, 208, 430, 168)  # seven full rows per capture


def scene(scroll=0):
    """Draw made-up notes, including fractional scroll positions for the animation."""
    image = QImage(W, H, QImage.Format.Format_RGB32)
    image.fill(QColor("#2B3A4A"))
    painter = QPainter(image)
    painter.fillRect(QRect(70, 88, 570, 430), QColor("#10151B"))
    painter.fillRect(QRect(70, 88, 570, 34), QColor("#202832"))
    font = QFont("IBM Plex Sans")
    font.setPixelSize(15)
    painter.setFont(font)
    painter.setPen(QColor("#E7E7E4"))
    painter.drawText(88, 111, "Demo Notes")
    font = QFont("JetBrains Mono")
    font.setPixelSize(14)
    painter.setFont(font)
    painter.setPen(QColor("#A3A39E"))
    painter.drawText(96, 148, "Sample checklist · fake content")
    painter.setClipRect(QRect(90, 160, 530, 340))
    painter.setPen(QColor("#E7E7E4"))
    for number in range(1, 41):
        y = round(AREA.y() + (number - 1 - scroll) * 24)
        if 136 <= y <= 500:
            painter.drawText(108, y + 17, f"{number:02d}  Sample note {number:02d} · ready")
    painter.end()
    return image


def make_gif(app, save_folder):
    from make_demo_gif import keycap, pointer, save_gif, scene_label, to_pil
    from make_record_gif import widget_image
    from snapclick.capture import Capture, DIM, Overlay
    from snapclick.preview import Preview
    from snapclick.repeat_area import RepeatArea

    frames = []
    cap = SimpleNamespace(image=scene(), origin=QPoint(), first=None, cursor=QPoint(680, 150))
    cap.selection = lambda: Capture.selection(cap)
    cap.move = lambda point: setattr(cap, "cursor", point)
    cap.close = lambda: None
    overlay = Overlay(cap, app.primaryScreen())
    overlay.area = QRect(0, 0, W, H)
    overlay.setGeometry(0, 0, W, H)
    overlay.dimmed = cap.image.copy()
    painter = QPainter(overlay.dimmed)
    painter.fillRect(overlay.dimmed.rect(), DIM)
    painter.end()
    overlay.show()

    state = {"scroll": 0, "mouse": QPoint(680, 150), "overlay": False,
             "preview": None, "session": None, "label": "1 · PrtSc, then two corners"}

    def compose(ms=60, key=None):
        if state["preview"]:
            state["preview"].timer.stop()
        app.processEvents()
        image = widget_image(overlay) if state["overlay"] else scene(state["scroll"])
        painter = QPainter(image)
        if state["session"] and not state["session"].closed:
            painter.drawImage(0, 0, widget_image(state["session"].borders[0]))
        if state["preview"]:
            thumb = widget_image(state["preview"])
            state["thumb_at"] = QPoint(W - thumb.width() - 16, H - thumb.height() - 16)
            painter.drawImage(state["thumb_at"], thumb)
        font = QFont("JetBrains Mono")
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor("#C9C9C4"))
        painter.drawText(76, 544, "demo · fake data")
        painter.end()
        scene_label(image, state["label"])
        if key:
            keycap(image, key, 130 if key == "Ctrl+V" else 96)
        pointer(image, state["mouse"])
        frames.append((to_pil(image), ms))

    def glide(end, steps=8):
        start = state["mouse"]
        for step in range(1, steps + 1):
            t = step / steps
            t = t * t * (3 - 2 * t)
            state["mouse"] = start + (end - start) * t
            if state["overlay"]:
                cap.cursor = state["mouse"]
                overlay.update()
            compose()

    compose(600)
    compose(650, "PrtSc")
    state["overlay"] = True
    glide(AREA.topLeft())
    cap.first = AREA.topLeft()
    overlay.update()
    compose(300)
    glide(AREA.topLeft() + QPoint(AREA.width(), AREA.height()), 10)
    compose(500)
    state["overlay"] = False
    overlay.close()

    preview = Preview(scene().copy(AREA), can_save=True, save_folder=str(save_folder))
    state["preview"], state["label"] = preview, "2 · click Repeat area"
    compose(500)
    glide(state["thumb_at"] + preview.buttons["repeat"].center())
    preview.set_hover("repeat")
    compose(650)
    session = RepeatArea(AREA, preview.image, [preview])
    for border in session.borders:
        border.area = QRect(0, 0, W, H)
        border.setGeometry(0, 0, W, H)
    session.changed.connect(lambda: preview.set_repeat_area(session.image(), session.count()))
    session.finished.connect(lambda: preview.finish_repeat_area(session.image(), session.count(), None))
    preview.start_repeat_area()
    state["session"], state["label"] = session, "3 · scroll down; the box stays fixed"
    compose(1000)
    glide(QPoint(500, 295))

    for target, label in ((5, "4 · PrtSc adds image 2"), (3, "5 · scroll up; PrtSc adds image 3")):
        state["label"] = label
        start = state["scroll"]
        for step in range(1, 11):
            state["scroll"] = start + (target - start) * step / 10
            compose(70)
        compose(850)
        compose(500, "PrtSc")
        with patch("snapclick.repeat_area.grab", return_value=scene(state["scroll"]).copy(AREA)):
            session.add()
        compose(1000)

    state["label"] = "6 · Esc finishes; Draw and Save are ready"
    compose(550, "Esc")
    session.finish()
    compose(1100)
    state["label"] = "7 · paste the joined image"
    compose(650, "Ctrl+V")
    preview.close()

    image = QImage(W, H, QImage.Format.Format_RGB32)
    image.fill(QColor("#0D0E10"))
    painter = QPainter(image)
    font = QFont("JetBrains Mono")
    font.setPixelSize(17)
    painter.setFont(font)
    painter.setPen(QColor("#FFB000"))
    painter.drawText(QRect(0, 20, W, 35), Qt.AlignmentFlag.AlignCenter,
                     "3 full captures · in capture order")
    joined = session.image()
    painter.drawImage((W - joined.width()) // 2, 78, joined)
    font.setPixelSize(13)
    painter.setFont(font)
    painter.setPen(QColor("#C9C9C4"))
    for index, lines in enumerate(("01–07", "06–12", "04–10")):
        painter.drawText(30, 105 + index * AREA.height(), f"Image {index + 1} · lines {lines}")
    painter.drawText(725, 235, "Repeated lines stay")
    painter.drawText(725, 403, "Scroll up still")
    painter.drawText(725, 425, "appends below")
    painter.drawText(QRect(0, 600, W, 24), Qt.AlignmentFlag.AlignCenter, "demo · fake data")
    painter.end()
    frames.append((to_pil(image), 3600))
    save_gif(frames, ROOT / "docs" / "repeat.gif")


def main():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_SCALE_FACTOR"] = "1"
    with tempfile.TemporaryDirectory(prefix="snapclick-repeat-demo-") as folder, ExitStack() as mocks:
        path = Path(folder)
        os.environ["SNAPCLICK_SETTINGS"] = str(path / "settings.json")
        (path / "settings.json").write_text(json.dumps({"save_folder": str(path / "captures"),
                                                       "start_with_windows": False}), encoding="utf-8")
        from snapclick.__main__ import load_fonts
        # Every screen read uses fake notes. No hotkeys or clipboard changes are needed.
        for name in ("snapclick.capture.grab_desktop", "snapclick.capture.grab", "snapclick.record.grab",
                     "snapclick.repeat_area.grab"):
            mocks.enter_context(patch(name, side_effect=AssertionError("unexpected screen read")))
        for name in ("snapclick.repeat_area.exclude_from_capture", "snapclick.record.exclude_from_capture",
                     "snapclick.preview.exclude_from_capture"):
            mocks.enter_context(patch(name, return_value=True))
        mocks.enter_context(patch("snapclick.repeat_area.GlobalHotkey"))
        app = QApplication(sys.argv)
        load_fonts()
        make_gif(app, path / "captures")


if __name__ == "__main__":
    main()
