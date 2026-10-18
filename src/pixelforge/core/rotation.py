"""Batch rotation using the original script's imageio/SciPy pipeline."""

import logging
import math
from contextlib import closing
from pathlib import Path

import imageio.v2 as imageio
from PIL import Image
from scipy import ndimage

from .duplicates import Progress
from .scanner import scan_folder


def rotate_images(input_dir: Path, output_dir: Path, angle: float = 45, progress: Progress = None):
    """Return (saved paths, errors). Process only images directly inside input_dir."""
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if not input_dir.is_dir():
        raise ValueError("Choose an existing input folder.")
    if not math.isfinite(angle):
        raise ValueError("Enter a finite numeric rotation angle.")
    files = scan_folder(input_dir, recursive=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    saved, errors = [], []
    logger = logging.Logger(__name__, logging.INFO)
    with closing(logging.FileHandler(output_dir / "rotation.log", encoding="utf-8")) as log_file:
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        for handler in (log_file, logging.StreamHandler()):
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.info("Starting rotation of images in '%s' by %s degrees.", input_dir, angle)
        for index, source in enumerate(files, 1):
            target = output_dir / f"rotated_{source.name}"
            try:
                if target.exists():
                    raise FileExistsError("Output already exists; choose another output folder.")
                with Image.open(source) as header:
                    if getattr(header, "n_frames", 1) > 1:
                        raise ValueError("Animated and multi-page images are not supported.")
                image = imageio.imread(source)
                rotated = ndimage.rotate(image, angle)
                with target.open("xb") as output:
                    try:
                        imageio.imwrite(output, rotated, format=source.suffix)
                    except Exception:
                        output.close()
                        target.unlink()
                        raise
                saved.append(target)
                logger.info("Rotated and saved: %s", target)
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")
                logger.error("Error processing %s: %s", source, exc)
            if progress:
                progress(index, len(files))
        logger.info("Finished rotating images. Saved %s; skipped %s.", len(saved), len(errors))
    return saved, errors
