import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pixelforge.core.conversion import OUTPUT_FORMATS, convert_images, files_to_convert


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_image(self, name="photo.png", mode="RGB"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        colour = (30, 100, 180, 80) if mode == "RGBA" else (30, 100, 180)
        Image.new(mode, (20, 12), colour).save(path)
        return path

    def test_all_output_formats(self):
        for output_format, extension in OUTPUT_FORMATS.items():
            with self.subTest(output_format=output_format):
                source_extension = ".png" if output_format == "BMP" else ".bmp"
                source = self.make_image(f"{output_format}/photo{source_extension}")
                original = source.read_bytes()
                saved, recycled, errors = convert_images([source], self.root, output_format)
                self.assertFalse(errors)
                self.assertEqual(recycled, 0)
                self.assertEqual(saved, [source.with_suffix(extension)])
                with Image.open(saved[0]) as converted:
                    self.assertEqual(converted.format, output_format)
                    self.assertEqual(converted.size, (20, 12))
                self.assertEqual(source.read_bytes(), original)

    def test_jpg_matches_supplied_rgb_quality_90_pipeline(self):
        source = self.make_image(mode="RGBA")
        expected = self.root / "expected.jpg"
        with Image.open(source) as image:
            image.convert("RGB").save(expected, "JPEG", quality=90)
        saved, _, errors = convert_images([source], self.root)
        self.assertFalse(errors)
        self.assertEqual(saved[0].read_bytes(), expected.read_bytes())

    def test_recursive_scan_skips_target_extension_and_duplicate_review_folder(self):
        source = self.make_image()
        nested = self.make_image("nested/photo.jpeg")
        self.make_image("already.jpg")
        self.make_image("Duplicates/Set_0001/review.png")
        (self.root / "notes.txt").write_text("not an image", encoding="utf-8")
        self.assertEqual(set(files_to_convert(self.root, "JPEG")), {source, nested})
        self.assertEqual(files_to_convert(self.root, "JPEG", recursive=False), [source])

    def test_collisions_keep_existing_files_and_use_numbered_names(self):
        source = self.make_image()
        existing = self.root / "photo.jpg"
        existing.write_bytes(b"keep this file")
        saved, _, errors = convert_images([source], self.root)
        self.assertFalse(errors)
        self.assertEqual(saved, [self.root / "photo_1.jpg"])
        self.assertEqual(existing.read_bytes(), b"keep this file")

    def test_transparency_preserved_for_png_and_lossless_tiff(self):
        source = self.make_image(mode="RGBA")
        for output_format in ("PNG", "TIFF"):
            with self.subTest(output_format=output_format):
                original = self.make_image(f"{output_format}/photo.tiff", mode="RGBA")
                if output_format == "TIFF":
                    original = source
                saved, _, errors = convert_images([original], self.root, output_format)
                self.assertFalse(errors)
                with Image.open(original) as before, Image.open(saved[0]) as after:
                    self.assertEqual(before.convert("RGBA").tobytes(), after.convert("RGBA").tobytes())

    def test_only_verified_conversions_are_recycled(self):
        source = self.make_image()
        calls = []

        def recycle(path):
            with Image.open(self.root / "photo.jpg") as converted:
                converted.verify()
            calls.append(path)
            Path(path).unlink()

        with patch("pixelforge.core.conversion.send2trash", side_effect=recycle):
            saved, recycled, errors = convert_images([source], self.root, delete_originals=True)
        self.assertFalse(errors)
        self.assertEqual(recycled, 1)
        self.assertEqual(calls, [str(source.resolve())])
        self.assertTrue(saved[0].exists())
        self.assertFalse(source.exists())
        log = (self.root / "conversion.log").read_text(encoding="utf-8")
        self.assertIn("Converted:", log)
        self.assertIn("Sent original to Recycle Bin:", log)

    def test_failed_save_keeps_original_and_removes_partial_output(self):
        source = self.make_image()
        original = source.read_bytes()

        def fail_save(image, output, *args, **kwargs):
            output.write(b"partial output")
            raise OSError("disk full")

        with patch.object(Image.Image, "save", fail_save), patch("pixelforge.core.conversion.send2trash") as recycle:
            saved, recycled, errors = convert_images([source], self.root, delete_originals=True)
        self.assertFalse(saved)
        self.assertEqual(recycled, 0)
        self.assertIn("disk full", errors[0])
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse((self.root / "photo.jpg").exists())
        recycle.assert_not_called()

    def test_invalid_saved_image_does_not_trigger_recycling(self):
        source = self.make_image()

        def invalid_save(image, output, *args, **kwargs):
            output.write(b"not a valid image")

        with patch.object(Image.Image, "save", invalid_save), patch("pixelforge.core.conversion.send2trash") as recycle:
            saved, recycled, errors = convert_images([source], self.root, delete_originals=True)
        self.assertFalse(saved)
        self.assertEqual(recycled, 0)
        self.assertEqual(len(errors), 1)
        self.assertTrue(source.exists())
        self.assertFalse((self.root / "photo.jpg").exists())
        recycle.assert_not_called()

    def test_cleanup_failure_is_reported_and_batch_continues(self):
        bad = self.make_image("bad.png")
        good = self.make_image("good.png")
        original_save, original_unlink = Image.Image.save, Path.unlink

        def fail_one_save(image, output, *args, **kwargs):
            if Path(output.name).stem == "bad":
                output.write(b"partial output")
                raise OSError("disk full")
            original_save(image, output, *args, **kwargs)

        def fail_one_cleanup(path, *args, **kwargs):
            if path.name == "bad.jpg":
                raise PermissionError("file locked")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Image.Image, "save", fail_one_save), patch.object(Path, "unlink", fail_one_cleanup):
            saved, _, errors = convert_images([bad, good], self.root)
        self.assertEqual(saved, [self.root / "good.jpg"])
        self.assertEqual(len(errors), 1)
        self.assertIn("could not remove partial output", errors[0])
        self.assertTrue(bad.exists())

    def test_truncated_jpeg_does_not_trigger_recycling(self):
        source = self.make_image()
        original_save = Image.Image.save

        def truncated_save(image, output, *args, **kwargs):
            encoded = BytesIO()
            original_save(image, encoded, *args, **kwargs)
            output.write(encoded.getvalue()[:-2])

        with patch.object(Image.Image, "save", truncated_save), patch("pixelforge.core.conversion.send2trash") as recycle:
            saved, recycled, errors = convert_images([source], self.root, delete_originals=True)
        self.assertFalse(saved)
        self.assertEqual(recycled, 0)
        self.assertTrue(errors)
        self.assertTrue(source.exists())
        self.assertFalse((self.root / "photo.jpg").exists())
        recycle.assert_not_called()

    def test_recycle_failure_preserves_output_and_reports_problem(self):
        source = self.make_image()
        with patch("pixelforge.core.conversion.send2trash", side_effect=OSError("Recycle Bin unavailable")):
            saved, recycled, errors = convert_images([source], self.root, delete_originals=True)
        self.assertEqual(recycled, 0)
        self.assertTrue(saved[0].exists())
        self.assertTrue(source.exists())
        self.assertIn("Recycle Bin unavailable", errors[0])

    def test_output_race_does_not_overwrite_or_recycle_original(self):
        source = self.make_image()
        target = self.root / "photo.jpg"

        def racing_path(folder, name):
            target.write_bytes(b"created by another process")
            return target

        with patch("pixelforge.core.conversion.unique_path", side_effect=racing_path), \
                patch("pixelforge.core.conversion.send2trash") as recycle:
            saved, recycled, errors = convert_images([source], self.root, delete_originals=True)
        self.assertFalse(saved)
        self.assertEqual(recycled, 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(target.read_bytes(), b"created by another process")
        self.assertTrue(source.exists())
        recycle.assert_not_called()

    def test_failed_inputs_do_not_stop_batch_and_progress_reaches_total(self):
        bad = self.root / "bad.png"
        bad.write_bytes(b"bad image")
        animation = self.root / "animated.gif"
        Image.new("RGB", (4, 4), "red").save(
            animation, save_all=True, append_images=[Image.new("RGB", (4, 4), "blue")]
        )
        good = self.make_image()
        updates = []
        saved, _, errors = convert_images(
            [bad, animation, good], self.root, progress=lambda *args: updates.append(args)
        )
        self.assertEqual(saved, [self.root / "photo.jpg"])
        self.assertEqual(len(errors), 2)
        self.assertTrue(animation.exists())
        self.assertEqual(updates, [(1, 3), (2, 3), (3, 3)])

    def test_unsupported_format_and_missing_folder(self):
        for output_format, directory in (("PDF", self.root), ("JPEG", self.root / "missing")):
            with self.subTest(output_format=output_format), self.assertRaises(ValueError):
                files_to_convert(directory, output_format)
            with self.assertRaises(ValueError):
                convert_images([], directory, output_format)


if __name__ == "__main__":
    unittest.main()
