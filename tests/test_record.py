"""Record step 1: selection, cancellation and independent hotkeys."""
import ctypes
import os
import unittest
from ctypes import wintypes
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from snapclick.hotkey import DEFAULT_HOTKEY, GlobalHotkey, RECORD_HOTKEY, RECORD_HOTKEY_ID, WM_HOTKEY
from snapclick.record import LiveSelection, Record, RecordBar

app = QApplication.instance() or QApplication([])


def demo_image():
    image = QImage(800, 600, QImage.Format.Format_RGB32)
    image.fill(QColor("#22313D"))
    return image


class RecordSelectionTest(unittest.TestCase):
    def setUp(self):
        for name, value in (("snapclick.capture.grab_desktop", (demo_image(), QPoint())),
                            ("snapclick.record.grab", demo_image()),
                            ("snapclick.record.exclude_from_capture", True)):
            mock = patch(name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        # A recording selection must never use the screenshot clipboard path.
        mock = patch("snapclick.capture.save_clipboard", side_effect=AssertionError("clipboard touched"))
        mock.start()
        self.addCleanup(mock.stop)

    def test_corners_in_every_direction(self):
        for a, b in ((QPoint(10, 20), QPoint(110, 80)), (QPoint(110, 80), QPoint(10, 20)),
                     (QPoint(110, 20), QPoint(10, 80)), (QPoint(10, 80), QPoint(110, 20))):
            with self.subTest(a=a, b=b):
                selector = LiveSelection()
                selected, finished = [], []
                selector.selected.connect(selected.append)
                selector.finished.connect(lambda: finished.append(True))
                selector.click(a)
                selector.click(b)
                self.assertEqual(selected, [QRect(10, 20, 100, 60)])
                self.assertEqual(finished, [True])
                self.assertFalse(selector.timer.isActive())
                self.assertEqual(selector.overlays, [])

    def test_empty_selection_cancels(self):
        for end in (QPoint(10, 80), QPoint(110, 20)):
            selector = LiveSelection()
            selected = []
            selector.selected.connect(selected.append)
            selector.click(QPoint(10, 20))
            selector.click(end)
            self.assertEqual(selected, [])
            self.assertFalse(selector.timer.isActive())

    @patch("snapclick.record.GlobalHotkey")
    def test_ready_cancel_and_escape_close_once(self, hotkey):
        for use_escape in (False, True):
            session = Record()
            finished = []
            session.finished.connect(lambda: finished.append(True))
            session.selection.click(QPoint(10, 20))
            session.selection.click(QPoint(210, 150))
            self.assertIsNone(session.selection)
            self.assertTrue(session.bar.isVisible())
            self.assertFalse(session.bar.record.isEnabled())
            self.assertTrue(all(b.isVisible() for b in session.borders))
            if use_escape:
                hotkey.call_args.args[1]()  # Esc also works when another app has focus
            else:
                session.bar.cancel.click()
            session.close()
            self.assertEqual(finished, [True])
            self.assertFalse(session.bar.isVisible())
            self.assertTrue(all(not b.isVisible() for b in session.borders))
            hotkey.return_value.close.assert_called()

    def test_cancel_before_second_corner(self):
        session = Record()
        finished = []
        session.finished.connect(lambda: finished.append(True))
        session.selection.click(QPoint(10, 20))
        session.selection.close()
        self.assertEqual(finished, [True])
        self.assertIsNone(session.bar)
        self.assertEqual(session.borders, [])

    def test_bar_stays_on_screen_near_bottom(self):
        screen = app.primaryScreen()
        bounds = screen.availableGeometry()
        ratio = screen.devicePixelRatio()
        frame = QRect(bounds.x() + 20, bounds.y() + round((bounds.height() - 60) * ratio), 160, 50)
        bar = RecordBar(frame, lambda: None)
        self.assertTrue(bounds.contains(bar.geometry()))
        self.assertLess(bar.y() + bar.height(), frame.y())
        bar.close()


class RecordHotkeyTest(unittest.TestCase):
    @patch("snapclick.hotkey.user32.UnregisterHotKey")
    @patch("snapclick.hotkey.user32.RegisterHotKey", return_value=True)
    def test_insert_does_not_replace_prtsc(self, register, unregister):
        shots, recordings = [], []
        shot = GlobalHotkey(app, lambda: shots.append(True), DEFAULT_HOTKEY)
        record = GlobalHotkey(app, lambda: recordings.append(True), RECORD_HOTKEY, RECORD_HOTKEY_ID)
        try:
            self.assertNotEqual(shot.hotkey_id, record.hotkey_id)
            for hotkey in (shot, record):
                msg = wintypes.MSG()
                msg.message, msg.wParam = WM_HOTKEY, hotkey.hotkey_id
                for listener in (shot, record):
                    listener.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))
            self.assertEqual(shots, [True])
            self.assertEqual(recordings, [True])
        finally:
            record.close()
            shot.close()
        self.assertEqual({c.args[1] for c in unregister.call_args_list}, {shot.hotkey_id, record.hotkey_id})


if __name__ == "__main__":
    unittest.main()
