"""Repeat area step 1: keep the chosen rectangle marked over the live screen (§2e)."""
from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from snapclick.capture import ACCENT
from snapclick.hotkey import GlobalHotkey, REPEAT_ESCAPE_ID
from snapclick.record import RecordBorder


class RepeatArea(QObject):
    finished = Signal()

    def __init__(self, frame):
        super().__init__()
        self.frame = QRect(frame)
        self.closed = False
        self.borders = [RecordBorder(self.frame, screen, color=ACCENT) for screen in QGuiApplication.screens()]
        # Finish outside the native filter callback so it can safely unregister itself.
        self.escape = GlobalHotkey(QGuiApplication.instance(), lambda: QTimer.singleShot(0, self.finish),
                                  {"vk": 0x1B, "mods": 0, "name": "Esc"}, REPEAT_ESCAPE_ID)

    def finish(self):
        if self.closed:
            return
        self.closed = True
        self.escape.close()
        for border in self.borders:
            border.close()
        self.finished.emit()
