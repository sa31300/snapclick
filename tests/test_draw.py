"""Tests for the Draw window and button (spec §2c). Run: .venv\\Scripts\\python -m unittest discover tests"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no windows on screen

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtWidgets import QApplication

from snapclick.draw import DrawWindow, draw_title
from snapclick.preview import Preview

app = QApplication.instance() or QApplication([])


def picture(width=300, height=200):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#336699"))
    return image


def press(widget, key):
    widget.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


class DrawTitleTest(unittest.TestCase):
    def test_single_shot(self):
        self.assertEqual(draw_title("single", 1, picture(810, 282)), "shot · 810×282")

    def test_stack(self):
        self.assertEqual(draw_title("stacked", 3, picture(810, 1050)), "stack · 3 pieces · 810×1050")


class DrawButtonTest(unittest.TestCase):
    def buttons(self, can_save, mode=None):
        preview = Preview(picture(), can_save=can_save, save_folder="demo")
        if mode == "stacking":
            preview.start_stack()
        elif mode == "stacked":
            preview.start_stack()
            preview.finish_stack(picture(), 3, None)
        names = sorted(preview.buttons, key=lambda name: preview.buttons[name].x())  # left to right
        preview.close()
        return names

    def test_order_single_shot(self):
        self.assertEqual(self.buttons(can_save=True), ["add", "draw", "save", "retake"])
        self.assertEqual(self.buttons(can_save=False), ["add", "draw", "retake"])  # auto-save on

    def test_hidden_while_stacking(self):
        self.assertEqual(self.buttons(can_save=True, mode="stacking"), ["finish", "retake"])

    def test_after_a_stack(self):  # Add below stays hidden (§2b)
        self.assertEqual(self.buttons(can_save=True, mode="stacked"), ["draw", "save", "retake"])

    def test_hover_label(self):
        preview = Preview(picture(), can_save=True, save_folder="demo")
        preview.set_hover("draw")
        self.assertEqual(preview.label()[0], "draw · mark up")
        preview.close()


class DrawWindowTest(unittest.TestCase):
    def open(self):
        window = DrawWindow(picture(), "shot · 300×200", QPoint(0, 0))
        results = {"done": [], "closed": 0}
        window.done.connect(results["done"].append)
        window.closed.connect(lambda: results.__setitem__("closed", results["closed"] + 1))
        return window, results

    def test_enter_gives_the_picture(self):
        window, results = self.open()
        press(window, Qt.Key.Key_Return)
        self.assertEqual(len(results["done"]), 1)
        self.assertEqual(results["done"][0].size(), picture().size())
        self.assertEqual(results["closed"], 1)

    def test_esc_changes_nothing(self):
        window, results = self.open()
        press(window, Qt.Key.Key_Escape)
        self.assertEqual(results["done"], [])
        self.assertEqual(results["closed"], 1)


if __name__ == "__main__":
    unittest.main()
