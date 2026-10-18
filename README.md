# PixelForge

A desktop toolkit for working with photo folders, built with PySide6 and Pillow.

- **Duplicates:** find byte-identical images, move sets for review, choose a copy to keep, or undo the move.
- **Gather images:** move images from subfolders into the main folder without overwriting filenames.
- **Remove metadata:** rebuild a still image without embedded EXIF, location, comments or colour profiles. Save a separate copy by default, or explicitly overwrite the original.
- **Rotate images:** choose input/output folders and an angle (45° by default). Uses the supplied imageio/SciPy rotation pipeline, expands the canvas and saves `rotated_` copies. Existing output files are skipped; `rotation.log` records each run in the output folder.
- **Convert images:** choose JPG, PNG, WebP, BMP, TIFF or GIF. Include subfolders by default, save alongside originals and add numbered suffixes to avoid overwrites. Keep originals by default, or confirm sending successfully converted originals to the Recycle Bin. Progress and `conversion.log` report results.

The interface uses a Windows Settings–inspired sidebar and follows the system light/dark setting. Poppins is bundled with its [SIL Open Font License](src/pixelforge/assets/fonts/OFL.txt), from [Google Fonts](https://github.com/google/fonts/tree/main/ofl/poppins).

A shared progress panel below the page heading shows the active operation, processed counts and percentage. Operations without a known total show an animated bar. Completed progress stays visible, including when switching pages.

Run on Windows:

```powershell
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe run.py
```

Run checks (the UI tests use Qt's offscreen platform):

```powershell
./venv/Scripts/python.exe -m unittest discover -s tests -v
```

Build the Windows executable from the project folder:

```powershell
./venv/Scripts/python.exe -m PyInstaller --noconfirm --clean PixelForge.spec
```

Run `dist/PixelForge/PixelForge.exe`. Distribute the entire `dist/PixelForge` folder, including `_internal`; the executable needs those bundled files and does not require Python on the receiving computer. This is a portable folder build, not an installer.

The checked-in spec adds `src` to PyInstaller's import search path, includes the app icon and Poppins fonts/license, and copies imageio's distribution metadata. Both imageio's Python modules and its `.dist-info` metadata are needed: imageio looks up its version at startup. A `sys.path` change in `run.py` alone does not tell PyInstaller where to find the package. If building directly from `run.py` instead, include `--paths src` and `--copy-metadata imageio`:

```powershell
./venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --windowed --name PixelForge --paths src --copy-metadata imageio --icon "src/pixelforge/assets/pixelforge.ico" --add-data "src/pixelforge/assets;pixelforge/assets" run.py
```

Prefer building from `PixelForge.spec` so the import path and bundled assets remain consistent. The spec also prevents an unrelated `icuuc.dll` on the build machine's PATH from shadowing the Windows ICU library required by Qt.

For a startup-only check, launch `PixelForge.exe --smoke-test -platform offscreen`. This constructs the real application and exits after its first event-loop iteration without opening a desktop window. Wait for the process and check for exit code 0. Normal launches keep running as usual.

Metadata removal supports JPEG, PNG, WebP, BMP and single-page TIFF. Animated and multi-page files are rejected. JPEG is re-encoded; removing rotation information or colour profiles can affect appearance. Explicitly overwriting an original cannot be undone. Gather currently has no undo action.

Rotation processes supported still images directly in the input folder, without visiting subfolders. Positive angles rotate counterclockwise; negative angles rotate clockwise. Animated and multi-page files are skipped. Rotation resamples pixels and JPEG output is re-encoded. Originals remain in place.

Conversion skips files already using the selected extension and excludes the app's duplicate-review folders. JPG follows the supplied script's RGB conversion and quality 90 setting. Conversions use 8-bit RGB/RGBA; JPG and BMP remove transparency, GIF uses a limited palette, and lossy formats can affect quality. Animated and multi-page files are skipped. Originals are only sent to the Recycle Bin after the new file saves and can be fully decoded; failed conversions keep their originals.
