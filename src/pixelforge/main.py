import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QCheckBox,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhotoTidy")
        self.resize(900, 600)
        self.folder: Path | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        row = QHBoxLayout()
        self.pick_btn = QPushButton("Choose folder…")
        self.pick_btn.clicked.connect(self.choose_folder)
        self.folder_label = QLabel("No folder selected")
        row.addWidget(self.pick_btn)
        row.addWidget(self.folder_label, 1)
        layout.addLayout(row)

        self.subfolders = QCheckBox("Include subfolders")
        self.subfolders.setChecked(True)
        layout.addWidget(self.subfolders)

        layout.addStretch()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select photo folder")
        if path:
            self.folder = Path(path)
            self.folder_label.setText(str(self.folder))


def run():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
