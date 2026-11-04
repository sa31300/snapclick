"""Record step 3: preview, PNG Save, editable Draw and safe Retake."""
import os
import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from snapclick import settings
from snapclick.draw import COLORS, draw_title
from snapclick.tray import Tray

app = QApplication.instance() or QApplication([])


class PreviewTray(SimpleNamespace):
    """Support weak references when Qt connects a bound test method."""


class RecordingPreviewTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.save_folder = Path(self.folder.name) / "captures"
        self.prefs = dict(settings.DEFAULTS, save_folder=str(self.save_folder), show_preview=True,
                          auto_save=True, format="jpg")  # screenshots and recordings stay separate
        self.image = QImage(360, 180, QImage.Format.Format_RGB32)
        self.image.fill(QColor("#22313D"))
        self.previous = QMimeData()
        self.previous.setText("before recording")
        self.version = 100
        self.copied = []
        for name, options in (
            ("snapclick.settings.SETTINGS_FILE", {"new": Path(self.folder.name) / "settings.json"}),
            ("snapclick.tray.save_clipboard", {"return_value": self.previous}),
            ("snapclick.tray.clipboard_version", {"side_effect": lambda: self.version}),
            ("snapclick.tray.restore_clipboard", {}),
            ("snapclick.tray.QGuiApplication.clipboard", {}),
        ):
            mock = patch(name, **options)
            result = mock.start()
            self.addCleanup(mock.stop)
            if name.endswith("restore_clipboard"):
                self.restored = result
            elif name.endswith("save_clipboard"):
                self.snapshot = result
            elif name.endswith("QGuiApplication.clipboard"):
                result.return_value.setImage.side_effect = self.copied_image

        self.tray = PreviewTray(preview=None, draw_window=None, undo=None, stack=None, repeat_area=None,
                               start_record=Mock(), start_capture=Mock(), showMessage=Mock())
        for name in ("save_image", "save_from_preview", "open_draw", "_drawn", "_draw_closed", "copy",
                     "_preview_closed", "close_preview", "undo_and_retake", "delete_file"):
            setattr(self.tray, name, MethodType(getattr(Tray, name), self.tray))
        self.addCleanup(self.tray.close_preview)

    def copied_image(self, image):
        self.version += 1
        self.copied.append(image.copy())

    def record(self, auto_save=False, show_preview=True):
        self.prefs.update(auto_save_recordings=auto_save, show_preview=show_preview)
        settings.save(self.prefs)
        self.tray.recording = SimpleNamespace(prefs=self.prefs)
        Tray._recorded(self.tray, self.image, 6, 10.8)
        Tray._record_done(self.tray)

    def draw_box(self):
        self.tray.open_draw()
        window = self.tray.draw_window
        window.canvas.ratio = 1
        canvas = window.canvas
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(40, 40))
        QTest.mouseMove(canvas, QPoint(180, 120))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(180, 120))
        return window

    def save(self):
        preview = self.tray.preview
        QTest.mouseClick(preview, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         preview.buttons["save"].center())

    def test_preview_shows_recording_label_and_no_add_below(self):
        self.record()
        preview = self.tray.preview
        self.assertEqual(preview.mode, "recorded")
        self.assertEqual(preview.label()[0], "recorded · 6 frames · 0:10")
        self.assertEqual(preview.button_names(), ["draw", "save", "retake"])
        self.assertEqual(preview.timer.interval(), 3000)
        self.assertEqual(self.copied, [self.image])
        self.assertFalse(self.save_folder.exists())

    def test_draw_holds_preview_and_copies_drawings(self):
        self.record()
        window = self.draw_box()
        self.assertTrue(self.tray.preview.held)
        self.assertFalse(self.tray.preview.timer.isActive())
        self.assertEqual(draw_title("recorded", 6, self.image), "recording · 6 frames · 360×180")
        window.finish()
        self.assertFalse(self.tray.preview.held)
        self.assertEqual(self.copied[-1].pixelColor(40, 80), QColor(COLORS["red"]))
        self.assertEqual(self.tray.preview.label()[0], "copied · with drawings")
        self.assertNotIn("add", self.tray.preview.buttons)

    def test_escape_discards_drawings_and_releases_preview(self):
        self.record()
        window = self.draw_box()
        QTest.keyClick(window, Qt.Key.Key_Escape)
        self.assertEqual(self.copied, [self.image])
        self.assertEqual(self.tray.preview.image, self.image)
        self.assertFalse(self.tray.preview.held)
        self.assertEqual(self.tray.preview.label()[0], "recorded · 6 frames · 0:10")

    def test_draw_again_keeps_shapes_editable(self):
        self.record()
        self.draw_box().finish()
        self.tray.open_draw()
        window = self.tray.draw_window
        self.assertEqual(window.image, self.image)
        self.assertEqual(len(window.shapes), 1)
        window.undo()
        window.finish()
        self.assertEqual(self.copied[-1], self.image)

    def test_save_writes_one_recording_png_with_drawings(self):
        self.record()
        self.draw_box().finish()
        self.save()
        path = self.tray.undo["saved_path"]
        self.assertTrue(path.name.startswith("rec_"))
        self.assertEqual(path.suffix, ".png")
        self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(QImage(str(path)).pixelColor(40, 80), QColor(COLORS["red"]))
        self.save()  # the green check must not save a duplicate
        self.assertEqual(list(self.save_folder.iterdir()), [path])
        self.assertEqual(self.tray.preview.label()[:2], ("saved ✓ ", path.name))

    def test_auto_save_uses_recording_toggle_and_draw_overwrites_same_file(self):
        self.prefs["auto_save"] = False
        self.record(auto_save=True)
        path = self.tray.undo["saved_path"]
        self.assertTrue(path.exists())
        self.assertEqual(self.tray.preview.button_names(), ["draw", "retake"])
        self.draw_box().finish()
        self.assertEqual(list(self.save_folder.iterdir()), [path])
        self.assertEqual(QImage(str(path)).pixelColor(40, 80), QColor(COLORS["red"]))

    def test_retake_restores_clipboard_deletes_manual_save_and_restarts_record(self):
        self.record()
        self.draw_box().finish()
        self.save()
        path = self.tray.undo["saved_path"]
        self.tray.undo_and_retake()
        self.restored.assert_called_once_with(self.previous)
        self.assertFalse(path.exists())
        self.tray.start_record.assert_called_once_with()
        self.tray.start_capture.assert_not_called()
        self.assertIsNone(self.tray.preview)
        self.assertIsNone(self.tray.undo)

    def test_retake_keeps_a_newer_clipboard_copy_and_deletes_auto_save(self):
        self.record(auto_save=True)
        path = self.tray.undo["saved_path"]
        self.version += 1  # another app copied after the recording
        self.tray.undo_and_retake()
        self.restored.assert_not_called()
        self.assertFalse(path.exists())
        self.tray.start_record.assert_called_once_with()

    @patch("snapclick.preview.subprocess.Popen")
    def test_saved_file_link_opens_the_recording_file(self, explorer):
        self.record()
        self.save()
        path = self.tray.undo["saved_path"]
        link = self.tray.preview.label_parts()[2]
        self.assertIsNotNone(link)
        QTest.mouseClick(self.tray.preview, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, link.center())
        explorer.assert_called_once_with(f'explorer /select,"{path}"')

    def test_preview_off_still_copies_and_saves_without_retaining_undo(self):
        self.record(auto_save=True, show_preview=False)
        self.assertEqual(self.copied, [self.image])
        self.assertEqual(len(list(self.save_folder.glob("rec_*.png"))), 1)
        self.assertIsNone(self.tray.preview)
        self.assertIsNone(self.tray.undo)
        self.snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
