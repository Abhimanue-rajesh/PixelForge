from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pixelforge.ui.widgets import ElidedLabel
from pixelforge.ui.workers import RotationWorker


class RotationPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.input_dir = None
        self.output_dir = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        description = QLabel("Rotate the images in a folder and save the results with a rotated_ filename prefix.")
        description.setProperty("role", "muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.folder_buttons = []
        self.folder_labels = {}
        for key, title in (("input", "Input folder"), ("output", "Output folder")):
            card = QFrame()
            card.setProperty("card", True)
            row = QHBoxLayout(card)
            row.setContentsMargins(20, 18, 20, 18)
            labels = QVBoxLayout()
            labels.addWidget(QLabel(title))
            path_label = ElidedLabel("No folder selected")
            path_label.setProperty("role", "muted")
            self.folder_labels[key] = path_label
            labels.addWidget(path_label)
            row.addLayout(labels, 1)
            button = window.button("Choose folder…", lambda checked=False, kind=key: self.choose_folder(kind))
            button.setAccessibleName(f"Choose {key} folder")
            self.folder_buttons.append(button)
            row.addWidget(button)
            layout.addWidget(card)

        card = QFrame()
        card.setProperty("card", True)
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 18, 20, 18)
        labels = QVBoxLayout()
        title = QLabel("Rotation angle")
        labels.addWidget(title)
        hint = QLabel("Positive values rotate counterclockwise. Negative values rotate clockwise.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        labels.addWidget(hint)
        row.addLayout(labels, 1)
        self.angle = QDoubleSpinBox()
        self.angle.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.angle.setRange(-360, 360)
        self.angle.setDecimals(2)
        self.angle.setSuffix("°")
        self.angle.setValue(45)
        self.angle.setAccessibleName("Rotation angle in degrees")
        title.setBuddy(self.angle)
        row.addWidget(self.angle)
        layout.addWidget(card)

        note = QLabel(
            "Still images only; subfolders are not included. The canvas expands to fit the rotated image. "
            "Original files stay in place and existing output files are skipped. "
            "Each run records saved and skipped files in rotation.log in the output folder."
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.rotate_btn = window.button("Rotate images", self.start, "primary")
        layout.addWidget(self.rotate_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.result = QLabel()
        self.result.setProperty("role", "muted")
        self.result.setWordWrap(True)
        self.result.hide()
        layout.addWidget(self.result)
        layout.addStretch()
        self.refresh()

    def choose_folder(self, kind):
        path = QFileDialog.getExistingDirectory(self, f"Choose {kind} folder")
        if path:
            if kind == "input":
                self.input_dir = Path(path)
            else:
                self.output_dir = Path(path)
            self.folder_labels[kind].set_full_text(path)
            self.result.hide()
            self.refresh()

    def refresh(self):
        idle = not self.window.busy
        for button in self.folder_buttons:
            button.setEnabled(idle)
        self.angle.setEnabled(idle)
        self.rotate_btn.setEnabled(idle and self.input_dir is not None and self.output_dir is not None)

    def start(self):
        if self.window.busy or self.input_dir is None or self.output_dir is None:
            return
        self.result.hide()
        self.window.set_busy(False, "Rotating images")
        worker = RotationWorker(self.input_dir, self.output_dir, self.angle.value())
        worker.progress.connect(self.window.on_progress)
        worker.done.connect(self.on_done)
        self.window.run_worker(worker)

    def on_done(self, saved, errors):
        message = f"Images saved: {len(saved)}. Files skipped: {len(errors)}."
        if not saved and not errors:
            message = "No images found directly in the input folder."
        self.result.setText(f"{message}\n{self.output_dir}")
        self.result.show()
        self.window.set_idle()
        self.window.warn(errors)
        if self.window.folder:
            self.window.rescan()
