from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
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
from pixelforge.ui.conversion_page import ConversionPage
from pixelforge.ui.metadata_page import MetadataPage
from pixelforge.ui.rotation_page import RotationPage
from pixelforge.ui.widgets import ElidedLabel, StatCard, StepBar, repolish
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
EMPTY, OVERVIEW, SETS = 0, 1, 2  # pages of the main stack


def make_tree(headers: list[str], fit_columns: range) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderLabels(headers)
    tree.setAlternatingRowColors(True)
    tree.setUniformRowHeights(True)
    tree.setIndentation(20)
    tree.setAnimated(True)
    head = tree.header()
    head.setStretchLastSection(False)
    head.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for col in fit_columns:
        head.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    return tree


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixelForge")
        self.resize(1280, 820)
        self.setMinimumSize(1040, 700)
        self.folder: Path | None = None
        self.files: list[Path] = []
        self.groups: list[DuplicateGroup] = []  # found, not yet moved
        self.pending: list[dict] = []  # moved, waiting for review
        self.nested = 0
        self.busy = False
        self.flash = ""  # one-off result message
        self.workers: list = []
        self.page = "home"

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(232)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(16, 30, 16, 20)
        nav.setSpacing(6)
        brand = QLabel("PixelForge")
        brand.setObjectName("brand")
        nav.addWidget(brand)
        tagline = QLabel("Your image tools")
        tagline.setProperty("role", "muted")
        nav.addWidget(tagline)
        nav.addSpacing(30)
        self.navigation = QButtonGroup(self)
        self.nav_buttons = {}
        pages = [
            ("home", "Home"),
            ("duplicates", "Duplicates"),
            ("gather", "Gather images"),
            ("metadata", "Remove metadata"),
            ("rotation", "Rotate images"),
            ("conversion", "Convert images"),
        ]
        for key, name in pages:
            button = self.button(name, lambda checked=False, p=key: self.show_page(p))
            button.setProperty("navigation", True)
            button.setCheckable(True)
            self.navigation.addButton(button)
            self.nav_buttons[key] = button
            nav.addWidget(button)
        nav.addStretch()
        local = QLabel("Images stay on your computer")
        local.setProperty("role", "muted")
        local.setWordWrap(True)
        nav.addWidget(local)
        shell.addWidget(sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(36, 30, 36, 28)
        content.setSpacing(20)
        shell.addLayout(content, 1)
        breadcrumb = QLabel("PixelForge  /  Image tools")
        breadcrumb.setProperty("role", "muted")
        content.addWidget(breadcrumb)
        self.page_title = QLabel("Home")
        self.page_title.setObjectName("title")
        content.addWidget(self.page_title)
        self.pages = QStackedWidget()
        content.addWidget(self.pages, 1)

        self.home_page = self.make_home()
        self.pages.addWidget(self.home_page)
        self.workspace = QWidget()
        self.pages.addWidget(self.workspace)
        outer = QVBoxLayout(self.workspace)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        self.workspace_description = QLabel()
        self.workspace_description.setProperty("role", "muted")
        self.workspace_description.setWordWrap(True)
        outer.addWidget(self.workspace_description)

        self.steps = StepBar()
        outer.addWidget(self.steps)

        # Folder card
        folder_card = QFrame()
        folder_card.setProperty("card", True)
        fl = QHBoxLayout(folder_card)
        fl.setContentsMargins(18, 14, 18, 14)
        fl.setSpacing(14)
        col = QVBoxLayout()
        col.setSpacing(0)
        cap = QLabel("Photo folder")
        cap.setProperty("role", "muted")
        self.folder_label = ElidedLabel("No folder selected")
        col.addWidget(cap)
        col.addWidget(self.folder_label)
        fl.addLayout(col, 1)
        self.subfolders = QCheckBox("Include subfolders")
        self.subfolders.setChecked(True)
        self.subfolders.toggled.connect(self.rescan)
        self.pick_btn = self.button("Choose folder…", self.choose_folder, "primary")
        fl.addWidget(self.subfolders)
        fl.addWidget(self.pick_btn)
        outer.addWidget(folder_card)

        # Stat cards
        self.stats = QFrame()
        self.stats.setProperty("card", True)
        stats = QHBoxLayout(self.stats)
        stats.setContentsMargins(0, 0, 0, 0)
        stats.setSpacing(12)
        self.card_images = StatCard("Images")
        self.card_nested = StatCard("In subfolders")
        self.card_sets = StatCard("Duplicate sets")
        self.card_extra = StatCard("Extra copies")
        for c in (self.card_images, self.card_nested, self.card_sets, self.card_extra):
            stats.addWidget(c, 1)
        outer.addWidget(self.stats)

        # Messages
        self.flash_label = QLabel()
        self.flash_label.setObjectName("flash")
        self.flash_label.setWordWrap(True)
        self.flash_label.setVisible(False)
        outer.addWidget(self.flash_label)
        self.summary = QLabel()
        self.summary.setObjectName("summary")
        self.summary.setWordWrap(True)
        self.summary.setVisible(False)
        outer.addWidget(self.summary)

        self.gather_hint = QLabel()
        self.gather_hint.setWordWrap(True)
        self.gather_hint.setProperty("role", "muted")
        outer.addWidget(self.gather_hint)

        # Bar 1: normal workflow
        self.find_bar = QWidget()
        fb = QHBoxLayout(self.find_bar)
        fb.setContentsMargins(0, 0, 0, 0)
        fb.setSpacing(10)
        self.check_btn = self.button("Find duplicates", self.start_check)
        self.move_btn = self.button("Move sets…", self.start_move)
        self.gather_btn = self.button("Gather into main folder…", self.start_gather)
        self.remove_empty = QCheckBox("Remove empty folders afterwards")
        for w in (self.check_btn, self.move_btn):
            fb.addWidget(w)
        fb.addStretch()
        outer.addWidget(self.find_bar)

        self.gather_bar = QFrame()
        self.gather_bar.setProperty("card", True)
        gb = QVBoxLayout(self.gather_bar)
        gb.setContentsMargins(18, 16, 18, 16)
        gb.setSpacing(14)
        gb.addWidget(self.remove_empty)
        gb.addWidget(self.gather_btn, 0, Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(self.gather_bar)

        # Bar 2: review of moved sets
        self.review_bar = QWidget()
        rb = QHBoxLayout(self.review_bar)
        rb.setContentsMargins(0, 0, 0, 0)
        rb.setSpacing(10)
        self.keep_btn = self.button(
            "Keep selected copy…", self.start_keep_selected, "primary"
        )
        self.keep_all_btn = self.button(
            "Keep suggested in all sets…", self.start_keep_all
        )
        self.undo_btn = self.button("Undo all…", self.start_undo)
        self.open_btn = self.button("Open Duplicates folder", self.open_duplicates)
        for w in (self.keep_btn, self.keep_all_btn, self.undo_btn, self.open_btn):
            rb.addWidget(w)
        rb.addStretch()
        outer.addWidget(self.review_bar)

        self.progress_panel = QFrame()
        self.progress_panel.setProperty("card", True)
        progress_layout = QVBoxLayout(self.progress_panel)
        progress_layout.setContentsMargins(16, 12, 16, 12)
        progress_layout.setSpacing(8)
        self.progress_task = "Processing images"
        self.progress_label = QLabel()
        self.progress_label.setWordWrap(True)
        progress_layout.addWidget(self.progress_label)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        progress_layout.addWidget(self.progress)
        content.insertWidget(content.indexOf(self.pages), self.progress_panel)
        self.progress_panel.hide()

        # Main area: empty state / folder overview / duplicate sets
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title = QLabel()
        self.empty_title.setObjectName("emptyTitle")
        self.empty_text = QLabel()
        self.empty_text.setObjectName("emptyText")
        self.empty_text.setWordWrap(True)
        self.empty_text.setMaximumWidth(460)
        for lab in (self.empty_title, self.empty_text):
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            el.addWidget(lab)

        self.overview_tree = make_tree(["Folder", "Images", "Types"], range(1, 3))
        self.overview_tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.sets_tree = make_tree(
            ["File", "Resolution", "Size", "Date taken", "From folder", "Note"],
            range(1, 6),
        )
        self.sets_tree.itemSelectionChanged.connect(self.refresh)
        self.stack = QStackedWidget()
        self.stack.addWidget(empty)
        self.stack.addWidget(self.overview_tree)
        self.stack.addWidget(self.sets_tree)
        outer.addWidget(self.stack, 1)

        self.metadata_page = MetadataPage(self)
        self.pages.addWidget(self.metadata_page)
        self.rotation_page = RotationPage(self)
        self.pages.addWidget(self.rotation_page)
        self.conversion_page = ConversionPage(self)
        self.pages.addWidget(self.conversion_page)
        self.show_page("home")

    def make_home(self):
        home = QWidget()
        layout = QVBoxLayout(home)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        intro = QLabel("A few useful tools for your photo folders. Choose one to get started.")
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        layout.addWidget(intro)
        layout.addSpacing(16)
        for key, name, detail in (
            ("duplicates", "Duplicates", "Find identical images, compare copies and choose what to keep."),
            ("gather", "Gather images", "Bring images from subfolders into one main folder."),
            ("metadata", "Remove metadata", "Save an image without embedded camera, location or other details."),
            ("rotation", "Rotate images", "Rotate a folder of images by a chosen angle and save the results."),
            ("conversion", "Convert images", "Convert images to JPG, PNG, WebP, BMP, TIFF or GIF."),
        ):
            row = self.button("", lambda checked=False, p=key: self.show_page(p))
            row.setProperty("toolRow", True)
            row.setMinimumHeight(92)
            row.setAccessibleName(name)
            row.setAccessibleDescription(detail)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(22, 18, 22, 18)
            row_layout.setSpacing(18)
            text = QVBoxLayout()
            text.setSpacing(4)
            heading = QLabel(name)
            heading.setProperty("role", "toolTitle")
            description = QLabel(detail)
            description.setWordWrap(True)
            description.setProperty("role", "muted")
            text.addWidget(heading)
            text.addWidget(description)
            row_layout.addLayout(text, 1)
            arrow = QLabel("›")
            arrow.setProperty("role", "chevron")
            row_layout.addWidget(arrow)
            for label in (heading, description, arrow):
                label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(row)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(home)
        home.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    def show_page(self, page: str):
        self.page = page
        titles = {
            "home": "Home", "duplicates": "Duplicates",
            "gather": "Gather images", "metadata": "Remove metadata",
            "rotation": "Rotate images",
            "conversion": "Convert images",
        }
        self.page_title.setText(titles[page])
        self.nav_buttons[page].setChecked(True)
        self.nav_buttons[page].setFocus(Qt.FocusReason.OtherFocusReason)
        pages = {
            "home": self.home_page, "metadata": self.metadata_page,
            "rotation": self.rotation_page, "conversion": self.conversion_page,
        }
        self.pages.setCurrentWidget(pages.get(page, self.workspace))
        self.refresh()

    # ---- small helpers --------------------------------------------------
    def button(self, text: str, slot, variant: str = "secondary") -> QPushButton:
        b = QPushButton(text)
        b.setProperty("variant", variant)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    @staticmethod
    def set_variant(btn: QPushButton, variant: str):
        if btn.property("variant") != variant:
            btn.setProperty("variant", variant)
            repolish(btn)

    def set_summary(self, text: str):
        self.summary.setText(text)
        self.summary.setVisible(bool(text))

    def show_flash(self, text: str):
        self.flash_label.setText(text)
        self.flash_label.setVisible(bool(text))

    # ---- UI state -------------------------------------------------------
    def refresh(self):
        reviewing = bool(self.pending)
        duplicates = self.page == "duplicates"
        gather = self.page == "gather"
        ok = not self.busy
        step = 3 if reviewing else 2 if self.groups else 1 if self.files else 0
        self.steps.set_current(step)

        self.steps.setVisible(duplicates)
        self.find_bar.setVisible(duplicates and not reviewing)
        self.review_bar.setVisible(duplicates and reviewing)
        self.gather_bar.setVisible(gather)
        self.gather_hint.setVisible(gather)
        self.summary.setVisible(duplicates and bool(self.summary.text()))
        self.card_sets.setVisible(duplicates)
        self.card_extra.setVisible(duplicates)
        self.workspace_description.setText(
            "Find exact duplicates and review each set before choosing a copy to keep."
            if duplicates else "Move images from subfolders into one place."
        )
        self.gather_hint.setText(
            "Finish reviewing or undo the pending duplicate sets in Duplicates before gathering images."
            if reviewing else "Images in subfolders will move into the chosen folder. Duplicate filenames get a numbered suffix."
        )
        self.pick_btn.setEnabled(ok)
        self.subfolders.setEnabled(ok)
        self.remove_empty.setEnabled(ok)
        self.check_btn.setEnabled(ok and bool(self.files))
        self.move_btn.setEnabled(ok and bool(self.groups))
        self.gather_btn.setEnabled(ok and self.nested > 0 and not reviewing)
        self.metadata_page.refresh()
        self.rotation_page.refresh()
        self.conversion_page.refresh()
        self.keep_btn.setEnabled(ok and bool(self.sets_tree.selectedItems()))
        for b in (self.keep_all_btn, self.undo_btn, self.open_btn):
            b.setEnabled(ok)
        # The next sensible action gets the accent colour.
        self.set_variant(self.pick_btn, "primary" if step == 0 else "secondary")
        self.set_variant(self.check_btn, "primary" if step == 1 else "secondary")
        self.set_variant(self.move_btn, "primary" if step == 2 else "secondary")

        self.update_stats(reviewing)
        if not self.files and not self.pending:
            if not self.folder:
                self.empty_title.setText("Choose a folder to get started")
                self.empty_text.setText(
                    "Choose the photo folder you want to work with. You can include its subfolders too."
                )
            elif self.busy:
                self.empty_title.setText("Scanning…")
                self.empty_text.setText("")
            else:
                self.empty_title.setText("No images found")
                self.empty_text.setText(
                    "Try including subfolders, or choose a different folder."
                )
            self.stack.setCurrentIndex(EMPTY)
        else:
            self.stack.setCurrentIndex(
                SETS if duplicates and (self.pending or self.groups) else OVERVIEW
            )

    def update_stats(self, reviewing: bool):
        if self.folder:
            self.card_images.set_value(
                "…" if self.busy and not self.files else str(len(self.files))
            )
            self.card_nested.set_value(str(self.nested))
        else:
            self.card_images.set_value("–")
            self.card_nested.set_value("–")
        sets = (
            [len(s["files"]) for s in self.pending]
            if reviewing
            else [len(g.files) for g in self.groups]
        )
        if sets:
            self.card_sets.set_value(
                str(len(sets)), "Sets to review" if reviewing else "Duplicate sets"
            )
            self.card_extra.set_value(str(sum(n - 1 for n in sets)))
        else:
            self.card_sets.set_value("–", "Duplicate sets")
            self.card_extra.set_value("–")

    def set_busy(self, indeterminate: bool, task: str = "Processing images"):
        self.busy = True
        self.show_flash("")
        self.progress_task = task
        self.progress_label.setText(f"{task}…" if indeterminate else f"{task}… 0%")
        self.progress_panel.show()
        (
            self.progress.setRange(0, 0)
            if indeterminate
            else self.progress.setRange(0, 100)
        )
        if not indeterminate:
            self.progress.setValue(0)
        self.refresh()

    def set_idle(self, success: bool = True):
        self.busy = False
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        if success:
            self.progress.setValue(self.progress.maximum())
        self.progress_label.setText(
            f"{self.progress_task}: complete (100%)" if success else f"{self.progress_task}: stopped"
        )
        self.refresh()

    def run_worker(self, worker):
        self.workers.append(worker)
        worker.finished.connect(lambda w=worker: self.workers.remove(w))
        worker.failed.connect(self.on_failed)
        worker.start()

    def on_failed(self, message: str):
        QMessageBox.critical(self, "Something went wrong", message)
        self.set_idle(success=False)

    def on_progress(self, done: int, total: int):
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        percent = done * 100 // max(total, 1)
        self.progress_label.setText(f"{self.progress_task}… {done} of {total} ({percent}%)")

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
            self.folder_label.set_full_text(str(self.folder))
            self.rescan()

    def rescan(self):
        if not self.folder:
            return
        self.files, self.groups, self.pending, self.nested = [], [], [], 0
        self.set_summary("")
        self.set_busy(True, "Scanning folder")
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
                f"{len(pending)} duplicate sets ({n} files) are waiting in the Duplicates folder. "
                "For each set, choose the copy to keep: it goes back to its original folder and "
                "the others go to the Recycle Bin. Or undo everything."
            )
        elif files:
            parts = "  ·  ".join(
                f"{k.upper()} {v}" for k, v in count_by_type(files).items()
            )
            text = f"{parts}.  Click “Find duplicates” to continue."
        else:
            text = ""
        self.set_summary(text)
        self.show_flash(self.flash)
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
            item.setTextAlignment(
                1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            items[folder] = item
            item.setExpanded(True)

    # ---- Step 3: find duplicates ----------------------------------------
    def start_check(self):
        self.groups = []
        self.set_summary("Looking for duplicates…")
        self.set_busy(False, "Finding duplicates")
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
            self.set_summary(
                f"Found {len(groups)} sets of duplicates ({n} files, {size}). Click “Move sets…” "
                "to move every copy of each set into its own folder inside Duplicates, "
                "where you can compare them and choose which to keep."
            )
        else:
            self.set_summary("No duplicates found.")
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
        self.set_busy(False, "Moving duplicate sets")
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
        self.set_busy(False, "Reviewing duplicate sets")
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
        self.set_busy(False, "Restoring images")
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
        self.set_busy(False, "Gathering images")
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
        accent = QBrush(self.palette().color(QPalette.ColorRole.Highlight))
        for set_name, rows in sets:
            top = QTreeWidgetItem(
                tree, [f"{set_name}  ·  {len(rows)} identical copies"]
            )
            top.setFirstColumnSpanned(True)
            top.setData(0, ROLE, (set_name, None))
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
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
                if suggested:
                    item.setForeground(5, accent)
        if len(sets) <= 200:
            tree.expandAll()

    def closeEvent(self, event):
        for w in list(self.workers):
            w.wait()
        super().closeEvent(event)
