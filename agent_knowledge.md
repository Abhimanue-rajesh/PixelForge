# PixelForge: Agent Knowledge

Read this before changing anything. Update it when you change behaviour, structure or decisions.

## 1. What this project is

PixelForge is a **native-feeling Windows desktop image toolkit**. Home links to separate Duplicates, Gather images and Remove metadata pages. Duplicate finding is one feature, not the app's main identity. Date-based renaming and sorting are planned. It is meant to be **installed by other, non-technical users**, so it must feel like a normal Windows program with a safe, undo-able workflow.

- Language: Python 3.10+
- UI: **PySide6 (Qt)**
- Image handling: Pillow (`PIL`); `imagehash` is installed but **not used yet** (reserved for similar-image detection)
- Recycle Bin: `send2trash`
- Packaging (planned, not done): PyInstaller in **folder mode** (not `--onefile`) + Inno Setup `Setup.exe`
- Target OS: Windows (code is cross-platform Python, so it can be tested on Linux/macOS headless)

The owner started from a separate repo of loose scripts (`ImageManipulationScripts`, ML-oriented). PixelForge is a **new, separate repo**; it does not depend on those scripts.

## 2. Repository layout

```
PixelForge/
├── run.py                  Dev launcher: adds src/ to sys.path, calls pixelforge.main.run()
├── requirements.txt        PySide6, pillow, imagehash, send2trash
├── setup.cfg
├── README.md
├── .gitignore              .venv/, venv/, __pycache__/, build/, dist/, *.spec
└── src/pixelforge/
    ├── main.py             QApplication + MainWindow; exposes run()
    ├── assets/fonts/       bundled Poppins Regular/Medium/SemiBold + OFL.txt
    ├── core/               NO Qt imports allowed here
    │   ├── scanner.py      find image files, count by type, per-folder stats
    │   ├── duplicates.py   hashing, find sets, naming, move_sets()
    │   ├── log.py          read/write the move log (pixelforge_log.json)
    │   ├── review.py       pending_sets(), resolve_sets() (keep one), undo_all()
    │   ├── organizer.py    gather images from subfolders into the main folder
    │   ├── metadata.py     rebuild a still image from pixels, safely save or overwrite
    │   ├── dates.py        PLACEHOLDER from initial skeleton (rename/sort by date, not built)
    │   └── history.py      PLACEHOLDER from initial skeleton (undo lives in log.py/review.py now)
    └── ui/
        ├── main_window.py  the single main window and all workflow logic
        ├── metadata_page.py separate single-image metadata tool
        ├── workers.py      QThread wrappers around core functions
        ├── theme.py        stylesheet + light/dark palettes (follows the Windows setting)
        └── widgets.py      StatCard, StepBar, ElidedLabel, repolish()
```

`dates.py` and `history.py` exist in the owner's tree but were created as empty skeleton files. Check their contents before assuming anything. Undo history is currently handled by `log.py` and `review.py`, not `history.py`.

## 3. Architecture rules (keep these)

1. **`core/` never imports Qt.** Core functions take paths in and return plain data out. This keeps them testable without a display.
2. **Long work runs off the UI thread** via `ui/workers.py`. Every worker subclasses `Worker` and implements `work()`. Errors are caught and emitted through the `failed` signal; progress goes through `progress(done, total)`.
3. **Signal naming:** worker completion signals are called `done`, never `finished`, because that clashes with `QThread.finished`.
4. **Keep worker references alive.** `MainWindow.run_worker` stores workers in `self.workers` and removes them on `QThread.finished`. Do not reassign a single `self.worker` attribute; a QThread destroyed while still returning from `run()` can crash the app. `closeEvent` waits on all workers.
5. **Operations are driven by disk state, not just memory.** After any operation the UI calls `rescan()`, which rebuilds everything (including pending review sets) from the filesystem and the log.

## 4. User workflow (current behaviour)

1. **Choose folder** (native dialog). Checkbox: include subfolders (on by default).
2. **Overview:** a tree of folders with total image counts and per-type counts (recursive, e.g. `Holiday  40  JPG 35 · PNG 5`). Summary line shows totals and how many images sit in subfolders.
3. **Find duplicates** (button). Finds sets of 2+ identical files and shows them as a tree of sets, with a "Suggested to keep" label on the best copy.
4. **Move sets…** (separate button, with confirmation dialog). Moves **every** copy of each set into `<folder>/Duplicates/Set_NNNN/` (moved, not copied), renamed with date, resolution and size.
5. **Review** (the UI switches to the review button bar automatically; also resumes after restarting the app, because it reads the log):
   - **Keep selected copy…** the chosen copy returns to its **original folder under its original filename**; the other copies of that set go to the **Recycle Bin**.
   - **Keep suggested in all sets…** same, for every set, using the suggested copy.
   - **Undo all…** every file goes back exactly where it came from.
   - **Open Duplicates folder** opens it in Explorer.
6. **Gather images** (separate sidebar page, disabled while duplicate sets await review): moves images from subfolders into the chosen folder; optional "Remove empty folders afterwards". Duplicates and Gather share the selected folder and scan state; navigating does not reset a workflow.
7. **Remove metadata** (independent sidebar page): choose one image, then save a clean copy by default. An explicit checkbox and confirmation enable overwriting that original. The original script's pixel-recreation approach is retained; no EXIF rotation is applied. Supported extensions: JPEG, PNG, WebP, BMP, TIFF. Reject multi-frame images to avoid dropping frames. Indexed images convert to RGBA to preserve palette colours and transparency; WebP saves losslessly. JPEG re-encodes and rotation/colour-profile removal can affect appearance. Temporary encoding completes before replacing an original; save-as uses exclusive creation and never overwrites an existing destination. Metadata overwrite has no undo, as explicitly requested by the owner's script. Runs via `MetadataWorker`; rescans the shared photo folder after success when one is selected.

## 5. Key decisions and why

| Decision | Reason |
|---|---|
| Duplicates are **sets of 2+**, and **all copies move** into one `Set_NNNN` folder | The owner wants to compare the whole set and choose, instead of the app silently picking a keeper |
| Files are **moved, never copied** | Avoids ending up with two copies (root + Duplicates) |
| Kept copy returns to its **original folder**, not the root | Preserves the user's existing organisation; Gather can flatten later |
| Nothing is deleted outright; extras go to the **Recycle Bin** | Keeps even the final step recoverable |
| **Exact (byte-identical) duplicates only** for now | Simple, safe, fast (size grouping, then SHA-256). Similar-image detection is a planned next step |
| Duplicate/Gather **never overwrite**; name clashes get `_1`, `_2` | Phones and cameras reuse filenames across folders |
| Find and Move are **separate buttons** | Owner wants a confirmation step with counts before anything moves |
| Log file drives Review and Undo | Survives closing the app; stays correct if the user deletes files by hand |
| PySide6 instead of Tkinter | Needs to look and behave like a native Windows app for other users |

## 6. Duplicate logic details

- `scanner.scan_folder(folder, recursive)` returns image files with extensions: `.jpg .jpeg .png .gif .bmp .tif .tiff .webp`. It **skips the `Duplicates` folder** so re-runs never rescan moved files. Counting treats `jpeg` as `jpg` and `tiff` as `tif`.
- `duplicates.find_duplicates(files, progress)`: groups by file size, hashes only size-collisions with SHA-256 (1 MB chunks), builds `DuplicateGroup(files=[ImageInfo...])`.
- **Suggested keeper** (first in `files`): most pixels, then largest file size, then oldest taken date, then path. For byte-identical files these are all equal, so the suggestion is effectively arbitrary until similar-image detection exists; the UI still labels it.
- `ImageInfo`: path, size_bytes, width, height, taken. `taken` = EXIF DateTimeOriginal (tag 36867 in the Exif IFD 0x8769), else EXIF DateTime (306), else file modified time.
- **Renamed filename format:** `YYYY-MM-DD_HHMMSS_WxH_SIZE_origstem.ext`, e.g. `2024-05-17_143022_4032x3024_2.4MB_IMG_1234.jpg`. `SIZE` is `NKB` under 1 MB, else `N.NMB`. Resolution is `unknown` if the image can't be read. Extension is lowercased.
- `duplicates.move_sets(groups, root, progress)` returns `(files_moved, errors)`. Set numbers continue from existing `Set_*` folders and the log. The log is saved every 25 sets and in a `finally` block.

## 7. The move log

Location: `<root>/Duplicates/pixelforge_log.json`. Format (version 2):

```json
{
  "version": 2,
  "sets": [
    {
      "name": "Set_0001",
      "files": [
        {
          "original": "C:/Photos/Holiday/IMG_1.jpg",
          "moved_to": "C:/Photos/Duplicates/Set_0001/2024-05-17_143022_4032x3024_2.4MB_IMG_1.jpg",
          "width": 4032, "height": 3024,
          "size_bytes": 2516582,
          "taken": "2024-05-17T14:30:22"
        }
      ]
    }
  ]
}
```

- `files` within a set are ordered suggested-best first; the UI relies on index 0 being the suggestion.
- `review.pending_sets(root)` prunes entries whose `moved_to` no longer exists and rewrites the log, so the log always matches disk. It is called on every scan.
- After a successful review or undo, `_cleanup` deletes the log when no sets remain and removes empty `Set_*` folders and an empty `Duplicates` folder. It never removes a `Duplicates` folder that still contains other files.
- An older flat-list log format (earlier version) is ignored by `load_log` and will be overwritten. Test data from that version should be deleted.
- Gather writes a separate `<root>/pixelforge_gather_log.json` (flat list of `{original, moved_to}`). **There is no Undo for Gather yet.**

## 8. Module reference

**core/scanner.py**
- `scan_folder(folder, recursive=True) -> list[Path]`
- `count_by_type(files) -> dict[str,int]`
- `folder_stats(files, root) -> dict[Path, dict[str,int]]` (recursive counts per folder, root included)
- Constants: `IMAGE_EXTENSIONS`, `DUPLICATES_DIRNAME = "Duplicates"`

**core/duplicates.py**
- `find_duplicates(files, progress=None) -> list[DuplicateGroup]`
- `move_sets(groups, root, progress=None) -> (int, list[str])`
- `read_info(path)`, `build_name(info)`, `unique_path(folder, name)`, `human_size(n)`, `file_hash(path)`
- `Progress = Optional[Callable[[int, int], None]]`

**core/log.py**
- `load_log(root)`, `save_log(root, data)`, `duplicates_dir(root)`, `next_set_number(root, data)`, `LOG_NAME`

**core/review.py**
- `pending_sets(root) -> list[dict]`
- `resolve_sets(root, choices: {set_name: moved_to_path | None}, progress=None) -> (kept, trashed, errors)` (`None` means use the suggested copy)
- `undo_all(root, progress=None) -> (restored, errors)`
- Restoring: file returns to `original` path under its original name; creates missing parent folders; uses `unique_path` if something already sits there.

**core/organizer.py**
- `files_to_gather(files, root)`, `gather_files(files, root, progress=None, remove_empty=False) -> (moved, errors, removed_dirs)`, `remove_empty_folders(root)` (uses `rmdir`, so only truly empty folders go)

**core/metadata.py**: `remove_metadata(source, destination, overwrite=False) -> Path`. Core has no Qt imports; errors propagate to the worker. Overwrite only permits replacing the source itself. The destination extension must match the source; same-folder temporary files are cleaned up on success and failure.

**ui/main_window.py**: `MainWindow`. State: `page, folder, files, groups (found, not moved), pending (moved, awaiting review), nested, busy, flash, workers`. `show_page()` selects Home, the shared Duplicates/Gather workspace, or MetadataPage. `refresh()` decides button visibility/enabled state and which tree is shown (overview tree vs sets tree). `flash` is a one-shot result message shown above the summary after the next rescan.

## 8b. UI design system

- `main.py` sets the **Fusion** style, registers bundled **Poppins** via `theme.load_fonts(app)`, then `theme.apply_theme(app)` installs one app-wide stylesheet and palette. It re-applies automatically when Windows switches light/dark (Qt 6.5+). Font files and their license must ship in `pixelforge/assets/fonts/` when packaging.
- **Colours live only in `theme.py`** (`LIGHT` and `DARK` dicts). Don't hard-code colours in widgets; use stylesheet properties instead: `card="true"` on a QFrame for a card, `role="muted"` for secondary text, `variant="primary"|"secondary"` on buttons.
- After changing a dynamic property at runtime, call `widgets.repolish(widget)` or the style won't update.
- Layout follows Windows Settings: persistent left navigation, page heading, restrained settings rows, 6px card corners and neutral light/dark surfaces. Home has three tool rows. The Duplicates workspace retains `StepBar`, folder selector, one compact statistics strip, messages, workflow/review actions, and the empty/overview/sets tree stack. Gather shows only folder statistics, its own action row and the overview tree. Metadata has its own file selector and save controls. Progress sits below the page stack and is shared across tools. Navigation is allowed during work, but mutation controls are disabled globally until it finishes.
- `MainWindow.refresh()` is the single place that sets the step, button states, which button is the accent (primary) one, stat cards and which stack page shows. Call it after any state change.
- Keep all four duplicate-review buttons on one horizontal row: Keep selected, Keep suggested in all sets, Undo all, Open Duplicates folder.
- Use plain text navigation and tree rows without decorative icons or emoji. Keep functional checkbox ticks and disclosure arrows.
- Empty-state labels share their layout width; center their text rather than each widget individually so wrapped descriptions receive their required height.
- The checkbox tick image is generated at runtime into the system temp folder (`pixelforge/check_*.png`), so no data files need bundling for packaging.

## 9. Running and testing

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Headless smoke testing works without a display:

```
QT_QPA_PLATFORM=offscreen python your_test.py
```

Run `python -m unittest discover -s tests -v` (use the venv interpreter). `tests/test_metadata.py` covers metadata stripping, pixel/transparency preservation, overwrite safety, failed saves, destination races and multi-frame rejection. `tests/test_ui.py` uses Qt offscreen and checks bundled fonts, page navigation, duplicate move/restart/review/undo, gathering and metadata save/cancel. UI tests patch confirmations, pump events and wait for both `busy` and `workers` to clear. Recycle Bin dispatch is stubbed against temporary fixtures in the review test.

## 10. Roadmap (in rough priority order)

1. **Rename by date** (`core/dates.py` + UI): use the same date logic as `read_info`; preview table before applying; never overwrite; write a log for undo.
2. **Sort into folders by date** (e.g. `2024/05/`), same preview and undo approach.
3. **Similar-image detection** with `imagehash` (perceptual hash). This is when "suggested keeper" becomes meaningful (resolution/size differ). Beware O(n²) comparisons on big folders; consider bucketing or a BK-tree.
4. **Undo for Gather** using `pixelforge_gather_log.json`.
5. **Cancel button** for long operations.
6. **Packaging:** PyInstaller folder mode, then an Inno Setup installer (Start Menu shortcut, uninstaller). Expect an installer of roughly 80–150 MB. Unsigned apps trigger a Windows SmartScreen warning ("More info", then "Run anyway"); fixing it needs a paid code-signing certificate.
7. **HEIC support** (iPhone photos) would need `pillow-heif`; not included in `IMAGE_EXTENSIONS` today.
8. Expand core regression coverage beyond the existing unittest metadata/UI checks.

## 11. Conventions for agents working here

- **Safety first.** Any operation that moves or removes user files needs: a confirmation dialog stating counts and destination, no silent overwrites, and a log entry that makes it undo-able. Prefer the Recycle Bin (`send2trash`) over permanent deletion.
- Keep `core/` free of Qt; put UI-only logic in `ui/`.
- Add new long-running operations as a `Worker` subclass in `ui/workers.py` with a `done` signal.
- After mutating files from the UI, finish with `self.rescan()` so the display reflects disk.
- Keep the UI text plain and friendly; users are not technical.
- Use `pathlib.Path` throughout and keep paths in the log as strings.
- Don't add dependencies without adding them to `requirements.txt` and noting them here.
- Known limitation to be aware of: on Windows, `send2trash` may delete permanently (no Recycle Bin) for files on network or some external drives.
- When in doubt about the owner's intent, ask; they prefer to agree on the workflow before code is written.
