import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pixelforge.core.metadata import remove_metadata


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_image(self, name="photo.png"):
        source = self.root / name
        image = Image.new("RGB", (20, 16), (120, 60, 30))
        exif = Image.Exif()
        exif[271] = "Private camera name"
        exif[306] = "2024:05:17 14:30:22"
        options = {"exif": exif, "icc_profile": b"private profile"}
        if source.suffix == ".png":
            text = PngImagePlugin.PngInfo()
            text.add_text("Comment", "Private comment")
            options["pnginfo"] = text
        image.save(source, **options)
        return source

    def test_metadata_removed_across_formats_and_original_preserved(self):
        for extension in (".png", ".jpg", ".webp", ".tiff"):
            with self.subTest(extension=extension):
                source = self.make_image(f"photo{extension}")
                original = source.read_bytes()
                output = self.root / f"clean{extension}"
                self.assertEqual(remove_metadata(source, output), output)
                self.assertEqual(source.read_bytes(), original)
                with Image.open(output) as clean:
                    self.assertEqual(clean.size, (20, 16))
                    self.assertNotIn(271, clean.getexif())
                    self.assertNotIn(306, clean.getexif())
                    self.assertFalse(clean.info.get("exif"))
                    self.assertNotIn("icc_profile", clean.info)
                    self.assertNotIn("Comment", clean.info)
                if extension != ".jpg":
                    with Image.open(source) as before, Image.open(output) as after:
                        self.assertEqual(before.tobytes(), after.tobytes())

    def test_explicit_overwrite(self):
        source = self.make_image()
        remove_metadata(source, source, overwrite=True)
        with Image.open(source) as image:
            self.assertEqual(image.getpixel((0, 0)), (120, 60, 30))
            self.assertFalse(image.getexif())
            self.assertNotIn("Comment", image.info)

    def test_existing_files_never_replaced_in_save_as(self):
        source = self.make_image()
        output = self.root / "existing.png"
        output.write_bytes(b"do not replace")
        for target, overwrite in ((source, False), (output, False), (output, True)):
            with self.subTest(target=target, overwrite=overwrite):
                before = target.read_bytes()
                with self.assertRaises(FileExistsError):
                    remove_metadata(source, target, overwrite)
                self.assertEqual(target.read_bytes(), before)

    def test_palette_and_transparency_preserved(self):
        source = self.root / "palette.png"
        image = Image.new("P", (4, 4), 1)
        image.putpalette([255, 0, 0, 0, 255, 0] + [0] * 762)
        image.putpixel((0, 0), 0)
        image.save(source, transparency=0)
        output = self.root / "clean.png"
        remove_metadata(source, output)
        with Image.open(source) as before, Image.open(output) as after:
            self.assertEqual(before.convert("RGBA").tobytes(), after.convert("RGBA").tobytes())

    def test_multiframe_files_rejected_without_changing_original(self):
        source = self.root / "pages.tiff"
        Image.new("RGB", (4, 4)).save(source, save_all=True, append_images=[Image.new("RGB", (4, 4), "red")])
        before = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "multi-page"):
            remove_metadata(source, source, overwrite=True)
        self.assertEqual(source.read_bytes(), before)

    def test_save_failure_leaves_original_and_no_temp_file(self):
        source = self.make_image()
        before = source.read_bytes()
        with patch.object(Image.Image, "save", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                remove_metadata(source, source, overwrite=True)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [source])

    def test_destination_race_does_not_overwrite(self):
        source = self.make_image()
        output = self.root / "clean.png"
        original_save = Image.Image.save

        def save_and_create(image, *args, **kwargs):
            original_save(image, *args, **kwargs)
            output.write_bytes(b"created while processing")

        with patch.object(Image.Image, "save", save_and_create):
            with self.assertRaises(FileExistsError):
                remove_metadata(source, output)
        self.assertEqual(output.read_bytes(), b"created while processing")

    def test_invalid_paths_and_format(self):
        source = self.make_image()
        for input_path, output in (
            (self.root / "missing.png", self.root / "out.png"),
            (source, self.root / "out.jpg"),
            (source, self.root / "missing" / "out.png"),
        ):
            with self.subTest(input_path=input_path, output=output), self.assertRaises(ValueError):
                remove_metadata(input_path, output)


if __name__ == "__main__":
    unittest.main()
