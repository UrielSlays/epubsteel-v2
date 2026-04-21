"""
Local override for PyInstaller's tkinter pre-find hook.

PyInstaller 6.19 incorrectly marks tkinter as unavailable on this Python 3.14
uv-managed install, even though importing tkinter works at runtime.
Leaving the search path untouched allows the stdlib tkinter package to be
collected normally.
"""


def pre_find_module_path(hook_api):
    return None
