from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelforge.core.duplicates import DuplicateGroup, human_size
from pixelforge.core.log import duplicates_dir
from pixelforge.core.organizer import files_to_gather
from pixelforge.core.scanner import count_by_type, folder_stats
from pixelforge.ui.workers import (
    FindWorker,
    GatherWorker,
    MoveWorker,
    ResolveWorker,
    ScanWorker,
    UndoWorker,
)

ROLE = Qt.ItemDataRole.UserRole
YES = QMessageBox.StandardButton.Yes


def make_tree(headers: list[str]) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderLabels(headers)
    tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    return tree


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixelForge")
        self.resize(1000, 700)
        self.folder: Path | None = None
        self.files: list[Path] = []
        self.groups: list[DuplicateGroup] = []  # found, not yet moved
        self.pending: list[dict] = []  # moved, waiting for review
        self.nested = 0
        self.busy = False
        self.flash = ""  # one-off result message
        self.workers: list = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        self.pick_btn = QPushButton("Choose folder…")
        self.pick_btn.clicked.connect(self.choose_folder)
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        top.addWidget(self.pick_btn)
        top.addWidget(self.folder_label, 1)
        root.addLayout(top)

        self.subfolders = QCheckBox("Include subfolders")
        self.subfolders.setChecked(True)
        self.subfolders.toggled.connect(self.rescan)
        root.addWidget(self.subfolders)

        self.summary = QLabel("Choose a folder to begin.")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        # Bar 1: normal workflow
        self.find_bar = QWidget()
        fl = QHBoxLayout(self.find_bar)
        fl.setContentsMargins(0, 0, 0, 0)
        self.check_btn = QPushButton("Find duplicates")
        self.check_btn.clicked.connect(self.start_check)
        self.move_btn = QPushButton("Move sets…")
        self.move_btn.clicked.connect(self.start_move)
        self.gather_btn = QPushButton("Gather into main folder…")
        self.gather_btn.clicked.connect(self.start_gather)
        self.remove_empty = QCheckBox("Remove empty folders afterwards")
        for w in (self.check_btn, self.move_btn, self.gather_btn):
            fl.addWidget(w)
        fl.addStretch()
        fl.addWidget(self.remove_empty)
        root.addWidget(self.find_bar)

        # Bar 2: review of moved sets
        self.review_bar = QWidget()
        rl = QHBoxLayout(self.review_bar)
        rl.setContentsMargins(0, 0, 0, 0)
        self.keep_btn = QPushButton("Keep selected copy…")
        self.keep_btn.clicked.connect(self.start_keep_selected)
        self.keep_all_btn = QPushButton("Keep suggested in all sets…")
        self.keep_all_btn.clicked.connect(self.start_keep_all)
        self.undo_btn = QPushButton("Undo all…")
        self.undo_btn.clicked.connect(self.start_undo)
        self.open_btn = QPushButton("Open Duplicates folder")
        self.open_btn.clicked.connect(self.open_duplicates)
        for w in (self.keep_btn, self.keep_all_btn, self.undo_btn, self.open_btn):
            rl.addWidget(w)
        rl.addStretch()
        root.addWidget(self.review_bar)

        self.progress = QProgressBar()
        root.addWidget(self.progress)

        self.overview_tree = make_tree(["Folder", "Images", "Types"])
        self.sets_tree = make_tree(
            ["File", "Resolution", "Size", "Date taken", "From folder", "Note"]
        )
        self.sets_tree.itemSelectionChanged.connect(self.refresh)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.overview_tree)
        self.stack.addWidget(self.sets_tree)
        root.addWidget(self.stack, 1)

        self.refresh()

    # ---- UI state -------------------------------------------------------
    def refresh(self):
        reviewing = bool(self.pending)
        self.find_bar.setVisible(not reviewing)
        self.review_bar.setVisible(reviewing)
        self.progress.setVisible(self.busy)
        ok = not self.busy
        self.pick_btn.setEnabled(ok)
        self.check_btn.setEnabled(ok and bool(self.files))
        self.move_btn.setEnabled(ok and bool(self.groups))
        self.gather_btn.setEnabled(ok and self.nested > 0)
        self.keep_btn.setEnabled(ok and bool(self.sets_tree.selectedItems()))
        for b in (self.keep_all_btn, self.undo_btn, self.open_btn):
            b.setEnabled(ok)
        self.stack.setCurrentWidget(
            self.sets_tree if (self.pending or self.groups) else self.overview_tree
        )

    def set_busy(self, indeterminate: bool):
        self.busy = True
        (
            self.progress.setRange(0, 0)
            if indeterminate
            else self.progress.setRange(0, 100)
        )
        if not indeterminate:
            self.progress.setValue(0)
        self.refresh()

    def set_idle(self):
        self.busy = False
        self.refresh()

    def run_worker(self, worker):
        self.workers.append(worker)
        worker.finished.connect(lambda w=worker: self.workers.remove(w))
        worker.failed.connect(self.on_failed)
        worker.start()

    def on_failed(self, message: str):
        QMessageBox.critical(self, "Something went wrong", message)
        self.set_idle()

    def on_progress(self, done: int, total: int):
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)

    def warn(self, errors: list):
        if errors:
            QMessageBox.warning(
                self,
                "Some files were skipped",
                f"{len(errors)} problems. First one:\n{errors[0]}",
            )

    def rel_folder(self, path: Path) -> str:
        try:
            rel = str(path.relative_to(self.folder))
        except ValueError:
            return str(path)
        return "(main folder)" if rel == "." else rel

    # ---- Step 1 + 2: choose folder, overview ----------------------------
    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select photo folder")
        if path:
            self.folder = Path(path)
            self.folder_label.setText(str(self.folder))
            self.rescan()

    def rescan(self):
        if not self.folder:
            return
        self.files, self.groups, self.pending, self.nested = [], [], [], 0
        self.summary.setText("Scanning folder…")
        self.set_busy(True)
        w = ScanWorker(self.folder, self.subfolders.isChecked())
        w.done.connect(self.on_scanned)
        self.run_worker(w)

    def on_scanned(self, files: list, pending: list):
        self.files, self.pending = files, pending
        self.nested = len(files_to_gather(files, self.folder))
        self.populate_overview()
        if pending:
            self.fill_sets(self.review_sets())
            n = sum(len(s["files"]) for s in pending)
            text = (
                f"{len(pending)} duplicate sets ({n} files) are waiting in the Duplicates folder.\n"
                "For each set, choose the copy to keep: it goes back to its original folder and "
                "the others go to the Recycle Bin. Or undo everything."
            )
        elif files:
            parts = "  ·  ".join(
                f"{k.upper()}: {v}" for k, v in count_by_type(files).items()
            )
            text = (
                f"Found {len(files)} images — {parts}\n{self.nested} are inside subfolders.\n"
                "Click “Find duplicates” to continue."
            )
        else:
            text = "No images found in this folder."
        self.summary.setText((self.flash + "\n\n" if self.flash else "") + text)
        self.flash = ""
        self.set_idle()

    def populate_overview(self):
        tree = self.overview_tree
        tree.clear()
        items = {}
        stats = folder_stats(self.files, self.folder)
        for folder in sorted(stats, key=lambda p: (len(p.parts), str(p).lower())):
            counts = stats[folder]
            is_root = folder == self.folder
            label = (folder.name or str(folder)) + (" (main folder)" if is_root else "")
            parent = items.get(folder.parent) if not is_root else None
            item = QTreeWidgetItem(
                parent if parent is not None else tree,
                [
                    label,
                    str(sum(counts.values())),
                    "  ·  ".join(f"{k.upper()} {v}" for k, v in counts.items()),
                ],
            )
            items[folder] = item
            item.setExpanded(True)

    # ---- Step 3: find duplicates ----------------------------------------
    def start_check(self):
        self.groups = []
        self.summary.setText("Looking for duplicates…")
        self.set_busy(False)
        w = FindWorker(self.files)
        w.progress.connect(self.on_progress)
        w.done.connect(self.on_found)
        self.run_worker(w)

    def on_found(self, groups: list):
        self.groups = groups
        if groups:
            self.fill_sets(self.found_sets())
            n = sum(len(g.files) for g in groups)
            size = human_size(sum(i.size_bytes for g in groups for i in g.files))
            self.summary.setText(
                f"Found {len(groups)} sets of duplicates — {n} files ({size}).\n"
                "Click “Move sets…” to move every copy of each set into its own folder "
                "inside Duplicates, where you can compare them and choose which to keep."
            )
        else:
            self.summary.setText("No duplicates found.")
        self.set_idle()

    # ---- Step 4: move sets ----------------------------------------------
    def start_move(self):
        n = sum(len(g.files) for g in self.groups)
        answer = QMessageBox.question(
            self,
            "Move sets",
            f"Move all {n} files of these {len(self.groups)} sets into:\n"
            f"{duplicates_dir(self.folder)}\n\n"
            "Each set gets its own folder. Files are moved, not copied, and nothing is deleted. "
            "Next you choose which copy to keep in each set, or you can undo everything.",
        )
        if answer != YES:
            return
        self.set_busy(False)
        w = MoveWorker(self.groups, self.folder)
        w.progress.connect(self.on_progress)
        w.done.connect(self.on_moved)
        self.run_worker(w)

    def on_moved(self, moved: int, errors: list):
        self.flash = f"Moved {moved} files into {len(self.groups)} sets."
        self.warn(errors)
        self.rescan()

    # ---- Step 5: review (keep one / undo) -------------------------------
    def start_keep_selected(self):
        items = self.sets_tree.selectedItems()
        if not items:
            return
        set_name, path = items[0].data(0, ROLE)
        s = next((x for x in self.pending if x["name"] == set_name), None)
        if s is None:
            return
        which = "the selected copy" if path else "the suggested copy"
        answer = QMessageBox.question(
            self,
            "Keep one copy",
            f"Keep {which} of {set_name}? It goes back to its original folder.\n"
            f"The other {len(s['files']) - 1} copies are sent to the Recycle Bin.",
        )
        if answer == YES:
            self.run_resolve({set_name: path})

    def start_keep_all(self):
        extra = sum(len(s["files"]) - 1 for s in self.pending)
        answer = QMessageBox.question(
            self,
            "Keep suggested in all sets",
            f"For all {len(self.pending)} sets, return the suggested copy to its original "
            f"folder and send the other {extra} files to the Recycle Bin?\n\n"
            "Tip: select a different copy in any set first and use “Keep selected copy…” "
            "if you want to choose yourself.",
        )
        if answer == YES:
            self.run_resolve({s["name"]: None for s in self.pending})

    def run_resolve(self, choices: dict):
        self.set_busy(False)
        w = ResolveWorker(self.folder, choices)
        w.progress.connect(self.on_progress)
        w.done.connect(self.on_resolved)
        self.run_worker(w)

    def on_resolved(self, kept: int, trashed: int, errors: list):
        self.flash = f"Kept {kept} images, sent {trashed} to the Recycle Bin."
        self.warn(errors)
        self.rescan()

    def start_undo(self):
        n = sum(len(s["files"]) for s in self.pending)
        answer = QMessageBox.question(
            self, "Undo all", f"Put all {n} files back in the folders they came from?"
        )
        if answer != YES:
            return
        self.set_busy(False)
        w = UndoWorker(self.folder)
        w.progress.connect(self.on_progress)
        w.done.connect(self.on_undone)
        self.run_worker(w)

    def on_undone(self, restored: int, errors: list):
        self.flash = f"Restored {restored} files to their original folders."
        self.warn(errors)
        self.rescan()

    def open_duplicates(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(duplicates_dir(self.folder))))

    # ---- Gather (separate tool) -----------------------------------------
    def start_gather(self):
        extra = (
            "\nEmpty folders will then be removed."
            if self.remove_empty.isChecked()
            else ""
        )
        answer = QMessageBox.question(
            self,
            "Gather images",
            f"Move {self.nested} images from subfolders into:\n{self.folder}\n\n"
            f"Files with the same name get _1, _2 added. Nothing is overwritten or deleted.{extra}",
        )
        if answer != YES:
            return
        self.groups = []
        self.set_busy(False)
        w = GatherWorker(self.files, self.folder, self.remove_empty.isChecked())
        w.progress.connect(self.on_progress)
        w.done.connect(self.on_gathered)
        self.run_worker(w)

    def on_gathered(self, moved: list, errors: list, removed: int):
        self.flash = f"Moved {len(moved)} images into the main folder."
        if removed:
            self.flash += f" Removed {removed} empty folders."
        self.warn(errors)
        self.rescan()

    # ---- Sets tree (shared by "found" preview and "review") -------------
    def found_sets(self):
        out = []
        for n, g in enumerate(self.groups, 1):
            rows = [
                (
                    str(i.path),
                    i.path.name,
                    f"{i.width} × {i.height}" if i.width else "unknown",
                    human_size(i.size_bytes),
                    f"{i.taken:%Y-%m-%d %H:%M}",
                    self.rel_folder(i.path.parent),
                    k == 0,
                )
                for k, i in enumerate(g.files)
            ]
            out.append((f"Set {n}", rows))
        return out

    def review_sets(self):
        out = []
        for s in self.pending:
            rows = []
            for k, f in enumerate(s["files"]):
                taken = datetime.fromisoformat(f["taken"])
                rows.append(
                    (
                        f["moved_to"],
                        Path(f["moved_to"]).name,
                        f"{f['width']} × {f['height']}" if f["width"] else "unknown",
                        human_size(f["size_bytes"]),
                        f"{taken:%Y-%m-%d %H:%M}",
                        self.rel_folder(Path(f["original"]).parent),
                        k == 0,
                    )
                )
            out.append((s["name"], rows))
        return out

    def fill_sets(self, sets: list):
        tree = self.sets_tree
        tree.clear()
        for set_name, rows in sets:
            top = QTreeWidgetItem(tree, [f"{set_name} — {len(rows)} identical copies"])
            top.setFirstColumnSpanned(True)
            top.setData(0, ROLE, (set_name, None))
            for key, name, res, size, date, folder, suggested in rows:
                item = QTreeWidgetItem(
                    top,
                    [
                        name,
                        res,
                        size,
                        date,
                        folder,
                        "Suggested to keep" if suggested else "",
                    ],
                )
                item.setData(0, ROLE, (set_name, key))
                item.setToolTip(0, key)
        if len(sets) <= 200:
            tree.expandAll()

    def closeEvent(self, event):
        for w in list(self.workers):
            w.wait()
        super().closeEvent(event)
