import sys

from PySide6.QtWidgets import QApplication

from pixelforge.ui.main_window import MainWindow
from pixelforge.ui.theme import apply_theme


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("PixelForge")
    app.setStyle("Fusion")  # consistent base that our stylesheet builds on
    apply_theme(app)
    try:  # follow Windows light/dark switching while the app is open (Qt 6.5+)
        app.styleHints().colorSchemeChanged.connect(lambda *_: apply_theme(app))
    except AttributeError:
        pass
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
