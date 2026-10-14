"""Snapclick entry point. Run with: python -m snapclick"""
import sys

from PySide6.QtWidgets import QApplication

from snapclick.tray import Tray


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # tray app: keep running with no windows
    tray = Tray(app)
    tray.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
