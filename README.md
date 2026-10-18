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

Metadata removal supports JPEG, PNG, WebP, BMP and single-page TIFF. Animated and multi-page files are rejected. JPEG is re-encoded; removing rotation information or colour profiles can affect appearance. Explicitly overwriting an original cannot be undone. Gather currently has no undo action.

Rotation processes supported still images directly in the input folder, without visiting subfolders. Positive angles rotate counterclockwise; negative angles rotate clockwise. Animated and multi-page files are skipped. Rotation resamples pixels and JPEG output is re-encoded. Originals remain in place.

Conversion skips files already using the selected extension and excludes the app's duplicate-review folders. JPG follows the supplied script's RGB conversion and quality 90 setting. Conversions use 8-bit RGB/RGBA; JPG and BMP remove transparency, GIF uses a limited palette, and lossy formats can affect quality. Animated and multi-page files are skipped. Originals are only sent to the Recycle Bin after the new file saves and can be fully decoded; failed conversions keep their originals.
