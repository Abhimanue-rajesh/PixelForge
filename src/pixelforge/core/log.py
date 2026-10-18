"""The move log: the app's record of which files sit in which Duplicates/Set_XXXX folder
and where they came from. Review and Undo both work from this file."""

import json
from pathlib import Path

from .scanner import DUPLICATES_DIRNAME

LOG_NAME = "pixelforge_log.json"


def duplicates_dir(root: Path) -> Path:
    return root / DUPLICATES_DIRNAME


def load_log(root: Path) -> dict:
    try:
        data = json.loads((duplicates_dir(root) / LOG_NAME).read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("sets"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"version": 2, "sets": []}


def save_log(root: Path, data: dict) -> None:
    d = duplicates_dir(root)
    d.mkdir(exist_ok=True)
    (d / LOG_NAME).write_text(json.dumps(data, indent=2), encoding="utf-8")


def next_set_number(root: Path, data: dict) -> int:
    names = [s["name"] for s in data["sets"]]
    d = duplicates_dir(root)
    if d.exists():
        names += [p.name for p in d.glob("Set_*")]
    nums = [0]
    for n in names:
        try:
            nums.append(int(n.split("_")[1]))
        except (IndexError, ValueError):
            pass
    return max(nums) + 1
