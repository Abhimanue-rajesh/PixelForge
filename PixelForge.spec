# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

project_dir = Path(SPECPATH)

a = Analysis(
    [str(project_dir / 'run.py')],
    pathex=[str(project_dir / 'src')],
    binaries=[],
    datas=[(str(project_dir / 'src/pixelforge/assets'), 'pixelforge/assets')] + copy_metadata('imageio'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt uses Windows' ICU API; do not bundle an unrelated icuuc.dll found on PATH.
a.binaries = [entry for entry in a.binaries if entry[0].lower() != 'icuuc.dll']
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PixelForge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(project_dir / 'src/pixelforge/assets/pixelforge.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PixelForge',
)
