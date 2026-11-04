"""Repeat area: passive fixed border, full-image appends and clean finishing."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from snapclick import settings
from snapclick.capture import ACCENT
from snapclick.draw import COLORS, draw_title
from snapclick.hotkey import REPEAT_ESCAPE_ID
from snapclick.repeat_area import reference_strips
from snapclick.tray import Tray

app = QApplication.instance() or QApplication([])


class RepeatAreaTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.prefs = dict(settings.DEFAULTS, save_folder=str(Path(self.folder.name) / "captures"),
                          show_preview=True)
        self.version = 100
        for name, options in (
            ("snapclick.settings.SETTINGS_FILE", {"new": Path(self.folder.name) / "settings.json"}),
            ("snapclick.repeat_area.GlobalHotkey", {}),
            ("snapclick.repeat_area.exclude_from_capture", {"return_value": True}),
            ("snapclick.repeat_area.grab", {"side_effect": AssertionError("unexpected screen read")}),
            ("snapclick.repeat_area.ctypes.windll.dwmapi.DwmFlush", {}),
            ("snapclick.preview.exclude_from_capture", {"return_value": True}),
            ("snapclick.record.exclude_from_capture", {"return_value": True}),
            ("snapclick.capture.grab_desktop", {"side_effect": AssertionError("unexpected screen read")}),
            ("snapclick.capture.grab", {"side_effect": AssertionError("unexpected screen read")}),
            ("snapclick.record.grab", {"side_effect": AssertionError("unexpected screen read")}),
            ("snapclick.tray.QGuiApplication.clipboard", {}),
            ("snapclick.tray.clipboard_version", {"side_effect": lambda: self.version}),
            ("snapclick.tray.restore_clipboard", {}),
        ):
            mock = patch(name, **options)
            result = mock.start()
            self.addCleanup(mock.stop)
            if name.endswith("GlobalHotkey"):
                self.hotkey = result
            elif name == "snapclick.repeat_area.grab":
                self.read = result
            elif name == "snapclick.repeat_area.exclude_from_capture":
                self.exclude = result
            elif name.endswith("DwmFlush"):
                self.flush = result
            elif name.endswith("QGuiApplication.clipboard"):
                self.clipboard = result.return_value
                self.clipboard.setImage.side_effect = self.copied_image
            elif name.endswith("restore_clipboard"):
                self.restored = result

        self.frame = QRect(40, 60, 160, 100)
        self.desktop = QImage(800, 600, QImage.Format.Format_RGB32)
        self.desktop.fill(QColor("#22313D"))
        self.first = self.desktop.copy(self.frame)
        self.previous = QMimeData()
        self.previous.setText("demo clipboard")
        self.tray = Tray(app)  # never show a real tray icon
        self.tray.showMessage = Mock()
        self.tray.theme_timer.stop()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.tray.close_preview()
        self.tray.hide()

    def copied_image(self, image):
        self.version += 1

    def capture(self, auto_save=False):
        settings.save(dict(self.prefs, auto_save=auto_save))
        self.tray.capture = SimpleNamespace(image=self.desktop, origin=QPoint(), previous_clipboard=self.previous,
                                            clipboard_version=self.version, selection=lambda: self.frame)
        self.tray._captured(self.first)
        self.tray._capture_done()

    def start(self):
        preview = self.tray.preview
        QTest.mouseClick(preview, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         preview.buttons["repeat"].center())
        return self.tray.repeat_area

    def click(self, name):
        preview = self.tray.preview
        QTest.mouseClick(preview, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         preview.buttons[name].center())

    def add(self, image=None):
        self.read.side_effect = None
        self.read.return_value = image if image is not None else self.first.copy()
        self.tray.start_capture()

    def draw_box(self):
        self.click("draw")
        window = self.tray.draw_window
        window.canvas.ratio = 1
        canvas = window.canvas
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(20, 120))
        QTest.mouseMove(canvas, QPoint(120, 170))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(120, 170))
        return window

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
        self.assertEqual(self.tray.preview.button_names(), ["finish", "retake"])
        self.assertFalse(self.tray.preview.timer.isActive())
        self.tray.preview.leaveEvent(None)
        self.assertFalse(self.tray.preview.timer.isActive())
        self.clipboard.setImage.assert_not_called()

    def test_reference_strips_show_last_bottom_above_and_last_top_below_at_original_size(self):
        top, bottom = QColor("#6A283D"), QColor("#305C6F")
        painter = QPainter(self.first)
        painter.fillRect(0, 0, 160, 40, top)
        painter.fillRect(0, 60, 160, 40, bottom)
        painter.end()
        self.capture()
        session = self.start()
        self.assertEqual(len(session.windows), len(app.screens()) + 1)  # reuse border windows + preview
        for border in session.borders:
            above, below = border.references
            self.assertEqual(above[1], self.first.copy(0, 60, 160, 40))
            self.assertEqual(below[1], self.first.copy(0, 0, 160, 40))
            self.assertEqual(above[0].size(), above[1].size())
            self.assertEqual(below[0].size(), below[1].size())
            self.assertFalse(above[0].intersects(self.frame))
            self.assertFalse(below[0].intersects(self.frame))
        rendered = session.borders[0].grab().toImage()
        self.assertEqual(rendered.pixelColor(120, 25), QColor("#556B5B"))  # bottom + 18% amber
        self.assertEqual(rendered.pixelColor(120, 180), QColor("#854132"))  # top + 18% amber
        self.assertEqual(rendered.pixelColor(120, 110).alpha(), 0)  # live box stays clear
        self.read.assert_not_called()

    def test_reference_strips_refresh_only_after_capture_and_never_enter_joined_image(self):
        self.capture()
        session = self.start()
        references = session.borders[0].references
        app.processEvents()
        self.assertIs(session.borders[0].references, references)
        self.assertEqual(session.findChildren(QTimer), [])
        self.read.assert_not_called()
        second = self.first.copy()
        second.fill(QColor("#6A283D"))
        self.read.side_effect = [second]
        self.tray.start_capture()
        for border in session.borders:
            self.assertEqual(border.references[0][1], second.copy(0, 60, 160, 40))
            self.assertEqual(border.references[1][1], second.copy(0, 0, 160, 40))
        joined = self.clipboard.setImage.call_args.args[0]
        self.assertEqual(joined.width(), 160)
        self.assertEqual(joined.height(), 200)
        self.assertEqual(joined.copy(0, 0, 160, 100), self.first)
        self.assertEqual(joined.copy(0, 100, 160, 100), second)
        app.processEvents()
        self.read.assert_called_once_with(self.frame)
        session.finish()
        self.assertTrue(all(not b.isVisible() for b in session.borders))

    def test_reference_strips_for_small_capture_at_negative_coordinates_do_not_resize(self):
        frame = QRect(-600, -100, 3, 12)
        image = QImage(3, 12, QImage.Format.Format_RGB32)
        image.fill(QColor("#305C6F"))
        above, below = reference_strips(frame, image)
        self.assertEqual(above[1], image)
        self.assertEqual(below[1], image)
        for rect, picture in (above, below):
            self.assertEqual(rect.size(), picture.size())
            self.assertFalse(rect.intersects(frame))
            self.assertEqual(rect.left(), frame.left())
        self.assertLess(above[0].bottom(), frame.top())
        self.assertGreater(below[0].top(), frame.bottom())

    def test_strip_at_screen_edge_is_clipped_instead_of_moved_inside_capture(self):
        self.frame.moveTop(2)
        self.capture()
        session = self.start()
        border = session.borders[0]
        above, _ = border.references
        self.assertLess(above[0].bottom(), border.area.top())
        rendered = border.grab().toImage()
        self.assertEqual(rendered.pixelColor(120, 40).alpha(), 0)
        self.assertFalse(above[0].intersects(self.frame))

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
        self.assertEqual(self.tray.preview.mode, "repeated")
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
        self.assertEqual(preview.mode, "repeated")

    def test_closing_preview_releases_border_and_escape(self):
        self.capture()
        session = self.start()
        self.tray.close_preview()
        self.assertTrue(session.closed)
        self.hotkey.return_value.close.assert_called_once()
        self.assertIsNone(self.tray.repeat_area)
        self.assertIsNone(self.tray.undo)

    def test_prtsc_adds_instead_of_starting_another_selection_and_insert_is_ignored(self):
        self.capture()
        session = self.start()
        self.read.side_effect = None
        self.read.return_value = self.first.copy()
        self.tray.start_capture()
        self.tray.start_record()
        self.assertIs(self.tray.repeat_area, session)
        self.assertIsNone(self.tray.capture)
        self.assertIsNone(self.tray.recording)
        self.assertEqual(self.tray.preview.image.size().height(), 200)
        self.read.assert_called_once_with(self.frame)
        self.clipboard.setImage.assert_called_once_with(self.tray.preview.image)

    def test_three_whole_images_stay_in_capture_order_including_duplicates(self):
        self.capture()
        session = self.start()
        second = self.first.copy()
        second.fill(QColor("#4A6240"))
        # Repeated content stays at the top of image 2; image 3 repeats image 1.
        for y in range(50):
            for x in range(second.width()):
                second.setPixelColor(x, y, self.first.pixelColor(x, y))
        self.read.side_effect = [second, self.first.copy()]
        self.read.assert_not_called()  # entering/scanning the UI never reads the screen
        for count in (2, 3):
            self.tray.start_capture()
            joined = self.tray.preview.image
            self.assertEqual(joined.size().width(), 160)
            self.assertEqual(joined.size().height(), 100 * count)
            self.assertEqual(self.tray.preview.count, count)
            self.assertEqual(session.count(), count)
            self.assertIn(f"repeat area · {count} ·", self.tray.preview.label()[0])
            self.assertFalse(self.tray.preview.timer.isActive())
            self.assertEqual(self.clipboard.setImage.call_args.args[0], joined)
        self.assertEqual(joined.copy(0, 0, 160, 100), self.first)
        self.assertEqual(joined.copy(0, 100, 160, 100), second)
        self.assertEqual(joined.copy(0, 200, 160, 100), self.first)
        self.assertEqual(self.read.call_count, 2)
        self.assertEqual(self.exclude.call_count, len(session.windows))
        self.flush.assert_not_called()  # supported capture exclusion needs no hiding
        self.hotkey.call_args.args[1]()
        app.processEvents()
        self.assertEqual(self.tray.preview.image, joined)
        self.assertEqual(self.tray.preview.mode, "repeated")
        self.assertEqual(self.tray.preview.label()[0], "copied · 3 images · 160×300")
        self.assertEqual(self.tray.preview.button_names(), ["draw", "save", "retake"])
        self.assertEqual(self.clipboard.setImage.call_count, 2)  # finishing never overwrites a newer copy
        self.assertTrue(all(not b.isVisible() for b in session.borders))
        session.add()
        self.assertEqual(self.read.call_count, 2)  # a finished session cannot append

    def test_negative_screen_position_is_read_in_real_pixels_without_resizing(self):
        self.frame = QRect(-600, 100, 160, 100)
        self.capture()
        self.start()
        self.read.side_effect = None
        self.read.return_value = self.first.copy()
        self.tray.start_capture()
        self.read.assert_called_once_with(QRect(-600, 100, 160, 100))
        self.assertEqual(self.tray.preview.image.copy(0, 100, 160, 100), self.first)

    def test_fallback_hides_all_own_windows_only_for_the_read_and_restores_opacity(self):
        self.capture()
        self.exclude.return_value = False
        session = self.start()
        session.borders[0].setWindowOpacity(0.75)
        before = [w.windowOpacity() for w in session.windows]

        def read(frame):
            self.assertEqual(frame, self.frame)
            self.assertTrue(all(w.windowOpacity() == 0 for w in session.windows))
            self.flush.assert_called_once()
            return self.first.copy()

        self.read.side_effect = read
        self.tray.start_capture()
        self.assertEqual([w.windowOpacity() for w in session.windows], before)
        self.assertTrue(all(w.isVisible() for w in session.windows))
        self.assertEqual(session.count(), 2)

    def test_failed_fallback_read_restores_windows_and_keeps_previous_image(self):
        self.capture()
        self.exclude.return_value = False
        session = self.start()
        self.read.side_effect = RuntimeError("demo read failure")
        with self.assertRaisesRegex(RuntimeError, "demo read failure"):
            session.add()
        self.assertTrue(all(w.windowOpacity() == 1 for w in session.windows))
        self.assertEqual(session.count(), 1)
        self.assertEqual(self.tray.preview.image, self.first)
        self.clipboard.setImage.assert_not_called()

    def test_finishing_three_images_with_button_keeps_result_and_releases_hotkey(self):
        self.capture()
        session = self.start()
        self.read.side_effect = [self.first.copy(), self.first.copy()]
        self.tray.start_capture()
        self.tray.start_capture()
        preview = self.tray.preview
        QTest.mouseClick(preview, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         preview.buttons["finish"].center())
        self.assertTrue(session.closed)
        self.assertIsNone(self.tray.repeat_area)
        self.assertEqual(preview.mode, "repeated")
        self.assertEqual(preview.count, 3)
        self.hotkey.return_value.close.assert_called_once()
        self.assertEqual(preview.image.height(), 300)

    def test_auto_save_removes_first_file_then_writes_one_final_joined_png_once(self):
        self.capture(auto_save=True)
        first_path = self.tray.undo["saved_path"]
        session = self.start()
        self.assertFalse(first_path.exists())
        self.add()
        self.assertEqual(list(first_path.parent.iterdir()), [])
        session.finish()
        path = self.tray.undo["saved_path"]
        self.assertEqual(QImage(str(path)), self.tray.preview.image)
        self.assertEqual(QImage(str(path)).height(), 200)
        self.assertEqual(list(path.parent.iterdir()), [path])
        session.finish()
        self.assertEqual(list(path.parent.iterdir()), [path])
        self.assertEqual(self.tray.preview.saved_path, path)
        self.assertEqual(self.tray.preview.label()[:2], ("saved · ", path.name))
        self.assertEqual(self.tray.preview.button_names(), ["draw", "retake"])

    def test_existing_drawing_stays_in_image_one_and_joined_draw_starts_fresh(self):
        self.capture(auto_save=True)
        preview = self.tray.preview
        preview.show_saved(self.tray.undo["saved_path"])
        annotated = self.first.copy()
        annotated.setPixelColor(10, 10, QColor("red"))
        preview.show_drawn(annotated)
        self.tray.undo.update(draw_base=self.first, shapes=["old demo shape"])
        self.start().finish()
        self.assertEqual(preview.image, annotated)
        self.assertIsNone(preview.save_state)
        self.assertNotIn("draw_base", self.tray.undo)
        self.assertNotIn("shapes", self.tray.undo)
        self.click("draw")
        self.assertEqual(self.tray.draw_window.image, annotated)
        self.assertEqual(self.tray.draw_window.shapes, [])

    def test_finish_one_image_hides_repeat_and_add_buttons(self):
        self.capture()
        self.start().finish()
        self.assertEqual(self.tray.preview.label()[0], "copied · 1 image · 160×100")
        self.assertEqual(self.tray.preview.button_names(), ["draw", "save", "retake"])

    def test_auto_save_uses_screenshot_jpg_format(self):
        self.prefs["format"] = "jpg"
        self.capture(auto_save=True)
        session = self.start()
        self.add()
        session.finish()
        path = self.tray.undo["saved_path"]
        self.assertEqual(path.suffix, ".jpg")
        self.assertTrue(path.read_bytes().startswith(b"\xff\xd8"))
        self.assertEqual(QImage(str(path)).size(), self.tray.preview.image.size())
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_manual_save_writes_joined_picture_once_and_draw_overwrites_same_file(self):
        self.capture()
        session = self.start()
        self.add()
        session.finish()
        self.assertFalse(Path(self.prefs["save_folder"]).exists())
        self.click("save")
        path = self.tray.undo["saved_path"]
        self.assertEqual(QImage(str(path)), self.tray.preview.image)
        self.click("save")
        self.assertEqual(list(path.parent.iterdir()), [path])
        self.draw_box().finish()
        self.assertEqual(QImage(str(path)).pixelColor(20, 140), QColor(COLORS["red"]))
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_draw_updates_whole_joined_picture_clipboard_and_auto_saved_file(self):
        self.capture(auto_save=True)
        session = self.start()
        self.add()
        session.finish()
        joined = self.tray.preview.image.copy()
        path = self.tray.undo["saved_path"]
        window = self.draw_box()
        self.assertEqual(window.image, joined)
        self.assertEqual(draw_title("repeated", 2, joined), "repeat area · 2 images · 160×200")
        self.assertTrue(self.tray.preview.held)
        window.finish()
        drawn = self.tray.preview.image
        self.assertEqual(drawn.size(), joined.size())
        self.assertEqual(drawn.pixelColor(20, 140), QColor(COLORS["red"]))
        self.assertEqual(self.clipboard.setImage.call_args.args[0], drawn)
        self.assertEqual(QImage(str(path)), drawn)
        self.click("draw")
        self.assertEqual(len(self.tray.draw_window.shapes), 1)
        self.tray.draw_window.undo()
        self.tray.draw_window.finish()
        self.assertEqual(self.tray.preview.image, joined)

    def test_escape_in_draw_leaves_joined_result_unchanged(self):
        self.capture()
        session = self.start()
        self.add()
        session.finish()
        joined = self.tray.preview.image.copy()
        self.clipboard.setImage.reset_mock()
        window = self.draw_box()
        QTest.keyClick(window, Qt.Key.Key_Escape)
        self.assertEqual(self.tray.preview.image, joined)
        self.clipboard.setImage.assert_not_called()
        self.assertFalse(self.tray.preview.held)

    def test_active_retake_removes_last_image_and_updates_references_without_screen_read(self):
        self.capture()
        session = self.start()
        second = self.first.copy()
        second.fill(QColor("#4A6240"))
        self.add(second)
        self.add()
        self.tray.preview.set_hover("retake")
        self.assertEqual(self.tray.preview.label()[0], "retake · remove image 3")
        self.click("retake")
        self.assertEqual(session.count(), 2)
        self.assertEqual(self.tray.preview.count, 2)
        self.assertEqual(self.tray.preview.image.copy(0, 100, 160, 100), second)
        self.assertEqual(self.clipboard.setImage.call_args.args[0], self.tray.preview.image)
        self.assertEqual(session.borders[0].references[0][1], second.copy(0, 60, 160, 40))
        self.assertFalse(session.closed)
        self.assertFalse(self.tray.preview.timer.isActive())
        self.assertEqual(self.read.call_count, 2)

    def test_active_retake_preserves_newer_clipboard_copy_and_finish_does_not_replace_it(self):
        self.capture()
        session = self.start()
        self.add()
        self.version += 1  # another app copied something after our latest image
        self.clipboard.setImage.reset_mock()
        self.click("retake")
        self.assertEqual(session.count(), 1)
        self.assertEqual(self.tray.preview.image, self.first)
        session.finish()
        self.clipboard.setImage.assert_not_called()

    def test_retake_with_image_one_restores_clipboard_and_reselects_same_frozen_screen(self):
        self.capture(auto_save=True)
        frozen = self.tray.undo["frozen"]
        session = self.start()
        folder = Path(self.prefs["save_folder"])
        with patch("snapclick.tray.Capture") as capture:
            self.click("retake")
            capture.assert_called_once_with(frozen)
        self.restored.assert_called_once_with(self.previous)
        self.assertTrue(session.closed)
        self.assertIsNone(self.tray.repeat_area)
        self.hotkey.return_value.close.assert_called_once()
        self.assertEqual(list(folder.iterdir()), [])  # discarding never saves a final image

    def test_finished_retake_restores_previous_clipboard_deletes_file_and_reselects(self):
        self.capture(auto_save=True)
        frozen = self.tray.undo["frozen"]
        session = self.start()
        self.add()
        session.finish()
        path = self.tray.undo["saved_path"]
        with patch("snapclick.tray.Capture") as capture:
            self.click("retake")
            capture.assert_called_once_with(frozen)
        self.restored.assert_called_once_with(self.previous)
        self.assertFalse(path.exists())

    def test_finished_retake_preserves_newer_copy_and_deletes_saved_result(self):
        self.capture(auto_save=True)
        session = self.start()
        self.add()
        session.finish()
        path = self.tray.undo["saved_path"]
        self.version += 1
        self.clipboard.setImage.reset_mock()
        with patch("snapclick.tray.Capture"):
            self.click("retake")
        self.restored.assert_not_called()
        self.clipboard.setImage.assert_not_called()
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
