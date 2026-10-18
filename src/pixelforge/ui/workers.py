from pathlib import Path

from PySide6.QtCore import QThread, Signal

from pixelforge.core import conversion, duplicates, metadata, organizer, review, rotation, scanner


class Worker(QThread):
    """Runs work() off the UI thread; any error is reported through `failed`."""

    progress = Signal(int, int)
    failed = Signal(str)

    def run(self):
        try:
            self.work()
        except Exception as e:
            self.failed.emit(str(e))

    def work(self):
        raise NotImplementedError


class ScanWorker(Worker):
    done = Signal(list, list)  # files, pending duplicate sets

    def __init__(self, folder: Path, recursive: bool):
        super().__init__()
        self.folder, self.recursive = folder, recursive

    def work(self):
        files = scanner.scan_folder(self.folder, self.recursive)
        self.done.emit(files, review.pending_sets(self.folder))


class FindWorker(Worker):
    done = Signal(list)

    def __init__(self, files: list):
        super().__init__()
        self.files = files

    def work(self):
        self.done.emit(duplicates.find_duplicates(self.files, self.progress.emit))


class MoveWorker(Worker):
    done = Signal(int, list)  # files moved, errors

    def __init__(self, groups: list, root: Path):
        super().__init__()
        self.groups, self.root = groups, root

    def work(self):
        moved, errors = duplicates.move_sets(self.groups, self.root, self.progress.emit)
        self.done.emit(moved, errors)


class ResolveWorker(Worker):
    done = Signal(int, int, list)  # kept, trashed, errors

    def __init__(self, root: Path, choices: dict):
        super().__init__()
        self.root, self.choices = root, choices

    def work(self):
        kept, trashed, errors = review.resolve_sets(
            self.root, self.choices, self.progress.emit
        )
        self.done.emit(kept, trashed, errors)


class UndoWorker(Worker):
    done = Signal(int, list)  # restored, errors

    def __init__(self, root: Path):
        super().__init__()
        self.root = root

    def work(self):
        restored, errors = review.undo_all(self.root, self.progress.emit)
        self.done.emit(restored, errors)


class GatherWorker(Worker):
    done = Signal(list, list, int)  # moved, errors, removed folders

    def __init__(self, files: list, root: Path, remove_empty: bool):
        super().__init__()
        self.files, self.root, self.remove_empty = files, root, remove_empty

    def work(self):
        moved, errors, removed = organizer.gather_files(
            self.files, self.root, self.progress.emit, self.remove_empty
        )
        self.done.emit(moved, errors, removed)


class MetadataWorker(Worker):
    done = Signal(str)

    def __init__(self, source: Path, destination: Path, overwrite: bool):
        super().__init__()
        self.source, self.destination, self.overwrite = source, destination, overwrite

    def work(self):
        result = metadata.remove_metadata(self.source, self.destination, self.overwrite)
        self.done.emit(str(result))


class RotationWorker(Worker):
    done = Signal(list, list)

    def __init__(self, input_dir: Path, output_dir: Path, angle: float):
        super().__init__()
        self.input_dir, self.output_dir, self.angle = input_dir, output_dir, angle

    def work(self):
        saved, errors = rotation.rotate_images(
            self.input_dir, self.output_dir, self.angle, self.progress.emit
        )
        self.done.emit(saved, errors)


class ConversionScanWorker(Worker):
    done = Signal(list)

    def __init__(self, directory: Path, output_format: str, recursive: bool):
        super().__init__()
        self.directory, self.output_format, self.recursive = directory, output_format, recursive

    def work(self):
        self.done.emit(conversion.files_to_convert(self.directory, self.output_format, self.recursive))


class ConversionWorker(Worker):
    done = Signal(list, int, list)

    def __init__(self, files: list, directory: Path, output_format: str, delete_originals: bool):
        super().__init__()
        self.files, self.directory = files, directory
        self.output_format, self.delete_originals = output_format, delete_originals

    def work(self):
        saved, recycled, errors = conversion.convert_images(
            self.files, self.directory, self.output_format, self.delete_originals, self.progress.emit
        )
        self.done.emit(saved, recycled, errors)
