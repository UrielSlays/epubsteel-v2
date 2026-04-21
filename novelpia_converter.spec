# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

block_cipher = None
python_base = Path(sys.base_prefix)
tcl_root = python_base / "tcl"

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[
        (str(python_base / "DLLs" / "_tkinter.pyd"), "."),
        (str(python_base / "DLLs" / "tcl86t.dll"), "."),
        (str(python_base / "DLLs" / "tk86t.dll"), "."),
    ],
    datas=[
        (str(tcl_root / "tcl8.6"), "_tcl_data"),
        (str(tcl_root / "tk8.6"), "_tk_data"),
    ],
    hiddenimports=[
        "auth",
        "scraper",
        "epub_generator",
        "requests",
        "bs4",
        "lxml",
        "ebooklib",
        "tkinter",
        "_tkinter",
    ],
    hookspath=["pyinstaller_hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="EPUBSteel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
