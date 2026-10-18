import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image
from PySide6.QtGui import QFontInfo
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton

from pixelforge.ui.main_window import MainWindow
from pixelforge.ui.theme import apply_theme, load_fonts


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        load_fonts(cls.app)
        apply_theme(cls.app, dark=False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.window = MainWindow()
        self.window.show()
        self.addCleanup(self.window.close)
        self.app.processEvents()

    def wait_idle(self):
        deadline = time.monotonic() + 10
        while self.window.busy or self.window.workers:
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("Background work did not finish")
            time.sleep(0.005)
        self.app.processEvents()

    def scan_fixture(self):
        nested = self.root / "Holiday"
        nested.mkdir()
        Image.new("RGB", (20, 16), "red").save(self.root / "photo.png")
        shutil.copyfile(self.root / "photo.png", nested / "copy.png")
        Image.new("RGB", (12, 10), "blue").save(nested / "unique.png")
        self.window.folder = self.root
        self.window.folder_label.set_full_text(str(self.root))
        self.window.rescan()
        self.wait_idle()

    def test_navigation_and_font(self):
        self.assertEqual(QFontInfo(self.app.font()).family(), "Poppins")
        self.assertEqual(self.window.page, "home")
        rows = self.window.home_page.findChildren(QPushButton)
        rows[0].click()
        self.assertEqual(self.window.page, "duplicates")
        self.assertTrue(self.window.find_bar.isVisible())
        self.assertFalse(self.window.gather_bar.isVisible())
        self.window.nav_buttons["gather"].click()
        self.assertTrue(self.window.gather_bar.isVisible())
        self.assertFalse(self.window.find_bar.isVisible())
        self.window.nav_buttons["metadata"].click()
        self.assertTrue(self.window.metadata_page.isVisible())

    def test_empty_state_text_fits_without_overlapping(self):
        self.addCleanup(lambda: apply_theme(self.app, dark=False))
        for dark in (False, True):
            apply_theme(self.app, dark=dark)
            for width, height in ((1280, 820), (1040, 700)):
                self.window.resize(width, height)
                for page in ("duplicates", "gather"):
                    with self.subTest(dark=dark, size=(width, height), page=page):
                        self.window.show_page(page)
                        self.app.processEvents()
                        title, text = self.window.empty_title, self.window.empty_text
                        self.assertGreaterEqual(text.height(), text.heightForWidth(text.width()))
                        self.assertLess(title.geometry().bottom(), text.geometry().top())

    def test_duplicate_move_restart_review_and_undo(self):
        self.scan_fixture()
        self.window.show_page("duplicates")
        self.window.start_check()
        self.wait_idle()
        self.assertEqual(len(self.window.groups), 1)
        self.window.show_page("gather")
        self.window.show_page("duplicates")
        self.assertEqual(len(self.window.groups), 1)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.window.start_move()
            self.wait_idle()
            self.assertEqual(len(self.window.pending), 1)
            self.assertTrue(self.window.review_bar.isVisible())
            # Disk state restores review even in a fresh window.
            resumed = MainWindow()
            self.addCleanup(resumed.close)
            resumed.folder = self.root
            resumed.rescan()
            deadline = time.monotonic() + 10
            while resumed.busy or resumed.workers:
                self.app.processEvents()
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.005)
            self.assertEqual(len(resumed.pending), 1)
            self.window.start_undo()
            self.wait_idle()
        self.assertTrue((self.root / "photo.png").exists())
        self.assertTrue((self.root / "Holiday" / "copy.png").exists())
        self.assertFalse(self.window.pending)

    def test_keep_selected_and_gather(self):
        self.scan_fixture()
        self.window.show_page("duplicates")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.window.start_check()
            self.wait_idle()
            self.window.start_move()
            self.wait_idle()
            selected = self.window.sets_tree.topLevelItem(0).child(1)
            self.window.sets_tree.setCurrentItem(selected)
            expected = Path(self.window.pending[0]["files"][1]["original"])
            discarded = []
            with patch("pixelforge.core.review.send2trash", side_effect=lambda path: (discarded.append(path), Path(path).unlink())):
                self.window.start_keep_selected()
                self.wait_idle()
            self.assertTrue(expected.exists())
            self.assertEqual(len(discarded), 1)
            self.window.show_page("gather")
            self.window.start_gather()
            self.wait_idle()
        self.assertEqual(self.window.nested, 0)
        self.assertTrue((self.root / "unique.png").exists())

    def test_metadata_save_as_and_overwrite_cancel(self):
        source = self.root / "photo.png"
        exif = Image.Exif()
        exif[271] = "Private camera"
        Image.new("RGB", (4, 4), "red").save(source, exif=exif)
        before = source.read_bytes()
        output = self.root / "clean.png"
        self.window.show_page("metadata")
        page = self.window.metadata_page
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(source), "")):
            page.choose_image()
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "")):
            page.start()
            self.wait_idle()
        self.assertTrue(output.exists())
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue(page.result.isVisible())
        with Image.open(output) as clean:
            self.assertFalse(clean.getexif())
        page.overwrite.setChecked(True)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            page.start()
        self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
