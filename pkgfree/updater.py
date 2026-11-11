"""In-app update: look for a newer GitHub release, download it, swap it in, restart.

Supported for the published builds only (PyInstaller): the Windows .exe, the Linux
AppImage and the macOS .app. Running from source, the user is pointed to the page.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from . import __version__
from .i18n import tr
from .installer import _version_key

REPO = "Nanobuo/Pkg-free"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
CHUNK = 1 << 20


class UpdateError(Exception):
    pass


@dataclass
class Release:
    version: str        # "1.4.0"
    tag: str            # "v1.4.0"
    notes: str          # release description (Markdown)
    page_url: str
    asset_name: Optional[str] = None
    asset_url: Optional[str] = None
    asset_size: int = 0
    asset_sha256: Optional[str] = None


def asset_name(platform: str = sys.platform) -> Optional[str]:
    """Name of the release file for this platform (same names on every release)."""
    if platform.startswith("win"):
        return "PS-PKG-Toolkit-windows-x64.exe"
    if platform.startswith("linux"):
        return "PS-PKG-Toolkit-linux-x86_64.AppImage"
    if platform == "darwin":
        return "PS-PKG-Toolkit-macos-arm64.zip"
    return None


def is_newer(latest: str, current: str = __version__) -> bool:
    return _version_key(latest) > _version_key(current)


def release_from_json(data: dict, platform: str = sys.platform) -> Release:
    tag = str(data.get("tag_name") or "")
    release = Release(version=tag.lstrip("vV"), tag=tag, notes=str(data.get("body") or ""),
                      page_url=str(data.get("html_url") or RELEASES_PAGE))
    wanted = asset_name(platform)
    for asset in data.get("assets") or []:
        if asset.get("name") == wanted:
            release.asset_name = wanted
            release.asset_url = asset.get("browser_download_url")
            release.asset_size = int(asset.get("size") or 0)
            digest = str(asset.get("digest") or "")
            if digest.startswith("sha256:"):
                release.asset_sha256 = digest.split(":", 1)[1].lower()
    return release


def _open(url: str, timeout: float):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"PS-PKG-Toolkit/{__version__}",
    })
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_latest(url: str = API_URL, timeout: float = 10) -> Release:
    try:
        with _open(url, timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            raise UpdateError(tr("Nessuna release trovata (il repository potrebbe essere "
                                 "privato).")) from ex
        raise UpdateError(tr("GitHub ha risposto con l'errore {code}.", code=ex.code)) from ex
    except (urllib.error.URLError, OSError, ValueError) as ex:
        raise UpdateError(tr("Impossibile contattare GitHub: {error}", error=ex)) from ex
    return release_from_json(data)


# -- where the running program lives -------------------------------------------------

def install_target() -> Optional[str]:
    """File (or .app bundle) to replace, or None when self-update is not possible."""
    if not getattr(sys, "frozen", False):
        return None
    if sys.platform.startswith("win"):
        return sys.executable
    if sys.platform.startswith("linux"):
        return os.environ.get("APPIMAGE") or None
    if sys.platform == "darwin":
        # .../PS-PKG-Toolkit.app/Contents/MacOS/PS-PKG-Toolkit
        bundle = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
        return bundle if bundle.endswith(".app") else None
    return None


def cleanup_previous(target: Optional[str] = None) -> None:
    """Remove what the last update left behind (the old .exe or .app)."""
    target = target or install_target()
    if not target:
        return
    old = target + ".old"
    try:
        if os.path.isdir(old):
            shutil.rmtree(old)
        elif os.path.exists(old):
            os.remove(old)
    except OSError:
        pass


# -- download and swap --------------------------------------------------------------

def download(release: Release, dest: str,
             progress: Optional[Callable[[int, int], None]] = None,
             should_cancel: Optional[Callable[[], bool]] = None,
             timeout: float = 30) -> str:
    """Download the release file to dest and check its SHA-256 (when GitHub provides it)."""
    if not release.asset_url:
        raise UpdateError(tr("Questa release non contiene il file per il tuo sistema."))
    h = hashlib.sha256()
    done = 0
    try:
        with _open(release.asset_url, timeout) as resp, open(dest, "wb") as out:
            total = int(resp.headers.get("Content-Length") or release.asset_size or 0)
            while True:
                if should_cancel and should_cancel():
                    raise UpdateError(tr("Aggiornamento annullato."))
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if release.asset_size and done != release.asset_size:
            raise UpdateError(tr("Download incompleto."))
        if release.asset_sha256 and h.hexdigest() != release.asset_sha256:
            raise UpdateError(tr("Il file scaricato è danneggiato (SHA-256 diverso)."))
    except UpdateError:
        _remove(dest)
        raise
    except (urllib.error.URLError, OSError) as ex:
        _remove(dest)
        raise UpdateError(tr("Download non riuscito: {error}", error=ex)) from ex
    return dest


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def staging_path(target: str) -> str:
    """Where to download: next to the target, so the final rename stays on one disk."""
    return os.path.join(os.path.dirname(target), f".{os.path.basename(target)}.download")


def apply_update(downloaded: str, target: str, platform: str = sys.platform) -> None:
    """Swap the downloaded build in place of target. The running copy keeps working."""
    if platform == "darwin":
        _apply_macos(downloaded, target)
    elif platform.startswith("win"):
        # A running .exe cannot be overwritten but can be renamed.
        old = target + ".old"
        _remove(old)
        os.replace(target, old)
        os.replace(downloaded, target)
    else:
        os.chmod(downloaded, 0o755)
        os.replace(downloaded, target)


def _apply_macos(zip_path: str, bundle: str) -> None:
    work = tempfile.mkdtemp(prefix=".pkgfree-update-", dir=os.path.dirname(bundle))
    try:
        subprocess.run(["ditto", "-x", "-k", zip_path, work], check=True)
        new_app = os.path.join(work, os.path.basename(bundle))
        if not os.path.isdir(new_app):
            apps = [d for d in os.listdir(work) if d.endswith(".app")]
            if not apps:
                raise UpdateError(tr("Lo zip scaricato non contiene l'app."))
            new_app = os.path.join(work, apps[0])
        old = bundle + ".old"
        shutil.rmtree(old, ignore_errors=True)
        os.rename(bundle, old)
        shutil.move(new_app, bundle)
        shutil.rmtree(old, ignore_errors=True)
    except (OSError, subprocess.CalledProcessError) as ex:
        raise UpdateError(tr("Installazione dell'aggiornamento non riuscita: {error}",
                             error=ex)) from ex
    finally:
        shutil.rmtree(work, ignore_errors=True)
        _remove(zip_path)


def relaunch(target: str, platform: str = sys.platform) -> None:
    """Start the updated program; the caller then quits."""
    env = dict(os.environ)
    # A PyInstaller program started by another one must unpack itself afresh.
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    if platform == "darwin":
        subprocess.Popen(["open", "-n", target], env=env)
    elif platform.startswith("win"):
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([target], env=env, creationflags=flags, close_fds=True)
    else:
        subprocess.Popen([target], env=env, start_new_session=True, close_fds=True)
