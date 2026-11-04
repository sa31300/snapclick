"""Repeat area step 1: preview entry, a passive fixed border and clean finishing."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from snapclick import settings
from snapclick.capture import ACCENT
from snapclick.hotkey import REPEAT_ESCAPE_ID
from snapclick.tray import Tray

app = QApplication.instance() or QApplication([])


class RepeatAreaTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.prefs = dict(settings.DEFAULTS, save_folder=str(Path(self.folder.name) / "captures"),
                          show_preview=True)
        for name, options in (
            ("snapclick.settings.SETTINGS_FILE", {"new": Path(self.folder.name) / "settings.json"}),
            ("snapclick.repeat_area.GlobalHotkey", {}),
            ("snapclick.record.exclude_from_capture", {"return_value": True}),
            ("snapclick.capture.grab_desktop", {"side_effect": AssertionError("unexpected screen read")}),
            ("snapclick.capture.grab", {"side_effect": AssertionError("unexpected screen read")}),
            ("snapclick.record.grab", {"side_effect": AssertionError("unexpected screen read")}),
            ("snapclick.tray.QGuiApplication.clipboard", {}),
        ):
            mock = patch(name, **options)
            result = mock.start()
            self.addCleanup(mock.stop)
            if name.endswith("GlobalHotkey"):
                self.hotkey = result
            elif name.endswith("clipboard"):
                self.clipboard = result.return_value

        self.frame = QRect(40, 60, 160, 100)
        self.desktop = QImage(800, 600, QImage.Format.Format_RGB32)
        self.desktop.fill(QColor("#22313D"))
        self.first = self.desktop.copy(self.frame)
        self.previous = QMimeData()
        self.previous.setText("demo clipboard")
        self.tray = Tray(app)  # never show a real tray icon
        self.tray.theme_timer.stop()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.tray.close_preview()
        self.tray.hide()

    def capture(self, auto_save=False):
        settings.save(dict(self.prefs, auto_save=auto_save))
        self.tray.capture = SimpleNamespace(image=self.desktop, origin=QPoint(), previous_clipboard=self.previous,
                                            clipboard_version=100, selection=lambda: self.frame)
        self.tray._captured(self.first)
        self.tray._capture_done()

    def start(self):
        preview = self.tray.preview
        QTest.mouseClick(preview, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         preview.buttons["repeat"].center())
        return self.tray.repeat_area

    def test_button_order_and_hover(self):
        self.capture()
        self.assertEqual(self.tray.preview.button_names(), ["add", "repeat", "draw", "save", "retake"])
        self.tray.preview.set_hover("repeat")
        self.assertEqual(self.tray.preview.label()[0], "repeat area · keep this box")

    def test_fixed_border_is_amber_transparent_and_accepts_no_input(self):
        self.capture()
        session = self.start()
        self.assertEqual(session.frame, self.frame)
        self.assertEqual(session.findChildren(QTimer), [])  # no screen-reading timer
        for border in session.borders:
            self.assertEqual(border.frame, self.frame)
            self.assertEqual(border.color, ACCENT)
            self.assertFalse(border.recording)  # dashed
            self.assertTrue(border.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            self.assertTrue(border.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
            image = border.grab().toImage()
            self.assertEqual(image.pixelColor(120, 110).alpha(), 0)
            self.assertEqual(image.pixelColor(10, 10).alpha(), 0)
            self.assertIn(ACCENT, [image.pixelColor(x, 59) for x in range(39, 201)])
        self.assertEqual(self.tray.preview.button_names(), ["finish"])
        self.assertFalse(self.tray.preview.timer.isActive())
        self.tray.preview.leaveEvent(None)
        self.assertFalse(self.tray.preview.timer.isActive())
        self.clipboard.setImage.assert_not_called()

    def test_global_escape_finishes_once_and_restores_first_preview(self):
        self.capture()
        undo = self.tray.undo
        session = self.start()
        self.assertEqual(self.hotkey.call_args.args[2], {"vk": 0x1B, "mods": 0, "name": "Esc"})
        self.assertEqual(self.hotkey.call_args.args[3], REPEAT_ESCAPE_ID)
        self.hotkey.call_args.args[1]()  # global Esc, even when another app has focus
        app.processEvents()
        session.finish()
        self.hotkey.return_value.close.assert_called_once()
        self.assertTrue(session.closed)
        self.assertTrue(all(not b.isVisible() for b in session.borders))
        self.assertIsNone(self.tray.repeat_area)
        self.assertIs(self.tray.undo, undo)
        self.assertEqual(self.tray.preview.mode, "single")
        self.assertEqual(self.tray.preview.image, self.first)
        self.clipboard.setImage.assert_not_called()

    def test_finish_button_closes_border(self):
        self.capture()
        session = self.start()
        preview = self.tray.preview
        QTest.mouseClick(preview, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         preview.buttons["finish"].center())
        self.assertTrue(session.closed)
        self.assertIsNone(self.tray.repeat_area)
        self.assertEqual(preview.mode, "single")

    def test_closing_preview_releases_border_and_escape(self):
        self.capture()
        session = self.start()
        self.tray.close_preview()
        self.assertTrue(session.closed)
        self.hotkey.return_value.close.assert_called_once()
        self.assertIsNone(self.tray.repeat_area)
        self.assertIsNone(self.tray.undo)

    def test_prtsc_and_insert_do_not_start_another_mode_in_step_one(self):
        self.capture()
        session = self.start()
        self.tray.start_capture()
        self.tray.start_record()
        self.assertIs(self.tray.repeat_area, session)
        self.assertIsNone(self.tray.capture)
        self.assertIsNone(self.tray.recording)
        self.assertEqual(self.tray.preview.image, self.first)
        self.clipboard.setImage.assert_not_called()

    def test_auto_saved_first_file_is_unchanged_in_step_one(self):
        self.capture(auto_save=True)
        path = self.tray.undo["saved_path"]
        before = path.read_bytes()
        self.start().finish()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(path.parent.iterdir()), [path])
        self.assertEqual(self.tray.preview.saved_path, path)

    def test_existing_draw_and_save_preview_state_survives(self):
        self.capture(auto_save=True)
        preview = self.tray.preview
        preview.show_saved(self.tray.undo["saved_path"])
        annotated = self.first.copy()
        annotated.setPixelColor(10, 10, QColor("red"))
        preview.show_drawn(annotated)
        label = preview.label()
        self.start().finish()
        self.assertEqual(preview.image, annotated)
        self.assertEqual(preview.label(), label)
        self.assertEqual(preview.save_state, "saved")


if __name__ == "__main__":
    unittest.main()
