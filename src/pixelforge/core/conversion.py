"""Convert still images alongside their originals, without overwriting files."""

import logging
from contextlib import closing
from pathlib import Path

from PIL import Image
from send2trash import send2trash

from .duplicates import Progress, unique_path
from .scanner import scan_folder

OUTPUT_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp", "TIFF": ".tiff", "GIF": ".gif"}


def files_to_convert(directory: Path, output_format: str, recursive: bool = True) -> list[Path]:
    if output_format not in OUTPUT_FORMATS:
        raise ValueError("Choose a supported output format.")
    if not directory.is_dir():
        raise ValueError("Choose an existing image folder.")
    extension = OUTPUT_FORMATS[output_format]
    return [path for path in scan_folder(directory, recursive) if path.suffix.lower() != extension]


def convert_images(
    files: list[Path], directory: Path, output_format: str = "JPEG",
    delete_originals: bool = False, progress: Progress = None,
):
    """Return (saved paths, recycled count, errors). Recycle only after a verified save."""
    if output_format not in OUTPUT_FORMATS:
        raise ValueError("Choose a supported output format.")
    if not directory.is_dir():
        raise ValueError("Choose an existing image folder.")
    extension = OUTPUT_FORMATS[output_format]
    saved, recycled, errors = [], 0, []
    logger = logging.Logger(__name__, logging.INFO)
    with closing(logging.FileHandler(directory / "conversion.log", encoding="utf-8")) as log_file:
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        for handler in (log_file, logging.StreamHandler()):
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.info("Starting conversion to %s in %s.", output_format, directory)
        for index, source in enumerate(files, 1):
            target, created, verified = None, False, False
            try:
                if source.suffix.lower() == extension:
                    continue
                target = unique_path(source.parent, source.with_suffix(extension).name)
                with Image.open(source) as image:
                    if getattr(image, "n_frames", 1) > 1:
                        raise ValueError("Animated and multi-page images are not supported.")
                    has_alpha = "A" in image.getbands() or "transparency" in image.info
                    mode = "RGBA" if has_alpha and output_format not in ("JPEG", "BMP") else "RGB"
                    with image.convert(mode) as converted:
                        with target.open("xb") as output:
                            created = True
                            options = {"quality": 90} if output_format == "JPEG" else {}
                            converted.save(output, output_format, **options)
                with Image.open(target) as result:
                    result.load()
                verified = True
                saved.append(target)
                logger.info("Converted: %s -> %s", source, target)
                if delete_originals:
                    send2trash(str(source.resolve()))
                    recycled += 1
                    logger.info("Sent original to Recycle Bin: %s", source)
            except Exception as exc:
                message = f"{source}: {exc}"
                if created and not verified:
                    try:
                        target.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        message += f"; could not remove partial output {target}: {cleanup_error}"
                errors.append(message)
                logger.error("Error processing %s", message)
            finally:
                if progress:
                    progress(index, len(files))
        logger.info("Finished conversion. Saved %s; recycled %s; problems %s.", len(saved), recycled, len(errors))
    return saved, recycled, errors
