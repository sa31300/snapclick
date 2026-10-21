"""Tests for the Draw window and button (spec §2c). Run: .venv\\Scripts\\python -m unittest discover tests"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no windows on screen

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from snapclick.draw import COLORS, DrawWindow, draw_title
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


class DrawingTest(unittest.TestCase):
    """Drag with the mouse on the picture, then ✓ (spec §2c, build step 2)."""

    def setUp(self):
        self.window = DrawWindow(picture(), "shot · 300×200", QPoint(0, 0))
        self.window.canvas.ratio = 1  # 1 widget point = 1 picture pixel, whatever the test screen says
        self.results = []
        self.window.done.connect(self.results.append)

    def drag(self, start, end):
        canvas = self.window.canvas
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(canvas, end)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)

    def pick(self, group, name):
        next(b for b in group.buttons() if b.property("name") == name).setChecked(True)

    def test_box_in_red_by_default(self):
        self.drag(QPoint(50, 40), QPoint(150, 120))
        self.window.finish()
        image = self.results[0]
        self.assertEqual(image.size(), picture().size())  # nothing cut or scaled
        self.assertEqual(image.pixelColor(50, 80), QColor(COLORS["red"]))  # left edge
        self.assertEqual(image.pixelColor(100, 80), QColor("#336699"))  # inside stays clear

    def test_blue_arrow(self):
        self.pick(self.window.tools, "arrow")
        self.pick(self.window.colors, "blue")
        self.drag(QPoint(40, 100), QPoint(240, 100))
        self.window.finish()
        self.assertEqual(self.results[0].pixelColor(120, 100), QColor(COLORS["blue"]))  # the shaft
        self.assertEqual(self.results[0].pixelColor(235, 100), QColor(COLORS["blue"]))  # the head

    def test_click_without_drag_draws_nothing(self):
        self.drag(QPoint(50, 40), QPoint(51, 41))
        self.assertEqual(self.window.shapes, [])

    def test_undo(self):
        self.drag(QPoint(50, 40), QPoint(150, 120))
        self.drag(QPoint(20, 20), QPoint(80, 60))
        self.window.undo()
        self.assertEqual(len(self.window.shapes), 1)
        self.window.undo()
        self.window.undo()  # nothing left: no error
        self.window.finish()
        self.assertEqual(self.results[0].pixelColor(50, 80), QColor("#336699"))

    def click(self, point):
        canvas = self.window.canvas
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    def test_mark_is_yellow_whatever_the_color(self):
        self.pick(self.window.tools, "mark")
        self.pick(self.window.colors, "blue")
        self.drag(QPoint(20, 20), QPoint(120, 60))
        self.window.finish()
        inside, outside = self.results[0].pixelColor(70, 40), self.results[0].pixelColor(200, 150)
        self.assertEqual(outside, QColor("#336699"))
        self.assertGreater(inside.red(), 120)  # #336699 under see-through yellow (red was 51)
        self.assertGreater(inside.green(), inside.blue())

    def test_steps_count_up_and_undo_takes_the_number_back(self):
        self.pick(self.window.tools, "step")
        for x in (40, 100, 160):
            self.click(QPoint(x, 100))
        self.window.undo()  # removes step 3
        self.click(QPoint(220, 100))  # this one is 3 again
        steps = [shape for shape in self.window.shapes if shape[0] == "step"]
        self.assertEqual([shape[2].x() for shape in steps], [40, 100, 220])
        self.window.finish()
        self.assertEqual(self.results[0].pixelColor(220 - 11, 100), QColor(COLORS["red"]))  # the circle
        self.assertEqual(self.results[0].pixelColor(160 - 11, 100), QColor("#336699"))  # undone

    def test_preview_label_after_done(self):
        preview = Preview(picture(), can_save=True, save_folder="demo")
        preview.show_drawn(picture())
        self.assertEqual(preview.label()[0], "copied · with drawings")
        preview.close()


if __name__ == "__main__":
    unittest.main()
