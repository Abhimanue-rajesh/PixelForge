from collections import Counter, defaultdict
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp"}
DUPLICATES_DIRNAME = "Duplicates"
_ALIASES = {"jpeg": "jpg", "tiff": "tif"}


def _type_of(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return _ALIASES.get(ext, ext)


def scan_folder(folder: Path, recursive: bool = True) -> list[Path]:
    """Return all image files in folder, skipping our own Duplicates folder."""
    entries = folder.rglob("*") if recursive else folder.glob("*")
    files = []
    for p in entries:
        if DUPLICATES_DIRNAME in p.relative_to(folder).parts[:-1]:
            continue
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            files.append(p)
    return sorted(files)


def count_by_type(files: list[Path]) -> dict[str, int]:
    """e.g. {'jpg': 120, 'png': 30}. jpeg counts as jpg."""
    return dict(sorted(Counter(_type_of(f) for f in files).items()))


def folder_stats(files: list[Path], root: Path) -> dict[Path, dict[str, int]]:
    """Per-folder image counts by type, including everything inside subfolders."""
    stats = defaultdict(Counter)
    for f in files:
        folder, kind = f.parent, _type_of(f)
        while True:
            stats[folder][kind] += 1
            if folder == root or folder.parent == folder:
                break
            folder = folder.parent
    return {k: dict(sorted(v.items())) for k, v in stats.items()}
