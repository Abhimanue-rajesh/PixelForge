# PixelForge

A desktop toolkit for working with photo folders, built with PySide6 and Pillow.

- **Duplicates:** find byte-identical images, move sets for review, choose a copy to keep, or undo the move.
- **Gather images:** move images from subfolders into the main folder without overwriting filenames.
- **Remove metadata:** rebuild a still image without embedded EXIF, location, comments or colour profiles. Save a separate copy by default, or explicitly overwrite the original.

The interface uses a Windows Settings–inspired sidebar and follows the system light/dark setting. Poppins is bundled with its [SIL Open Font License](src/pixelforge/assets/fonts/OFL.txt), from [Google Fonts](https://github.com/google/fonts/tree/main/ofl/poppins).

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
