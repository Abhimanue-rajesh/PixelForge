from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from pixelforge.ui.widgets import ElidedLabel
from pixelforge.ui.workers import MetadataWorker


class MetadataPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.source = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        description = QLabel("Remove embedded details such as camera information, dates, location and comments.")
        description.setWordWrap(True)
        description.setProperty("role", "muted")
        layout.addWidget(description)

        card = QFrame()
        card.setProperty("card", True)
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 18, 20, 18)
        labels = QVBoxLayout()
        labels.addWidget(QLabel("Image file"))
        self.path_label = ElidedLabel("Choose an image to clean")
        self.path_label.setProperty("role", "muted")
        labels.addWidget(self.path_label)
        row.addLayout(labels, 1)
        self.choose_btn = window.button("Choose image…", self.choose_image)
        row.addWidget(self.choose_btn)
        layout.addWidget(card)

        card = QFrame()
        card.setProperty("card", True)
        settings = QVBoxLayout(card)
        settings.setContentsMargins(20, 18, 20, 18)
        self.overwrite = QCheckBox("Overwrite the original image")
        self.overwrite.toggled.connect(self.refresh)
        settings.addWidget(self.overwrite)
        hint = QLabel("Off by default. Save a clean copy and keep the original with its metadata.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        settings.addWidget(hint)
        layout.addWidget(card)

        note = QLabel(
            "JPEG, PNG, WebP, BMP and single-page TIFF. Saving JPEG again can affect image quality. "
            "Removing rotation information or colour profiles can change how an image looks. "
            "Animated and multi-page files are left untouched."
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.clean_btn = window.button("Remove metadata and save as…", self.start, "primary")
        layout.addWidget(self.clean_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.result = QLabel()
        self.result.setObjectName("flash")
        self.result.setWordWrap(True)
        self.result.hide()
        layout.addWidget(self.result)
        layout.addStretch()
        self.refresh()

    def refresh(self):
        busy = self.window.busy
        self.choose_btn.setEnabled(not busy)
        self.overwrite.setEnabled(not busy)
        self.clean_btn.setEnabled(not busy and self.source is not None)
        self.clean_btn.setText("Remove metadata…" if self.overwrite.isChecked() else "Remove metadata and save as…")

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose image", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)"
        )
        if path:
            self.source = Path(path)
            self.path_label.set_full_text(str(self.source))
            self.result.hide()
            self.refresh()

    def start(self):
        if self.source is None or self.window.busy:
            return
        overwrite = self.overwrite.isChecked()
        if overwrite:
            answer = QMessageBox.question(
                self, "Overwrite original image",
                f"Remove metadata and replace this original image?\n{self.source}\n\n"
                "The original metadata cannot be restored. Saving JPEG again can affect image quality.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            destination = self.source
        else:
            suggested = self.source.with_name(f"{self.source.stem}_clean{self.source.suffix}")
            path, _ = QFileDialog.getSaveFileName(
                self, "Save clean image", str(suggested), f"Image (*{self.source.suffix})"
            )
            if not path:
                return
            destination = Path(path)
            if not destination.suffix:
                destination = destination.with_suffix(self.source.suffix)
        self.result.hide()
        self.window.set_busy(True)
        worker = MetadataWorker(self.source, destination, overwrite)
        worker.done.connect(self.on_done)
        self.window.run_worker(worker)

    def on_done(self, path):
        self.result.setText(f"Saved image without embedded metadata.\n{path}")
        self.result.show()
        self.window.set_idle()
        if self.window.folder:
            self.window.rescan()
