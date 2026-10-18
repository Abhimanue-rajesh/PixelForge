from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QMessageBox, QScrollArea, QVBoxLayout, QWidget,
)

from pixelforge.core.conversion import OUTPUT_FORMATS
from pixelforge.ui.widgets import ElidedLabel
from pixelforge.ui.workers import ConversionScanWorker, ConversionWorker


class ConversionPage(QScrollArea):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.directory = None
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        description = QLabel("Convert images to a chosen format. New files are saved beside their originals.")
        description.setProperty("role", "muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        card = QFrame()
        card.setProperty("card", True)
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 18, 20, 18)
        labels = QVBoxLayout()
        labels.addWidget(QLabel("Image folder"))
        self.folder_label = ElidedLabel("No folder selected")
        self.folder_label.setProperty("role", "muted")
        labels.addWidget(self.folder_label)
        row.addLayout(labels, 1)
        self.choose_btn = window.button("Choose folder…", self.choose_folder)
        row.addWidget(self.choose_btn)
        layout.addWidget(card)

        card = QFrame()
        card.setProperty("card", True)
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 18, 20, 18)
        label = QLabel("Convert to")
        row.addWidget(label, 1)
        self.format = QComboBox()
        self.format.setMinimumWidth(180)
        for name, extension in OUTPUT_FORMATS.items():
            title = "JPG" if name == "JPEG" else name
            self.format.addItem(f"{title} ({extension})", name)
        self.format.setAccessibleName("Output image format")
        label.setBuddy(self.format)
        row.addWidget(self.format)
        layout.addWidget(card)

        card = QFrame()
        card.setProperty("card", True)
        options = QVBoxLayout(card)
        options.setContentsMargins(20, 18, 20, 18)
        options.setSpacing(12)
        self.subfolders = QCheckBox("Include subfolders")
        self.subfolders.setChecked(True)
        self.delete_originals = QCheckBox("Send originals to the Recycle Bin after conversion")
        options.addWidget(self.subfolders)
        options.addWidget(self.delete_originals)
        layout.addWidget(card)

        note = QLabel(
            "Still images only. Files already using the selected extension are left unchanged. "
            "Existing filenames get a numbered suffix. JPG uses quality 90; JPG and BMP remove transparency. "
            "GIF uses a limited colour palette. A conversion.log file records the results in the chosen folder."
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.convert_btn = window.button("Convert images", self.start, "primary")
        layout.addWidget(self.convert_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.result = QLabel()
        self.result.setProperty("role", "muted")
        self.result.setWordWrap(True)
        self.result.hide()
        layout.addWidget(self.result)
        layout.addStretch()
        self.setWidget(body)
        body.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
        self.refresh()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose image folder")
        if path:
            self.directory = Path(path)
            self.folder_label.set_full_text(path)
            self.result.hide()
            self.refresh()

    def refresh(self):
        idle = not self.window.busy
        for control in (self.choose_btn, self.format, self.subfolders, self.delete_originals):
            control.setEnabled(idle)
        self.convert_btn.setEnabled(idle and self.directory is not None)

    def start(self):
        if self.window.busy or self.directory is None:
            return
        self.result.hide()
        self.window.set_busy(True, "Checking images for conversion")
        worker = ConversionScanWorker(self.directory, self.format.currentData(), self.subfolders.isChecked())
        worker.done.connect(self.on_prepared)
        self.window.run_worker(worker)

    def on_prepared(self, files):
        self.window.set_idle()
        if not files:
            self.result.setText("No images need conversion to the selected format.")
            self.result.show()
            return
        recycle = self.delete_originals.isChecked()
        if recycle:
            answer = QMessageBox.question(
                self, "Convert images and recycle originals",
                f"Images to convert: {len(files)}\nFolder: {self.directory}\n\n"
                f"Save {self.format.currentText()} files beside the originals, then send each successfully "
                "converted original to the Recycle Bin?\n\nOriginals are kept if conversion fails. "
                "Existing files are never overwritten.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.window.set_busy(False, "Converting images")
        worker = ConversionWorker(files, self.directory, self.format.currentData(), recycle)
        worker.progress.connect(self.window.on_progress)
        worker.done.connect(self.on_done)
        self.window.run_worker(worker)

    def on_done(self, saved, recycled, errors):
        self.result.setText(
            f"Images converted: {len(saved)}. Originals sent to Recycle Bin: {recycled}. Problems: {len(errors)}."
        )
        self.result.show()
        self.window.set_idle()
        self.window.warn(errors)
        if self.window.folder:
            self.window.rescan()
