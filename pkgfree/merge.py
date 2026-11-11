"""Merge a base game and its updates into one new game PKG.

Files are read straight from the source PKGs (later updates win), so no temporary
extraction is needed: only the space of the new PKG.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import builder
from .i18n import tr
from .installer import _version_key, safe_folder_name, title_id_of
from .pkg import PkgError, PkgFile
from .sfo import Sfo


@dataclass
class MergeResult:
    content_id: str
    title: str
    version: str
    patches: list[str] = field(default_factory=list)


def output_name(title: str, title_id: str, version: str) -> str:
    """Suggested file name, e.g. "Driveclub [CUSA00003] v01.28.pkg"."""
    name = safe_folder_name(title, title_id)
    return f"{name} [{title_id}] v{version}.pkg" if name != title_id else \
        f"{title_id} v{version}.pkg"


def describe(paths: list[str]) -> tuple[str, str, str]:
    """(title, title ID, final version) of the PKG that merging paths would produce."""
    from .installer import read_info
    infos = [read_info(p) for p in paths]
    base = next((i for i in infos if i.kind == "game"), None)
    if base is None:
        raise PkgError(tr("Serve esattamente un gioco base per creare il PKG (trovati: {n})", n=0))
    versions = [i.app_ver for i in infos if i.kind in ("game", "patch")]
    return base.title, title_id_of(base), max(versions, key=_version_key)


def space_needed(paths: list[str]) -> int:
    """Upper bound of the merged PKG size: the base plus every update."""
    return sum(os.path.getsize(p) for p in paths)


def check_space(paths: list[str], out_path: str) -> Optional[tuple[int, int]]:
    """(needed, free) when the destination disk is too small, else None."""
    needed = space_needed(paths)
    folder = os.path.dirname(os.path.abspath(out_path))
    try:
        free = shutil.disk_usage(folder).free
    except OSError:
        return None
    return (needed, free) if free < needed else None


def merge_pkgs(paths: list[str], out_path: str, log: Callable[[str], None] = lambda s: None,
               progress: Optional[builder.BuildProgress] = None,
               should_cancel: Optional[Callable[[], bool]] = None) -> MergeResult:
    pkgs = [PkgFile(p) for p in paths]
    try:
        base = [p for p in pkgs if p.info.kind == "game"]
        patches = [p for p in pkgs if p.info.kind == "patch"]
        others = [p for p in pkgs if p.info.kind not in ("game", "patch")]
        if others:
            raise PkgError(tr("{name}: solo il gioco base e i suoi aggiornamenti possono essere "
                              "uniti in un PKG (i DLC restano PKG separati)",
                              name=os.path.basename(others[0].path)))
        if len(base) != 1:
            raise PkgError(tr("Serve esattamente un gioco base per creare il PKG (trovati: {n})",
                              n=len(base)))
        base_pkg = base[0]
        tid = title_id_of(base_pkg.info)
        for p in patches:
            if title_id_of(p.info) != tid:
                raise PkgError(tr("{name} è un aggiornamento di un altro gioco ({other})",
                                  name=os.path.basename(p.path), other=title_id_of(p.info)))
            if p.info.is_delta_patch:
                raise PkgError(tr("{name} è una patch delta: non può essere unita",
                                  name=os.path.basename(p.path)))
        patches.sort(key=lambda p: _version_key(p.info.app_ver))

        files: dict[str, builder.SourceFile] = {}
        dirs: set[str] = set()
        for p in [base_pkg] + patches:
            log(tr("Lettura di {name}...", name=os.path.basename(p.path)))
            if p.has_pfs:
                pfs = p.pfs()
                for node in p.list_files(safe_names=False):
                    if node.is_dir:
                        dirs.add(node.path)
                    else:
                        files[node.path] = builder.SourceFile(
                            node.path, node.size, lambda pfs=pfs, node=node: pfs.read_file(node))
            for name, data in p.sce_sys_entries():
                files["sce_sys/" + name] = builder.bytes_source("sce_sys/" + name, data)

        newest = patches[-1] if patches else base_pkg
        raw_sfo = newest.read_entry(0x1000)
        if raw_sfo is None:
            raise PkgError(tr("{name}: param.sfo mancante", name=os.path.basename(newest.path)))
        sfo = Sfo.parse(raw_sfo)
        sfo.set_str("CATEGORY", "gd", 4)
        if not sfo.get("CONTENT_ID"):
            sfo.set_str("CONTENT_ID", base_pkg.info.content_id, 48)
        content_id = builder.build_pkg(list(files.values()), dirs, out_path, sfo=sfo, log=log,
                                       progress=progress, should_cancel=should_cancel)
        return MergeResult(content_id, base_pkg.info.title, str(sfo.get("APP_VER", "")),
                           [p.info.app_ver for p in patches])
    finally:
        for p in pkgs:
            p.close()
