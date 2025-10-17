# app/utils/zbar_loader.py
import os
import sys
import ctypes
from pathlib import Path


def _candidate_dirs():
    dirs = []
    # 1) PyInstaller temp extraction dir
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass))
        dirs.append(Path(meipass) / "app" / "bin")
    # 2) Next to this file (inside app/bin when installed)
    here = Path(__file__).resolve()
    dirs.append(here.parent.parent / "bin")  # app/bin
    dirs.append(here.parent)  # app/utils
    # 3) Current working directory
    dirs.append(Path.cwd())
    return [d for d in dirs if d and d.exists()]


def ensure_zbar_loaded() -> bool:
    """
    Tries to locate and load the ZBar DLL on Windows and set ZBAR_PATH env var
    so that pyzbar can import successfully. Returns True if a load path was set.
    """
    # If already set, keep it
    if os.environ.get("ZBAR_PATH"):
        return True

    dll_names = [
        "libzbar-64.dll",  # common on Windows x64
        "zbar.dll",
    ]

    for d in _candidate_dirs():
        for name in dll_names:
            dll_path = d / name
            if dll_path.exists():
                # On Python 3.8+, add directory to DLL search path
                try:
                    os.add_dll_directory(str(dll_path.parent))  # type: ignore[attr-defined]
                except Exception:
                    # Fallback: try to preload the DLL
                    try:
                        ctypes.WinDLL(str(dll_path))
                    except Exception:
                        pass
                # Set env var for pyzbar
                os.environ["ZBAR_PATH"] = str(dll_path)
                return True

    return False
