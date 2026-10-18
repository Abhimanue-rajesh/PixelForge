"""Review step: pick one copy per set to keep, or undo everything. Works from the log."""

import shutil
from pathlib import Path

from send2trash import send2trash

from .duplicates import Progress, unique_path
from .log import LOG_NAME, duplicates_dir, load_log, save_log


def pending_sets(root: Path) -> list[dict]:
    """Sets still waiting in the Duplicates folder. Forgets files the user already
    removed by hand, so the log always matches what's on disk."""
    data = load_log(root)
    kept_sets, changed = [], False
    for s in data["sets"]:
        files = [f for f in s["files"] if Path(f["moved_to"]).exists()]
        if len(files) != len(s["files"]):
            changed = True
        if files:
            s["files"] = files
            kept_sets.append(s)
        else:
            try:
                (duplicates_dir(root) / s["name"]).rmdir()
            except OSError:
                pass
    if changed or len(kept_sets) != len(data["sets"]):
        data["sets"] = kept_sets
        save_log(root, data)
    return kept_sets


def _restore(entry: dict) -> Path:
    """Move a file back to the folder it came from, under its original name."""
    src, dst = Path(entry["moved_to"]), Path(entry["original"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst = unique_path(dst.parent, dst.name)
    shutil.move(str(src), str(dst))
    return dst


def _cleanup(root: Path) -> None:
    d = duplicates_dir(root)
    if not d.exists():
        return
    if not load_log(root)["sets"]:
        (d / LOG_NAME).unlink(missing_ok=True)
    for sub in d.glob("Set_*"):
        try:
            sub.rmdir()  # only removes empty folders
        except OSError:
            pass
    try:
        d.rmdir()
    except OSError:
        pass


def resolve_sets(root: Path, choices: dict, progress: Progress = None):
    """choices maps set name -> moved_to path of the copy to keep (None = suggested).
    The kept copy returns to its original folder; the rest go to the Recycle Bin.
    Returns (kept, trashed, errors)."""
    todo = [s for s in load_log(root)["sets"] if s["name"] in choices]
    kept, trashed, errors = 0, 0, []
    for i, s in enumerate(todo, 1):
        files = [f for f in s["files"] if Path(f["moved_to"]).exists()]
        if files:
            keep = next(
                (f for f in files if f["moved_to"] == choices[s["name"]]), files[0]
            )
            try:
                _restore(keep)
                kept += 1
            except OSError as e:
                errors.append(f"{keep['moved_to']}: {e}")
                files = []  # leave this set untouched
            for f in files:
                if f is keep:
                    continue
                try:
                    send2trash(f["moved_to"])
                    trashed += 1
                except Exception as e:
                    errors.append(f"{f['moved_to']}: {e}")
        if progress:
            progress(i, len(todo))
    pending_sets(root)  # prunes everything that was resolved
    _cleanup(root)
    return kept, trashed, errors


def undo_all(root: Path, progress: Progress = None):
    """Put every file in the log back exactly where it came from. Returns (restored, errors)."""
    entries = [
        f
        for s in load_log(root)["sets"]
        for f in s["files"]
        if Path(f["moved_to"]).exists()
    ]
    restored, errors = 0, []
    for i, f in enumerate(entries, 1):
        try:
            _restore(f)
            restored += 1
        except OSError as e:
            errors.append(f"{f['moved_to']}: {e}")
        if progress:
            progress(i, len(entries))
    pending_sets(root)
    _cleanup(root)
    return restored, errors
