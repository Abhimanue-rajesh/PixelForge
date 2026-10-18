import sys

from PySide6.QtWidgets import QApplication

from pixelforge.ui.main_window import MainWindow


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("PixelForge")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
