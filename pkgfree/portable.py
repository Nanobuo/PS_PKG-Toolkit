"""Portable mode: settings live in a "PS-PKG-Toolkit-data" folder next to the program.

The folder is created at the first start when the program sits in a writable place
(a USB stick, a folder on the desktop...). Otherwise, e.g. in C:\\Program Files, the
settings go to the user profile as before. On macOS portable mode is opt-in: create
the folder next to PS-PKG-Toolkit.app by hand.

Folders on the same removable drive as the program are stored relative to it, so they
keep working when the stick gets another drive letter on another PC.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Optional

DATA_DIR = "PS-PKG-Toolkit-data"
USER_DIR = "PS-PKG-Toolkit"
# Names used up to version 1.5 (when the program was called PKG Free).
LEGACY_DATA_DIR = "PkgFree-data"
LEGACY_USER_DIR = "PkgFree"
CONFIG_NAME = "config.json"


def program_dir() -> Optional[str]:
    """Folder holding the program as the user sees it (.exe, AppImage or .app)."""
    from .updater import install_target
    target = install_target()
    return os.path.dirname(target) if target else None


def _profile_base() -> str:
    return os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")


def user_data_dir() -> str:
    return os.path.join(_profile_base(), USER_DIR)


def carry_over_settings(data_dir: str) -> None:
    """Give a new settings folder the settings of an earlier copy, if there are any."""
    target = os.path.join(data_dir, CONFIG_NAME)
    if os.path.exists(target):
        return
    for folder in (user_data_dir(), os.path.join(_profile_base(), LEGACY_USER_DIR)):
        old = os.path.join(folder, CONFIG_NAME)
        if os.path.normcase(os.path.abspath(old)) == os.path.normcase(os.path.abspath(target)):
            continue
        if os.path.isfile(old):
            try:
                os.makedirs(data_dir, exist_ok=True)
                shutil.copy2(old, target)
            except OSError:
                pass
            return


def portable_data_dir(prog_dir: Optional[str], platform: str = sys.platform) -> Optional[str]:
    """The portable data folder, created if possible; None means "use the user profile"."""
    if not prog_dir:
        return None
    data = os.path.join(prog_dir, DATA_DIR)
    if os.path.isdir(data):
        return data
    legacy = os.path.join(prog_dir, LEGACY_DATA_DIR)
    if os.path.isdir(legacy):
        try:
            os.rename(legacy, data)
            return data
        except OSError:
            return legacy
    if platform == "darwin":
        return None
    try:
        os.mkdir(data)
    except OSError:
        return None
    # First portable start: carry over the settings of an installed copy, if any.
    carry_over_settings(data)
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
