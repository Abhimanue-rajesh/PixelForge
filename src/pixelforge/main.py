import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from pixelforge.ui.main_window import MainWindow
from pixelforge.ui.theme import apply_theme, load_fonts


def run(smoke_test: bool = False):
    app = QApplication(sys.argv)
    app.setApplicationName("PixelForge")
    app.setStyle("Fusion")  # consistent base that our stylesheet builds on
    load_fonts(app)
    apply_theme(app)
    try:  # follow Windows light/dark switching while the app is open (Qt 6.5+)
        app.styleHints().colorSchemeChanged.connect(lambda *_: apply_theme(app))
    except AttributeError:
        pass
    window = MainWindow()
    window.show()
    if smoke_test:
        QTimer.singleShot(0, app.quit)
    sys.exit(app.exec())
