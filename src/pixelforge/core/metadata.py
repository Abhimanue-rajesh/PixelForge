"""Rebuild a still image from pixels without carrying its metadata forward."""

import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def remove_metadata(source: Path, destination: Path, overwrite: bool = False) -> Path:
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError("Choose an existing image file.")
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Choose a JPEG, PNG, WebP, BMP or TIFF image.")
    if destination.suffix.lower() != source.suffix.lower():
        raise ValueError("Save the image with the same file extension as the original.")
    if not destination.parent.is_dir():
        raise ValueError("The output folder does not exist.")
    if destination.exists() and not (overwrite and destination == source):
        raise FileExistsError("That file already exists. Choose a different output filename.")

    temp_path = None
    try:
        with Image.open(source) as image:
            if getattr(image, "n_frames", 1) > 1:
                raise ValueError("Animated and multi-page images are not supported; the original was left untouched.")
            # Palette transparency is pixel appearance, so retain it as alpha.
            pixels = image.convert("RGBA") if "transparency" in image.info or image.mode == "P" else image
            with Image.new(pixels.mode, pixels.size) as clean:
                clean.paste(pixels)
                fd, name = tempfile.mkstemp(suffix=source.suffix, dir=destination.parent)
                os.close(fd)
                temp_path = Path(name)
                options = {"lossless": True} if image.format == "WEBP" else {}
                clean.save(temp_path, format=image.format, **options)

        if overwrite and destination == source:
            os.replace(temp_path, destination)
        else:
            # Exclusive creation also protects against a file appearing during processing.
            with destination.open("xb") as output:
                try:
                    with temp_path.open("rb") as saved:
                        shutil.copyfileobj(saved, output)
                except Exception:
                    output.close()
                    destination.unlink()
                    raise
        return destination
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
