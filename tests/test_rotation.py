import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import imageio.v2 as imageio
import numpy as np
from scipy import ndimage
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pixelforge.core.rotation import rotate_images


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input_dir = self.root / "input"
        self.input_dir.mkdir()
        self.output_dir = self.root / "output"
        self.pixels = np.arange(8 * 12 * 3, dtype=np.uint8).reshape(8, 12, 3)
        self.source = self.input_dir / "photo.png"
        imageio.imwrite(self.source, self.pixels)

    def test_pixels_match_original_scipy_algorithm(self):
        original = self.source.read_bytes()
        for angle in (45, 90, -45):
            with self.subTest(angle=angle):
                output = self.output_dir / str(angle)
                saved, errors = rotate_images(self.input_dir, output, angle)
                self.assertFalse(errors)
                self.assertEqual(saved, [output / "rotated_photo.png"])
                np.testing.assert_array_equal(imageio.imread(saved[0]), ndimage.rotate(self.pixels, angle))
        self.assertEqual(self.source.read_bytes(), original)

    def test_default_angle_progress_and_log(self):
        updates = []
        saved, errors = rotate_images(self.input_dir, self.output_dir, progress=lambda *args: updates.append(args))
        self.assertFalse(errors)
        np.testing.assert_array_equal(imageio.imread(saved[0]), ndimage.rotate(self.pixels, 45))
        self.assertEqual(updates, [(1, 1)])
        log = (self.output_dir / "rotation.log").read_text(encoding="utf-8")
        self.assertIn("45 degrees", log)
        self.assertIn("Rotated and saved:", log)
        self.assertIn("Finished rotating images", log)

    def test_supported_still_formats_can_be_saved(self):
        for suffix in (".jpg", ".bmp", ".gif", ".tif", ".webp"):
            imageio.imwrite(self.input_dir / f"photo{suffix}", self.pixels)
        originals = {path: path.read_bytes() for path in self.input_dir.iterdir()}
        saved, errors = rotate_images(self.input_dir, self.output_dir)
        self.assertFalse(errors)
        self.assertEqual(len(saved), len(originals))
        for source, original in originals.items():
            expected = ndimage.rotate(imageio.imread(source), 45)
            result = imageio.imread(self.output_dir / f"rotated_{source.name}")
            self.assertEqual(result.shape[:2], expected.shape[:2])
            self.assertEqual(source.read_bytes(), original)

    def test_bad_file_does_not_stop_batch_and_subfolders_are_excluded(self):
        (self.input_dir / "bad.png").write_bytes(b"not an image")
        (self.input_dir / "notes.txt").write_text("not an image", encoding="utf-8")
        nested = self.input_dir / "nested"
        nested.mkdir()
        imageio.imwrite(nested / "nested.png", self.pixels)
        saved, errors = rotate_images(self.input_dir, self.output_dir)
        self.assertEqual(len(saved), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("bad.png", errors[0])
        self.assertFalse((self.output_dir / "rotated_nested.png").exists())
        self.assertIn("bad.png", (self.output_dir / "rotation.log").read_text(encoding="utf-8"))

    def test_existing_output_never_overwritten(self):
        self.output_dir.mkdir()
        target = self.output_dir / "rotated_photo.png"
        target.write_bytes(b"keep this file")
        saved, errors = rotate_images(self.input_dir, self.output_dir)
        self.assertFalse(saved)
        self.assertEqual(len(errors), 1)
        self.assertEqual(target.read_bytes(), b"keep this file")

    def test_failed_write_removes_partial_output_and_preserves_input(self):
        original = self.source.read_bytes()

        def fail_write(output, *args, **kwargs):
            output.write(b"partial output")
            raise OSError("disk full")

        with patch("pixelforge.core.rotation.imageio.imwrite", side_effect=fail_write):
            saved, errors = rotate_images(self.input_dir, self.output_dir)
        self.assertFalse(saved)
        self.assertIn("disk full", errors[0])
        self.assertFalse((self.output_dir / "rotated_photo.png").exists())
        self.assertEqual(self.source.read_bytes(), original)

    def test_same_folder_does_not_process_new_outputs_or_change_input(self):
        original = self.source.read_bytes()
        saved, errors = rotate_images(self.input_dir, self.input_dir)
        self.assertEqual(len(saved), 1)
        self.assertFalse(errors)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertFalse((self.input_dir / "rotated_rotated_photo.png").exists())

    def test_invalid_input_and_nonfinite_angle(self):
        with self.assertRaises(ValueError):
            rotate_images(self.root / "missing", self.output_dir)
        for angle in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(angle=angle), self.assertRaises(ValueError):
                rotate_images(self.input_dir, self.output_dir, angle)
        self.assertFalse(self.output_dir.exists())

    def test_multiframe_images_are_skipped_without_dropping_frames(self):
        source = self.input_dir / "animated.gif"
        Image.new("RGB", (4, 4), "red").save(
            source, save_all=True, append_images=[Image.new("RGB", (4, 4), "blue")], duration=100, loop=0
        )
        original = source.read_bytes()
        saved, errors = rotate_images(self.input_dir, self.output_dir)
        self.assertEqual(len(saved), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Animated and multi-page", errors[0])
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse((self.output_dir / "rotated_animated.gif").exists())


if __name__ == "__main__":
    unittest.main()
