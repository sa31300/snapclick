"""Recording selection, controls, frame sheets and independent settings."""
import ctypes
import os
import tempfile
import unittest
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from snapclick.hotkey import DEFAULT_HOTKEY, GlobalHotkey, RECORD_HOTKEY, RECORD_HOTKEY_ID, WM_HOTKEY
from snapclick.record import LiveSelection, Record, RecordBar
from snapclick.frames import FrameBuffer, GAP, TAG_HEIGHT, clock_text, make_sheet
from snapclick import settings
from snapclick.capture import draw_cursor
from snapclick.settings_window import SettingsWindow
from snapclick.tray import Tray

app = QApplication.instance() or QApplication([])


def demo_image(width=800, height=600, color="#22313D"):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
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
        mock = patch("snapclick.clicks.user32.GetAsyncKeyState", return_value=0)
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
            self.assertTrue(session.bar.record.isEnabled())
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

    @patch("snapclick.record.GlobalHotkey")
    def test_stop_and_escape_keep_recording_once(self, hotkey):
        for use_escape in (False, True):
            session = Record()
            recorded, finished = [], []
            session.recorded.connect(lambda image, count, elapsed: recorded.append((image, count, elapsed)))
            session.finished.connect(lambda: finished.append(True))
            session.selection.click(QPoint(10, 20))
            session.selection.click(QPoint(210, 150))
            with patch("snapclick.record.time.monotonic", return_value=100):
                session.bar.record.click()
            self.assertTrue(session.timer.isActive())
            self.assertTrue(all(b.recording for b in session.borders))
            self.assertEqual(session.bar.cancel.text(), "■ stop")
            self.assertEqual(session.bar.clock.text(), "0:00 / 0:30")
            with patch("snapclick.record.time.monotonic", return_value=103.5):
                if use_escape:
                    hotkey.call_args.args[1]()
                else:
                    session.bar.cancel.click()
            session.stop()
            self.assertEqual(finished, [True])
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0][1:], (2, 3.5))
            self.assertFalse(session.timer.isActive())
            self.assertIsNone(session.buffer)
            self.assertFalse(session.bar.isVisible())

    @patch("snapclick.record.GlobalHotkey")
    def test_max_length_stops_and_keeps_final_frame(self, hotkey):
        prefs = dict(settings.load(), record_max_length=15, record_frames=8)
        session = Record(prefs)
        recorded = []
        session.recorded.connect(lambda image, count, elapsed: recorded.append((image, count, elapsed)))
        session.selection.click(QPoint(10, 20))
        session.selection.click(QPoint(210, 150))
        with patch("snapclick.record.time.monotonic", return_value=100):
            session.start()
        with patch("snapclick.record.time.monotonic", return_value=114.9):
            session.tick()
        self.assertEqual(session.bar.clock.text(), "0:14 / 0:15")
        with patch("snapclick.record.time.monotonic", return_value=115.1):
            session.tick()
        self.assertTrue(session.closed)
        self.assertEqual(recorded[0][1:], (2, 15))

    @patch("snapclick.record.GlobalHotkey")
    @patch("snapclick.clicks.user32.GetAsyncKeyState", return_value=0)
    def test_mouse_button_is_polled_only_while_recording(self, mouse_state, hotkey):
        session = Record()
        session.selection.click(QPoint(10, 20))
        session.selection.click(QPoint(210, 150))
        mouse_state.assert_not_called()
        with patch("snapclick.record.time.monotonic", return_value=100):
            session.start()
        self.assertEqual(mouse_state.call_count, 2)  # initialize, then read the first frame
        with patch("snapclick.record.time.monotonic", return_value=101):
            session.stop()
        self.assertEqual(mouse_state.call_count, 3)  # the final frame
        session.close()
        self.assertEqual(mouse_state.call_count, 3)
        self.assertIsNone(session.clicks)


class FrameSheetTest(unittest.TestCase):
    def test_skip_duplicates_keep_first_and_last(self):
        buffer = FrameBuffer(QSize(180, 90), 12)
        picture = demo_image(180, 90)
        for elapsed in (0, 0.2, 0.4):
            buffer.add(picture, elapsed)
        buffer.add(picture, 10, final=True)
        self.assertEqual([t for t, _ in buffer.selected()], [0, 10])

    def test_evenly_spaced_changed_frames(self):
        buffer = FrameBuffer(QSize(180, 90), 8)
        for i in range(20):
            buffer.add(demo_image(180, 90, QColor(i, 0, 0)), i)
        self.assertEqual([t for t, _ in buffer.selected()], [0, 3, 5, 8, 11, 14, 16, 19])

    def test_four_columns_labels_above_unscaled_pictures(self):
        frames = [(i, demo_image(180, 90, QColor(i * 20, 0, 0))) for i in range(6)]
        sheet = make_sheet(frames)
        self.assertEqual(sheet.size(), QSize(4 * 180 + 5 * GAP, 2 * (90 + TAG_HEIGHT) + 3 * GAP))
        for i, (_, image) in enumerate(frames):
            x = GAP + (i % 4) * (180 + GAP)
            y = GAP + (i // 4) * (90 + TAG_HEIGHT + GAP)
            self.assertEqual(sheet.pixelColor(x, y), QColor("#FFB000"))
            self.assertEqual(sheet.copy(x, y + TAG_HEIGHT, 180, 90), image)
        self.assertEqual(sheet.pixelColor(sheet.width() - 1, sheet.height() - 1), QColor("#0D0E10"))

    def test_large_sheets_stay_within_2400_pixels(self):
        for count in (8, 12, 16):
            for size in (QSize(7680, 2160), QSize(1200, 8000)):
                buffer = FrameBuffer(size, count)
                frame = demo_image(buffer.size.width(), buffer.size.height())
                sheet = make_sheet([(i, frame) for i in range(count)])
                self.assertLessEqual(max(sheet.width(), sheet.height()), 2400)
                self.assertLessEqual(buffer.size.width(), size.width())
                self.assertLessEqual(buffer.size.height(), size.height())

    def test_clock(self):
        self.assertEqual(clock_text(4.9), "0:04")
        self.assertEqual(clock_text(60), "1:00")

    def test_one_pixel_wide_selection_stays_valid_when_scaled(self):
        buffer = FrameBuffer(QSize(1, 8000), 16)
        buffer.add(demo_image(1, 8000), 0)
        self.assertEqual(buffer.selected()[0][1].size(), buffer.size)
        self.assertGreater(buffer.size.width(), 0)
        self.assertFalse(make_sheet(buffer.selected()).isNull())


class RecordingSettingsTest(unittest.TestCase):
    def test_settings_save_immediately_and_do_not_change_screenshot_toggle(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(settings, "SETTINGS_FILE", Path(folder) / "settings.json"):
                settings.save(dict(settings.DEFAULTS, save_folder=str(Path(folder) / "captures"), auto_save=True))
                window = SettingsWindow()
                window.record_frames.itemAt(2).widget().click()
                window.record_max_length.itemAt(0).widget().click()
                window.auto_save_recordings.click()
                prefs = settings.load()
                self.assertEqual(prefs["record_frames"], 16)
                self.assertEqual(prefs["record_max_length"], 15)
                self.assertTrue(prefs["auto_save_recordings"])
                self.assertTrue(prefs["auto_save"])
                window.close()

    def test_recording_name_is_png_with_its_own_prefix_and_collision_suffix(self):
        when = datetime(2026, 1, 2, 3, 4, 5)
        with tempfile.TemporaryDirectory() as folder:
            first = settings.new_file_path(folder, "png", when, prefix="rec_")
            self.assertEqual(first.name, "rec_2026-01-02_03-04-05.png")
            first.touch()
            self.assertEqual(settings.new_file_path(folder, "png", when, prefix="rec_").name,
                             "rec_2026-01-02_03-04-05_2.png")
            self.assertEqual(settings.new_file_path(folder, "jpg", when).name, "2026-01-02_03-04-05.jpg")

    @patch("snapclick.tray.QGuiApplication.clipboard")
    def test_recording_save_is_independent_and_always_png(self, clipboard):
        for screenshot_on in (False, True):
            for recording_on in (False, True):
                prefs = dict(settings.load(), auto_save=screenshot_on, auto_save_recordings=recording_on, format="jpg")
                tray = SimpleNamespace(recording=SimpleNamespace(prefs=prefs), save_image=Mock())
                image = demo_image(180, 90)
                Tray._recorded(tray, image, 2, 10)
                clipboard.return_value.setImage.assert_called_with(image)
                self.assertEqual(tray.save_image.call_count, int(recording_on))
                if recording_on:
                    self.assertEqual(tray.save_image.call_args.args[1]["format"], "png")
                    self.assertEqual(tray.save_image.call_args.kwargs, {"prefix": "rec_"})
                self.assertEqual(prefs["auto_save"], screenshot_on)
                self.assertEqual(prefs["format"], "jpg")


class RecordingCursorTest(unittest.TestCase):
    @patch("snapclick.capture.gdi32.DeleteObject")
    @patch("snapclick.capture.user32.DrawIconEx")
    @patch("snapclick.capture.user32.GetIconInfo")
    @patch("snapclick.capture.user32.GetCursorInfo")
    def test_pointer_uses_hotspot_and_frees_bitmaps(self, cursor, icon, draw, delete):
        def cursor_info(pointer):
            info = pointer._obj
            self.assertEqual(info.cbSize, ctypes.sizeof(info))
            info.flags, info.hCursor = 1, 123
            info.ptScreenPos.x, info.ptScreenPos.y = 40, 50
            return True

        def icon_info(handle, pointer):
            info = pointer._obj
            info.xHotspot, info.yHotspot = 3, 4
            info.hbmMask, info.hbmColor = 456, 789
            return True

        cursor.side_effect = cursor_info
        icon.side_effect = icon_info
        draw_cursor(99, QPoint(-10, 20))
        draw.assert_called_once_with(99, 47, 26, 123, 0, 0, 0, None, 3)
        self.assertEqual([call.args[0] for call in delete.call_args_list], [456, 789])


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
