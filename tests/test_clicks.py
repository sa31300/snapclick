"""Click circles: quick presses, held buttons, positions and pulse lifetime."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from snapclick.clicks import ClickMarks

app = QApplication.instance() or QApplication([])


def picture():
    image = QImage(100, 80, QImage.Format.Format_RGB32)
    image.fill(QColor("#22313D"))
    return image


class ClickMarksTest(unittest.TestCase):
    def setUp(self):
        state = patch("snapclick.clicks.user32.GetAsyncKeyState", return_value=0)
        self.state = state.start()
        self.addCleanup(state.stop)
        position = patch("snapclick.clicks.user32.GetCursorPos", side_effect=self.position)
        self.position_mock = position.start()
        self.addCleanup(position.stop)
        self.point = QPoint(-160, 140)
        self.frame = QRect(-200, 100, 100, 80)

    def position(self, pointer):
        pointer._obj.x, pointer._obj.y = self.point.x(), self.point.y()
        return True

    def draw(self, marks, elapsed):
        image = picture()
        marks.draw(image, self.frame, elapsed)
        return image

    def test_quick_click_draws_at_tip_grows_then_disappears(self):
        self.state.side_effect = [0, 1, 0, 0]
        marks = ClickMarks()
        first = self.draw(marks, 1)
        grown = self.draw(marks, 1.2)
        expired = self.draw(marks, 1.41)
        self.assertNotEqual(first, picture())
        self.assertNotEqual(grown, first)
        self.assertEqual(expired, picture())
        self.assertEqual(first.pixelColor(40, 40), picture().pixelColor(40, 40))
        self.assertEqual(first.pixelColor(51, 40), QColor("#FFB000"))
        self.position_mock.assert_called_once()

    def test_start_click_is_discarded_and_hold_does_not_repeat(self):
        self.state.side_effect = [0x8001, 0x8000, 0, 0x8000, 0x8000]
        marks = ClickMarks()
        self.assertEqual(self.draw(marks, 0), picture())
        self.assertEqual(self.draw(marks, 0.2), picture())
        self.assertNotEqual(self.draw(marks, 1), picture())
        self.assertEqual(self.draw(marks, 1.5), picture())
        self.position_mock.assert_called_once()

    def test_click_outside_the_rectangle_does_not_leave_a_mark(self):
        marks = ClickMarks()
        self.point = QPoint(0, 0)
        self.state.return_value = 1
        self.assertEqual(self.draw(marks, 1), picture())
        self.assertEqual(marks.marks, [])

    def test_two_quick_clicks_keep_both_locations_until_expiry(self):
        self.state.side_effect = [0, 1, 1, 0]
        marks = ClickMarks()
        self.draw(marks, 1)
        self.point = QPoint(-130, 150)
        self.draw(marks, 1.2)
        self.assertEqual([p for _, p in marks.marks], [QPoint(-160, 140), QPoint(-130, 150)])
        self.draw(marks, 1.41)
        self.assertEqual([p for _, p in marks.marks], [QPoint(-130, 150)])

    def test_failed_position_read_does_not_draw_at_a_wrong_location(self):
        marks = ClickMarks()
        self.state.return_value = 1
        self.position_mock.side_effect = None
        self.position_mock.return_value = False
        self.assertEqual(self.draw(marks, 1), picture())


if __name__ == "__main__":
    unittest.main()
