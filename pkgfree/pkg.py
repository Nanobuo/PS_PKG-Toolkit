"""Reader/extractor for PS4 fake PKG files (fPKG).

Format notes come from the (GPL) PKG extractor that shipped with shadPS4 and from
LibOrbisPkg. Layout of a PKG:

* a big-endian header followed by a table of metadata entries (param.sfo, icon0.png,
  npbind.dat, ...) that end up in ``sce_sys/``;
* an AES-XTS encrypted "outer" PFS image that contains a single zlib-compressed
  (PFSC) "inner" PFS image, which holds the actual game files under ``uroot``.
"""

from __future__ import annotations

import hashlib
import os
import struct
import sys
import zlib
from array import array
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from . import crypto
from .entry_names import ENTRY_NAMES
from .i18n import tr
from .sfo import parse_sfo

PKG_MAGIC = 0x7F434E54
PFSC_MAGIC = b"PFSC"

PFS_FILE = 2
PFS_DIR = 3
PFS_CURRENT_DIR = 4
PFS_PARENT_DIR = 5

PFS_MODE_SIGNED = 0x1
PFS_MODE_64BIT = 0x2
PFS_MODE_ENCRYPTED = 0x4

INODE_SIZE_D32 = 0xA8

# PKG header pfs_image_flags bit: the EKPFS is first hashed with the seed.
PFS_FLAG_NEW_CRYPT = 0x2000000000000000

SUPERROOT_INODE = 0

# pfs_image.dat (the PFSC image) is the only file of the outer PFS and starts
# right after its few metadata blocks; shadPS4 only looked at the first few MB.
PFSC_SCAN_LIMIT = 1 << 30
PFSC_FINE_SCAN_LIMIT = 64 << 20

ENTRY_KEYS_ID = 0x10
IMAGE_KEY_ID = 0x20
PARAM_SFO_ID = 0x1000
ICON0_ID = 0x1200

CONTENT_FLAG_DELTA_PATCH = 0x41000000

# Number of inner blocks (0x10000 each) read with a single I/O + decrypt call.
READ_BATCH_BLOCKS = 64

ProgressCallback = Callable[[int, int, str], None]
# (bytes_done, bytes_total)
ByteProgress = Callable[[int, int], None]

HASH_CHUNK = 8 << 20


@dataclass
class DigestCheck:
    name: str     # "header", "body" or "pfs"
    status: str   # "ok", "mismatch" or "absent" (digest not stored in the PKG)


class PkgError(Exception):
    pass


class Cancelled(Exception):
    pass


@dataclass
class PkgEntry:
    id: int
    filename_offset: int
    flags1: int
    flags2: int
    offset: int
    size: int
    raw: bytes  # the 32-byte table record as used for key derivation

    @property
    def encrypted(self) -> bool:
        return bool(self.flags1 & 0x80000000)

    @property
    def key_index(self) -> int:
        return (self.flags2 & 0xF000) >> 12


@dataclass
class PfsNode:
    path: str  # relative path, '/' separated
    inode: int
    is_dir: bool
    size: int = 0
    loc: int = 0


@dataclass
class PkgInfo:
    path: str
    content_id: str
    title_id: str
    content_type: int
    content_flags: int
    pfs_image_flags: int
    pfs_image_offset: int
    pfs_image_size: int
    sfo: dict = field(default_factory=dict)

    @property
    def category(self) -> str:
        return str(self.sfo.get("CATEGORY", "")).lower()

    @property
    def kind(self) -> str:
        """'game', 'patch', 'dlc' or 'other'."""
        cat = self.category
        if cat.startswith("gd"):
            return "game"
        if cat == "gp":
            return "patch"
        if cat.startswith("ac"):
            return "dlc"
        return "other"

    @property
    def app_ver(self) -> str:
        return str(self.sfo.get("APP_VER", ""))

    @property
    def version(self) -> str:
        return str(self.sfo.get("VERSION", ""))

    @property
    def title(self) -> str:
        return str(self.sfo.get("TITLE", ""))

    @property
    def entitlement_label(self) -> str:
        return self.content_id[20:].rstrip("\x00")

    @property
    def is_delta_patch(self) -> bool:
        return (self.content_flags & CONTENT_FLAG_DELTA_PATCH) == CONTENT_FLAG_DELTA_PATCH


_WINDOWS_INVALID = str.maketrans({c: "_" for c in '<>:"|?*'})


def _safe_name(name: str) -> str:
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
        raise PkgError(tr("Nome file non valido nel PKG: {name}", name=repr(name)))
    if os.name == "nt":
        name = name.translate(_WINDOWS_INVALID).rstrip(" .") or "_"
    return name


def long_path(path: str) -> str:
    """Allow paths longer than MAX_PATH on Windows."""
    path = os.path.abspath(path)
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        if path.startswith("\\\\"):
            return "\\\\?\\UNC\\" + path[2:]
        return "\\\\?\\" + path
    return path


class PkgFile:
    def __init__(self, path: str):
        self.path = path
        self._f = open(path, "rb")
        try:
            self._parse_header()
        except Exception:
            self._f.close()
            raise
        self._dk3: Optional[bytes] = None
        self._pfs: Optional[_PfsReader] = None

    # -- context manager -------------------------------------------------
    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "PkgFile":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- header ------------------------------------------------------------
    def _read_at(self, offset: int, size: int) -> bytes:
        self._f.seek(offset)
        data = self._f.read(size)
        if len(data) != size:
            raise PkgError(tr("Fine del file inattesa: il PKG è incompleto o danneggiato"))
        return data

    def _parse_header(self) -> None:
        hdr = self._read_at(0, 0x440)
        magic, = struct.unpack_from(">I", hdr, 0)
        if magic != PKG_MAGIC:
            raise PkgError(tr("Non è un file PKG PS4 valido"))
        entry_count, = struct.unpack_from(">I", hdr, 0x10)
        table_offset, = struct.unpack_from(">I", hdr, 0x18)
        content_id = hdr[0x40:0x64].split(b"\x00", 1)[0].decode("ascii", "replace")
        content_type, content_flags = struct.unpack_from(">II", hdr, 0x74)
        pfs_flags, pfs_offset, pfs_size = struct.unpack_from(">QQQ", hdr, 0x408)
        pkg_size, = struct.unpack_from(">Q", hdr, 0x430)

        file_size = os.fstat(self._f.fileno()).st_size
        if pkg_size and pkg_size > file_size:
            raise PkgError(tr("Il PKG è incompleto (dimensione inferiore a quella dichiarata)"))

        self.entries: list[PkgEntry] = []
        table = self._read_at(table_offset, entry_count * 32)
        for i in range(entry_count):
            rec = table[i * 32:(i + 1) * 32]
            eid, name_off, f1, f2, off, size = struct.unpack_from(">IIIIII", rec)
            raw = rec[:24] + b"\x00" * 8
            self.entries.append(PkgEntry(eid, name_off, f1, f2, off, size, raw))

        sfo = {}
        sfo_entry = self.entry(PARAM_SFO_ID)
        if sfo_entry is not None:
            try:
                sfo = parse_sfo(self._read_at(sfo_entry.offset, sfo_entry.size))
            except ValueError:
                sfo = {}

        self.info = PkgInfo(
            path=self.path,
            content_id=content_id,
            title_id=content_id[7:16],
            content_type=content_type,
            content_flags=content_flags,
            pfs_image_flags=pfs_flags,
            pfs_image_offset=pfs_offset,
            pfs_image_size=pfs_size,
            sfo=sfo,
        )

    def entry(self, entry_id: int) -> Optional[PkgEntry]:
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None

    def read_entry(self, entry_id: int) -> Optional[bytes]:
        """Raw data of an unencrypted header entry (e.g. ICON0_ID), or None."""
        e = self.entry(entry_id)
        if e is None or e.encrypted:
            return None
        return self._read_at(e.offset, e.size)

    # -- keys ----------------------------------------------------------------
    def _get_dk3(self) -> bytes:
        if self._dk3 is None:
            e = self.entry(ENTRY_KEYS_ID)
            if e is None:
                raise PkgError(tr("Il PKG non contiene la tabella delle chiavi"))
            # seed digest (32) + 7 digests (7*32) + 7 RSA-encrypted keys (7*256); we need key #3
            enc = self._read_at(e.offset + 32 + 7 * 32 + 3 * 256, 256)
            try:
                self._dk3 = crypto.decrypt_dk3(enc)
            except crypto.CryptoError as ex:
                raise PkgError(tr(
                    "Impossibile decifrare il PKG: sono supportati solo i PKG 'fake' (fPKG). "
                    "({error})", error=ex)) from ex
        return self._dk3

    def _get_ekpfs(self) -> bytes:
        e = self.entry(IMAGE_KEY_ID)
        if e is None:
            raise PkgError(tr("Il PKG non contiene la chiave dell'immagine PFS"))
        iv_key = crypto.entry_iv_key(e.raw, self._get_dk3())
        img_key = crypto.aes_cbc_decrypt(iv_key, self._read_at(e.offset, 256))
        try:
            return crypto.decrypt_ekpfs(img_key)
        except crypto.CryptoError as ex:
            raise PkgError(tr(
                "Impossibile decifrare la chiave PFS: sono supportati solo i PKG 'fake' (fPKG). "
                "({error})", error=ex)) from ex

    # -- sce_sys metadata ------------------------------------------------------
    def sce_sys_entries(self) -> Iterator[tuple[str, bytes]]:
        """(name, data) of the header entries that belong in sce_sys (param.sfo, icons...)."""
        for e in self.entries:
            if e.id < 0x400:  # digests / keys / internal tables
                continue
            name = ENTRY_NAMES.get(e.id)
            if not name:
                continue
            data = self._read_at(e.offset, e.size)
            if e.encrypted:
                if e.key_index != 3:
                    continue  # bound to console keys, useless for the emulator
                iv_key = crypto.entry_iv_key(e.raw, self._get_dk3())
                data = crypto.aes_cbc_decrypt(iv_key, data)
            yield name, data

    def extract_sce_sys(self, dest_dir: str) -> list[str]:
        """Write the PKG header entries (param.sfo, icons, npbind.dat...) to dest_dir/sce_sys."""
        written = []
        sce_sys = os.path.join(dest_dir, "sce_sys")
        for name, data in self.sce_sys_entries():
            out = os.path.join(sce_sys, *name.split("/"))
            os.makedirs(long_path(os.path.dirname(out)), exist_ok=True)
            with open(long_path(out), "wb") as f:
                f.write(data)
            written.append(name)
        return written

    # -- PFS -----------------------------------------------------------------
    @property
    def has_pfs(self) -> bool:
        return self.info.pfs_image_size > 0 and self.info.pfs_image_offset > 0

    def pfs(self) -> "_PfsReader":
        if self._pfs is None:
            if not self.has_pfs:
                raise PkgError(tr("Il PKG non contiene file di gioco"))
            self._pfs = _PfsReader(self)
        return self._pfs

    def list_files(self, safe_names: bool = True) -> list[PfsNode]:
        """Files and folders of the game; safe_names replaces characters Windows rejects."""
        if not self.has_pfs:
            return []
        return list(self.pfs().walk(safe_names))

    # -- integrity -------------------------------------------------------------
    def _hash_range(self, offset: int, size: int, progress, base: int, total: int,
                    should_cancel) -> bytes:
        h = hashlib.sha256()
        self._f.seek(offset)
        left = size
        while left > 0:
            if should_cancel and should_cancel():
                raise Cancelled()
            chunk = self._f.read(min(HASH_CHUNK, left))
            if not chunk:
                raise PkgError(tr("Fine del file inattesa: il PKG è incompleto o danneggiato"))
            h.update(chunk)
            left -= len(chunk)
            if progress:
                progress(base + size - left, total)
        return h.digest()

    def verify(
        self,
        progress: Optional[ByteProgress] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> list[DigestCheck]:
        """Check the SHA-256 digests stored in the PKG header.

        header: bytes 0..0xFE0; body: the metadata entries; pfs: the whole game
        image (reads the entire file). An all-zero digest means "not stored".
        """
        hdr = self._read_at(0, 0x1000)
        body_off, body_size = struct.unpack_from(">QQ", hdr, 0x20)
        checks = [
            ("header", 0, 0xFE0, hdr[0xFE0:0x1000]),
            ("body", body_off, body_size, hdr[0x160:0x180]),
            ("pfs", self.info.pfs_image_offset, self.info.pfs_image_size, hdr[0x440:0x460]),
        ]
        todo = [c for c in checks if any(c[3]) and c[2] > 0]
        total = sum(c[2] for c in todo)
        done = 0
        results = []
        for name, off, size, expected in checks:
            if (name, off, size, expected) not in todo:
                results.append(DigestCheck(name, "absent"))
                continue
            digest = self._hash_range(off, size, progress, done, total, should_cancel)
            done += size
            results.append(DigestCheck(name, "ok" if digest == expected else "mismatch"))
        return results

    # -- extraction ----------------------------------------------------------------
    def extract(
        self,
        dest_dir: str,
        progress: Optional[ProgressCallback] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        skip: Optional[set] = None,
        on_file_done: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Extract the game files (uroot) and sce_sys metadata into dest_dir.

        Existing files are overwritten, so extracting an update on top of the base
        game produces a merged, up-to-date folder. Files listed in ``skip`` that
        already exist with the right size are left alone (resuming an interrupted
        extraction); ``on_file_done`` is called with each file finished. Returns
        the number of bytes skipped.
        """
        os.makedirs(long_path(dest_dir), exist_ok=True)
        nodes = self.list_files()
        total = sum(n.size for n in nodes if not n.is_dir)
        done = 0
        skipped = 0
        for node in nodes:
            if should_cancel and should_cancel():
                raise Cancelled()
            target = os.path.join(dest_dir, *node.path.split("/"))
            if node.is_dir:
                os.makedirs(long_path(target), exist_ok=True)
                continue
            if skip and node.path in skip:
                try:
                    if os.path.getsize(long_path(target)) == node.size:
                        done += node.size
                        skipped += node.size
                        continue
                except OSError:
                    pass
            os.makedirs(long_path(os.path.dirname(target)), exist_ok=True)
            if progress:
                progress(done, total, node.path)
            with open(long_path(target), "wb") as out:
                for chunk in self._pfs.read_file(node):
                    if should_cancel and should_cancel():
                        raise Cancelled()
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total, node.path)
            if on_file_done:
                on_file_done(node.path)
        # Header entries last: an update's param.sfo must win over the PFS copy.
        self.extract_sce_sys(dest_dir)
        if progress:
            progress(total, total, "")
        return skipped


class _PfsReader:
    """Random access to the inner (decompressed) PFS image of a PKG."""

    def __init__(self, pkg: PkgFile):
        self._pkg = pkg
        self._base = pkg.info.pfs_image_offset
        self._size = pkg.info.pfs_image_size

        outer_hdr = pkg._read_at(self._base, 0x380)
        self.outer_mode, = struct.unpack_from("<H", outer_hdr, 0x1C)
        bs, = struct.unpack_from("<i", outer_hdr, 0x20)
        self.outer_block_size = bs if 0x1000 <= bs <= 0x100000 and bs % 0x1000 == 0 else 0x10000
        self._xts: Optional[crypto.XtsDecryptor] = None
        self._pfsc = self._locate(outer_hdr[0x370:0x380])
        hdr = self._read(self._pfsc, 0x30)
        self._block_size, = struct.unpack_from("<Q", hdr, 0x10)
        block_offsets, = struct.unpack_from("<Q", hdr, 0x18)
        data_length, = struct.unpack_from("<Q", hdr, 0x28)
        if self._block_size == 0 or self._block_size > 0x100000:
            raise PkgError(tr("Intestazione PFSC non valida"))
        n_blocks = (data_length + self._block_size - 1) // self._block_size
        self._map = array("Q")
        self._map.frombytes(self._read(self._pfsc + block_offsets, (n_blocks + 1) * 8))
        if sys.byteorder != "little":
            self._map.byteswap()
        self._n_blocks = n_blocks

        sb = self.read_blocks(0, 1)
        inner_mode, = struct.unpack_from("<H", sb, 0x1C)
        inner_bs, = struct.unpack_from("<i", sb, 0x20)
        if inner_bs != self._block_size:
            raise PkgError(tr("Dimensione blocco PFS interna inattesa"))
        if inner_mode & (PFS_MODE_SIGNED | PFS_MODE_64BIT):
            raise PkgError(tr("Formato PFS interno non supportato (mode=0x{mode:X})", mode=inner_mode))
        self._inodes_per_block = self._block_size // INODE_SIZE_D32
        self._inode_cache: dict[int, bytes] = {}

    # -- raw access to the outer image ------------------------------------------
    def _read(self, offset: int, size: int) -> bytes:
        """Read (and decrypt) bytes from the outer PFS image."""
        if self._xts is None:
            return self._pkg._read_at(self._base + offset, size)
        start = offset & ~(crypto.XTS_SECTOR_SIZE - 1)
        end = (offset + size + crypto.XTS_SECTOR_SIZE - 1) & ~(crypto.XTS_SECTOR_SIZE - 1)
        enc = self._pkg._read_at(self._base + start, end - start)
        dec = self._xts.decrypt(enc, start // crypto.XTS_SECTOR_SIZE)
        return dec[offset - start:offset - start + size]

    def _key_candidates(self, seed: bytes) -> list[tuple[str, Optional[crypto.XtsDecryptor]]]:
        """Ways the outer image may be protected, most likely first.

        Two key derivations exist ("new crypt" hashes the EKPFS with the seed
        first). Which one a PKG uses is signalled by a header flag, but not
        every tool sets it consistently, so both are tried.
        """
        cands: list[tuple[str, Optional[crypto.XtsDecryptor]]] = []
        if not self.outer_mode & PFS_MODE_ENCRYPTED:
            cands.append((tr("in chiaro"), None))
        ekpfs = self._pkg._get_ekpfs()
        flag = bool(self._pkg.info.pfs_image_flags & PFS_FLAG_NEW_CRYPT)
        for new_crypt in (flag, not flag):
            data_key, tweak_key = crypto.pfs_gen_crypto_key(ekpfs, seed, new_crypt)
            name = tr("chiave 'new crypt'") if new_crypt else tr("chiave classica")
            cands.append((name, crypto.XtsDecryptor(data_key, tweak_key)))
        if self.outer_mode & PFS_MODE_ENCRYPTED:
            cands.append((tr("in chiaro"), None))
        return cands

    def _superroot_ok(self) -> bool:
        """The first inode of the outer image (the superroot) must be a directory."""
        data = self._read(self.outer_block_size, 0x20)
        mode, nlink = struct.unpack_from("<HH", data, 0)
        size, = struct.unpack_from("<q", data, 8)
        return (mode & 0xF000) == 0x4000 and 0 < nlink < 0x10000 and 0 < size < (1 << 40)

    def _scan_pfsc(self, step: int, limit: int) -> Optional[int]:
        start = self.outer_block_size
        for off in range(start, min(self._size, limit), step):
            if self._read(off, 4) == PFSC_MAGIC:
                return off
        return None

    def _locate(self, seed: bytes) -> int:
        cands = self._key_candidates(seed)
        # Prefer a key that yields a sane superroot inode, then look for the PFSC image.
        valid = []
        for name, xts in cands:
            self._xts = xts
            try:
                if self._superroot_ok():
                    valid.append((name, xts))
            except PkgError:
                pass
        tried = []
        for name, xts in valid or cands:
            self._xts = xts
            off = self._scan_pfsc(self.outer_block_size, PFSC_SCAN_LIMIT)
            if off is None:
                # Unusual alignment: look at every XTS sector of the first part.
                off = self._scan_pfsc(crypto.XTS_SECTOR_SIZE, PFSC_FINE_SCAN_LIMIT)
            if off is not None:
                self.key_used = name
                return off
            tried.append(name)
        flags = self._pkg.info.pfs_image_flags
        raise PkgError(tr(
            "Immagine PFSC non trovata: PKG non supportato o danneggiato "
            "(mode=0x{mode:X}, flags=0x{flags:016X}, blocco=0x{block:X}, chiave valida: "
            "{valid}; provate: {tried})",
            mode=self.outer_mode, flags=flags, block=self.outer_block_size,
            valid=", ".join(n for n, _ in valid) or tr("nessuna"), tried=", ".join(tried)))

    # -- inner image -------------------------------------------------------------
    def read_blocks(self, first: int, count: int) -> bytes:
        if first < 0 or first + count > self._n_blocks:
            raise PkgError(tr("Riferimento a blocco PFS fuori dai limiti"))
        bs = self._block_size
        start = self._map[first]
        raw = self._read(self._pfsc + start, self._map[first + count] - start)
        out = bytearray()
        for i in range(first, first + count):
            a, b = self._map[i] - start, self._map[i + 1] - start
            chunk = raw[a:b]
            if len(chunk) >= bs:
                block = chunk[:bs]
            elif len(chunk) == 0:
                block = bytes(bs)
            else:
                try:
                    block = zlib.decompress(chunk)
                except zlib.error as ex:
                    raise PkgError(tr("Blocco compresso danneggiato ({error})", error=ex)) from ex
                if len(block) < bs:
                    block += bytes(bs - len(block))
            out += block
        return bytes(out)

    def _inode(self, ino: int) -> tuple[int, int, int, int]:
        """Return (mode, size, blocks, loc) for an inode number."""
        blk = 1 + ino // self._inodes_per_block
        if blk not in self._inode_cache:
            self._inode_cache[blk] = self.read_blocks(blk, 1)
        off = (ino % self._inodes_per_block) * INODE_SIZE_D32
        data = self._inode_cache[blk]
        mode, = struct.unpack_from("<H", data, off)
        size, = struct.unpack_from("<q", data, off + 0x08)
        blocks, loc = struct.unpack_from("<II", data, off + 0x60)
        return mode, size, blocks, loc

    def _dirents(self, ino: int) -> Iterator[tuple[str, int, int]]:
        _, size, blocks, loc = self._inode(ino)
        n = blocks or (size + self._block_size - 1) // self._block_size
        for b in range(n):
            data = self.read_blocks(loc + b, 1)
            pos = 0
            while pos + 16 <= len(data):
                d_ino, d_type, namelen, entsize = struct.unpack_from("<iiii", data, pos)
                if entsize <= 0 or namelen < 0 or pos + 16 + namelen > len(data):
                    break
                name = data[pos + 16:pos + 16 + namelen].decode("utf-8", "replace")
                pos += entsize
                if d_ino > 0 and d_type in (PFS_FILE, PFS_DIR):
                    yield name, d_ino, d_type

    def walk(self, safe_names: bool = True) -> Iterator[PfsNode]:
        uroot = None
        for name, ino, typ in self._dirents(SUPERROOT_INODE):
            if name == "uroot" and typ == PFS_DIR:
                uroot = ino
        if uroot is None:
            raise PkgError(tr("Cartella 'uroot' non trovata nel PFS"))
        stack = [("", uroot)]
        seen = {uroot}
        while stack:
            prefix, dir_ino = stack.pop()
            for name, ino, typ in self._dirents(dir_ino):
                path = prefix + (_safe_name(name) if safe_names else name)
                if typ == PFS_DIR:
                    if ino in seen:
                        continue
                    seen.add(ino)
                    yield PfsNode(path, ino, True)
                    stack.append((path + "/", ino))
                else:
                    _, size, _, loc = self._inode(ino)
                    yield PfsNode(path, ino, False, size, loc)

    def read_file(self, node: PfsNode) -> Iterator[bytes]:
        remaining = node.size
        block = node.loc
        while remaining > 0:
            n = min(READ_BATCH_BLOCKS, (remaining + self._block_size - 1) // self._block_size)
            data = self.read_blocks(block, n)
            take = min(remaining, len(data))
            yield data[:take]
            remaining -= take
            block += n
