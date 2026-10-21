"""Tests for passing the wheel on (spec §6). Run: .venv\\Scripts\\python -m unittest discover tests"""
import ctypes
import unittest

from snapclick.stack import INPUT, MOUSEEVENTF_WHEEL, OWN_WHEEL, move_input, needs_real_wheel, wheel_input


class WheelTest(unittest.TestCase):
    def test_browsers_get_a_real_wheel(self):
        self.assertTrue(needs_real_wheel("Chrome_WidgetWin_1"))  # Brave, Chrome, Edge

    def test_terminals_keep_the_posted_wheel(self):
        self.assertFalse(needs_real_wheel("CASCADIA_HOSTING_WINDOW_CLASS"))  # Windows Terminal
        self.assertFalse(needs_real_wheel("ConsoleWindowClass"))  # classic console

    def test_wheel_input(self):
        down = wheel_input(-120)
        self.assertEqual(down.mi.dwFlags, MOUSEEVENTF_WHEEL)
        self.assertEqual(down.mi.mouseData, 0xFFFFFF88)  # -120 as Windows reads it
        self.assertEqual(down.mi.dwExtraInfo, OWN_WHEEL)
        self.assertEqual(wheel_input(1).mi.mouseData, 1)  # tiny touchpad steps

    def test_move_input_spans_all_monitors(self):
        virtual = (-1920, 0, 3840, 1080)  # a monitor left of the main one
        self.assertEqual(move_input(-1920, 0, virtual).mi.dx, 0)
        self.assertEqual(move_input(1919, 1079, virtual).mi.dx, 65535)
        self.assertEqual(move_input(1919, 1079, virtual).mi.dy, 65535)
        self.assertEqual(move_input(0, 0, virtual).mi.dx, 32776)  # middle

    def test_input_size_matches_windows(self):
        self.assertEqual(ctypes.sizeof(INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


if __name__ == "__main__":
    unittest.main()
