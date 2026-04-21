# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

python_base = Path(sys.base_prefix)
tcl_root = python_base / 'tcl'

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[
        (str(python_base / 'DLLs' / '_tkinter.pyd'), '.'),
        (str(python_base / 'DLLs' / 'tcl86t.dll'), '.'),
        (str(python_base / 'DLLs' / 'tk86t.dll'), '.'),
    ],
    datas=[
        (str(tcl_root / 'tcl8.6'), 'tcl/tcl8.6'),
        (str(tcl_root / 'tk8.6'), 'tcl/tk8.6'),
    ],
    hiddenimports=['tkinter', '_tkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_tkinter.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EPUBSteel',
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
