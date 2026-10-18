import json
import shutil
from pathlib import Path

from .duplicates import Progress, unique_path
from .scanner import DUPLICATES_DIRNAME


def files_to_gather(files: list[Path], root: Path) -> list[Path]:
    """Images that live in a subfolder rather than directly in root."""
    return [f for f in files if f.parent != root]


def remove_empty_folders(root: Path) -> int:
    """Remove empty subfolders (deepest first). rmdir only works on empty folders."""
    removed = 0
    dirs = sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for d in dirs:
        if DUPLICATES_DIRNAME in d.relative_to(root).parts:
            continue
        try:
            d.rmdir()
            removed += 1
        except OSError:
            pass  # not empty: leave it alone
    return removed


def gather_files(
    files: list[Path], root: Path, progress: Progress = None, remove_empty: bool = False
):
    """Move images from subfolders into root. Never overwrites: clashes get _1, _2...
    Returns (moved, errors, removed_folder_count)."""
    todo = files_to_gather(files, root)
    moved, errors = [], []
    for i, f in enumerate(todo, 1):
        target = unique_path(root, f.name)
        try:
            shutil.move(str(f), str(target))
            moved.append({"original": str(f), "moved_to": str(target)})
        except OSError as e:
            errors.append(f"{f}: {e}")
        if progress:
            progress(i, len(todo))

    if moved:  # log is the basis for a future Undo
        log_file = root / "pixelforge_gather_log.json"
        history = []
        if log_file.exists():
            try:
                history = json.loads(log_file.read_text(encoding="utf-8"))
            except ValueError:
                pass
        log_file.write_text(json.dumps(history + moved, indent=2), encoding="utf-8")

    removed = remove_empty_folders(root) if remove_empty else 0
    return moved, errors, removed
