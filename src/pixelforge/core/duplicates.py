import hashlib
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from .log import duplicates_dir, load_log, next_set_number, save_log

Progress = Optional[Callable[[int, int], None]]


@dataclass
class ImageInfo:
    path: Path
    size_bytes: int
    width: int
    height: int
    taken: datetime

    @property
    def pixels(self) -> int:
        return self.width * self.height


@dataclass
class DuplicateGroup:
    files: list[ImageInfo]  # 2 or more identical copies, suggested-best first


def human_size(n: int) -> str:
    if n < 1024 * 1024:
        return f"{max(1, round(n / 1024))}KB"
    return f"{n / 1024 / 1024:.1f}MB"


def file_hash(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def read_info(path: Path) -> ImageInfo:
    """Dimensions + date taken (EXIF, falling back to file modified time)."""
    stat = path.stat()
    taken = datetime.fromtimestamp(stat.st_mtime)
    width = height = 0
    try:
        with Image.open(path) as img:
            width, height = img.size
            exif = img.getexif()
            raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)
            if raw:
                taken = datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass  # unreadable metadata is fine; we keep the fallbacks
    return ImageInfo(path, stat.st_size, width, height, taken)


def find_duplicates(
    files: list[Path], progress: Progress = None
) -> list[DuplicateGroup]:
    """Find sets of byte-identical files. Only files sharing a size get hashed."""
    by_size = defaultdict(list)
    for f in files:
        try:
            by_size[f.stat().st_size].append(f)
        except OSError:
            continue
    candidates = [f for group in by_size.values() if len(group) > 1 for f in group]

    by_hash = defaultdict(list)
    for i, f in enumerate(candidates, 1):
        try:
            by_hash[file_hash(f)].append(f)
        except OSError:
            continue
        if progress:
            progress(i, len(candidates))

    groups = []
    for paths in by_hash.values():
        if len(paths) < 2:
            continue
        # Suggested keeper first: most pixels, then biggest file, then oldest.
        infos = sorted(
            (read_info(p) for p in paths),
            key=lambda i: (-i.pixels, -i.size_bytes, i.taken, str(i.path)),
        )
        groups.append(DuplicateGroup(infos))
    groups.sort(key=lambda g: str(g.files[0].path))
    return groups


def build_name(info: ImageInfo) -> str:
    """e.g. 2024-05-17_143022_4032x3024_2.4MB_IMG_1234.jpg"""
    dims = f"{info.width}x{info.height}" if info.width else "unknown"
    return (
        f"{info.taken:%Y-%m-%d_%H%M%S}_{dims}_{human_size(info.size_bytes)}_"
        f"{info.path.stem}{info.path.suffix.lower()}"
    )


def unique_path(folder: Path, name: str) -> Path:
    target = folder / name
    n = 1
    while target.exists():
        target = folder / f"{Path(name).stem}_{n}{Path(name).suffix}"
        n += 1
    return target


def move_sets(groups: list[DuplicateGroup], root: Path, progress: Progress = None):
    """Move EVERY copy of each set into root/Duplicates/Set_XXXX (moved, not copied).
    Returns (files_moved, errors)."""
    dest = duplicates_dir(root)
    dest.mkdir(exist_ok=True)
    data = load_log(root)
    number = next_set_number(root, data)
    total = sum(len(g.files) for g in groups)
    done, moved, errors = 0, 0, []
    try:
        for g in groups:
            set_name = f"Set_{number:04d}"
            number += 1
            set_dir = dest / set_name
            set_dir.mkdir(exist_ok=True)
            entries = []
            for info in g.files:
                target = unique_path(set_dir, build_name(info))
                try:
                    shutil.move(str(info.path), str(target))
                    entries.append(
                        {
                            "original": str(info.path),
                            "moved_to": str(target),
                            "width": info.width,
                            "height": info.height,
                            "size_bytes": info.size_bytes,
                            "taken": info.taken.isoformat(timespec="seconds"),
                        }
                    )
                except OSError as e:
                    errors.append(f"{info.path}: {e}")
                done += 1
                if progress:
                    progress(done, total)
            if entries:
                data["sets"].append({"name": set_name, "files": entries})
                moved += len(entries)
                if len(data["sets"]) % 25 == 0:
                    save_log(root, data)  # periodic save in case of a crash
            else:
                try:
                    set_dir.rmdir()
                except OSError:
                    pass
    finally:
        save_log(root, data)
    return moved, errors
