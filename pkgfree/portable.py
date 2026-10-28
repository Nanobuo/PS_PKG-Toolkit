"""Portable mode: settings live in a "PkgFree-data" folder next to the program.

The folder is created at the first start when the program sits in a writable place
(a USB stick, a folder on the desktop...). Otherwise, e.g. in C:\\Program Files, the
settings go to the user profile as before. On macOS portable mode is opt-in: create
the folder next to PkgFree.app by hand.

Folders on the same removable drive as the program are stored relative to it, so they
keep working when the stick gets another drive letter on another PC.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Optional

DATA_DIR = "PkgFree-data"
CONFIG_NAME = "config.json"


def program_dir() -> Optional[str]:
    """Folder holding the program as the user sees it (.exe, AppImage or .app)."""
    from .updater import install_target
    target = install_target()
    return os.path.dirname(target) if target else None


def user_data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "PkgFree")


def portable_data_dir(prog_dir: Optional[str], platform: str = sys.platform) -> Optional[str]:
    """The portable data folder, created if possible; None means "use the user profile"."""
    if not prog_dir:
        return None
    data = os.path.join(prog_dir, DATA_DIR)
    if os.path.isdir(data):
        return data
    if platform == "darwin":
        return None
    try:
        os.mkdir(data)
    except OSError:
        return None
    # First portable start: carry over the settings of an installed copy, if any.
    old = os.path.join(user_data_dir(), CONFIG_NAME)
    if os.path.isfile(old):
        try:
            shutil.copy2(old, os.path.join(data, CONFIG_NAME))
        except OSError:
            pass
    return data


# -- folders relative to the program ------------------------------------------------

def _volume(path: str) -> str:
    """Drive letter on Windows, mount point elsewhere."""
    path = os.path.abspath(path)
    if os.name == "nt":
        return os.path.splitdrive(path)[0].upper()
    while not os.path.ismount(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path


def _system_volumes() -> set:
    if os.name == "nt":
        return {os.environ.get("SystemDrive", "C:").upper()}
    return {"/", _volume(os.path.expanduser("~"))}


def to_stored(path: str, base: Optional[str]) -> str:
    """Path as written to the settings: relative to base when both are on the same
    removable drive (not the system one), absolute otherwise."""
    if not path or not base or not os.path.isabs(path):
        return path
    vol = _volume(base)
    if not vol or vol.startswith("\\\\") or vol != _volume(path) or vol in _system_volumes():
        return path
    try:
        rel = os.path.relpath(path, base)
    except ValueError:
        return path
    return rel.replace("\\", "/")


def from_stored(value: str, base: Optional[str]) -> str:
    if not value or not base or os.path.isabs(value):
        return value
    return os.path.normpath(os.path.join(base, value))
