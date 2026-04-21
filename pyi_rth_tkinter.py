"""
PyInstaller runtime hook for tkinter on Python 3.14/uv installs.
"""

from __future__ import annotations

import os
import sys


if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    base = sys._MEIPASS
    os.environ.setdefault("TCL_LIBRARY", os.path.join(base, "tcl", "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", os.path.join(base, "tcl", "tk8.6"))
