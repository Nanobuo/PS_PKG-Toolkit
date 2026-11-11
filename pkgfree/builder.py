"""Build a fake PKG (fPKG) for jailbroken consoles: the reverse of extraction.

The layout follows LibOrbisPkg's PkgBuilder (https://github.com/maxton/LibOrbisPkg,
LGPL-3.0): an unencrypted inner PFS holding the game files, stored uncompressed in a
PFSC container that is the single file of a signed, AES-XTS encrypted outer PFS; the PKG
body holds param.sfo, icons and the other sce_sys entries, a debug license and the
keys, all encrypted with the well-known "fake" keys and an all-zero passcode.

Only game packages (CATEGORY "gd") are built. Files come from SourceFile objects so a
package can be produced straight from other PKGs without extracting them to disk.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import struct
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Optional

from . import build_keys, crypto, keys
from .entry_names import ENTRY_NAMES
from .i18n import tr
from .pkg import Cancelled, PkgError, long_path
from .sfo import Sfo

BLOCK = 0x10000
SECTORS_PER_BLOCK = BLOCK // crypto.XTS_SECTOR_SIZE
PASSCODE = "0" * 32
SIG_SIZE = 36  # HMAC-SHA256 + 32-bit block number
SIGS_PER_BLOCK = BLOCK // SIG_SIZE
DIRENT_MAX = 280

INODE_D32 = 0xA8
INODE_S32 = 0x2C8
MODE_DIR = 0x4000 | 0x16D  # directory, r-x for everyone
MODE_FILE = 0x8000 | 0x16D
FLAG_COMPRESSED = 0x1
FLAG_UNK2 = 0x4
FLAG_UNK3 = 0x8
FLAG_READONLY = 0x10
FLAG_INTERNAL = 0x20000
DT_FILE, DT_DIR, DT_DOT, DT_DOTDOT = 2, 3, 4, 5

CONTENT_TYPE_GD = 0x1A
DRM_PS4 = 0xF
CONTENT_FLAGS_GD = 0x08000000 | 0x02000000

E_DIGESTS = 0x1
E_ENTRY_KEYS = 0x10
E_IMAGE_KEY = 0x20
E_GENERAL_DIGESTS = 0x80
E_METAS = 0x100
E_ENTRY_NAMES = 0x200
E_LICENSE_DAT = 0x400
E_LICENSE_INFO = 0x401
E_PSRESERVED = 0x409
E_PARAM_SFO = 0x1000
E_CHUNK_DAT = 0x1001
E_CHUNK_SHA = 0x1002
E_CHUNK_XML = 0x1003

# sce_sys files that become PKG entries. The ones generated here, or that only make
# sense in the original package (delta patch info), are left out.
_REGENERATED = {E_LICENSE_DAT, E_LICENSE_INFO, E_PSRESERVED, E_PARAM_SFO, E_CHUNK_DAT,
                E_CHUNK_SHA, E_CHUNK_XML, 0x407, 0x408}
ENTRY_FILES = {name: eid for eid, name in ENTRY_NAMES.items()
               if eid >= 0x400 and eid not in _REGENERATED}
SKIPPED_SCE_SYS = {ENTRY_NAMES[eid] for eid in _REGENERATED if eid in ENTRY_NAMES}

PLAYGO_MANIFEST = (
    b"\xef\xbb\xbf<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\"?>\r\n"
    b"<psproject fmt=\"playgo-manifest\" version=\"0990\">\r\n"
    b"  <volume>\r\n"
    b"    <chunk_info chunk_count=\"1\" scenario_count=\"1\">\r\n"
    b"      <scenarios default_id=\"0\">\r\n"
    b"        <scenario id=\"0\" type=\"sp\" initial_chunk_count=\"1\" "
    b"label=\"Scenario #0\">0</scenario>\r\n"
    b"      </scenarios>\r\n"
    b"    </chunk_info>\r\n"
    b"  </volume>\r\n"
    b"</psproject>\r\n")

BuildProgress = Callable[[int, int, str], None]  # done bytes, total bytes, what is happening


@dataclass
class SourceFile:
    """A file of the package: path relative to the game root ("sce_sys/icon0.png")."""
    path: str
    size: int
    read: Callable[[], Iterable[bytes]]


def file_source(path: str, rel: str) -> SourceFile:
    def read() -> Iterator[bytes]:
        with open(long_path(path), "rb") as f:
            while True:
                chunk = f.read(4 << 20)
                if not chunk:
                    return
                yield chunk
    return SourceFile(rel, os.path.getsize(long_path(path)), read)


def bytes_source(rel: str, data: bytes) -> SourceFile:
    return SourceFile(rel, len(data), lambda: [data])


def folder_sources(folder: str) -> tuple[list[SourceFile], set[str]]:
    """Files and directories of an extracted game folder."""
    files, dirs = [], set()
    for root, dnames, fnames in os.walk(long_path(folder)):
        rel_root = os.path.relpath(root, long_path(folder)).replace(os.sep, "/")
        rel_root = "" if rel_root == "." else rel_root + "/"
        for d in dnames:
            dirs.add(rel_root + d)
        for name in fnames:
            files.append(file_source(os.path.join(root, name), rel_root + name))
    return files, dirs


# -- helpers --------------------------------------------------------------------------

def _align(value: int, align: int) -> int:
    return (value + align - 1) // align * align


def _ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def compute_keys(content_id: str, passcode: str, index: int) -> bytes:
    data = (hashlib.sha256(struct.pack(">I", index)).digest()
            + hashlib.sha256(content_id.encode("ascii").ljust(48, b"\x00")).digest()
            + passcode.encode("ascii"))
    return hashlib.sha256(data).digest()


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def keystone(passcode: str = PASSCODE) -> bytes:
    header = bytes.fromhex("6b657973746f6e65020001000000000000000000000000000000000000000000")
    fingerprint = hmac.new(build_keys.KEYSTONE_HMAC_KEY, passcode.encode("ascii"),
                           hashlib.sha256).digest()
    final = hmac.new(build_keys.KEYSTONE_MAC_DATA, header + fingerprint, hashlib.sha256).digest()
    return header + fingerprint + final


def _path_hash(path: str) -> int:
    h = 0
    for ch in path:
        up = ch.upper()
        h = (ord(up if len(up) == 1 else ch) + 31 * h) & 0xFFFFFFFF
    return h


class _Dirent:
    __slots__ = ("ino", "type", "name")

    def __init__(self, ino: int, dtype: int, name: str):
        self.ino, self.type, self.name = ino, dtype, name.encode("utf-8")

    @property
    def size(self) -> int:
        return _align(len(self.name) + 17, 8)

    def to_bytes(self) -> bytes:
        raw = struct.pack("<IiII", self.ino, self.type, len(self.name), self.size) + self.name
        return raw + bytes(self.size - len(raw))


def _pack_dirents(dirents: list[_Dirent]) -> list[bytes]:
    """Dirent blocks: a dirent never straddles two blocks."""
    blocks, cur, pos = [], bytearray(BLOCK), 0
    for d in dirents:
        raw = d.to_bytes()
        cur[pos:pos + len(raw)] = raw
        pos += len(raw)
        if pos > BLOCK - DIRENT_MAX:
            blocks.append(bytes(cur))
            cur, pos = bytearray(BLOCK), 0
    if pos or not blocks:
        blocks.append(bytes(cur))
    return blocks


@dataclass(eq=False)
class _Inode:
    number: int
    mode: int
    flags: int
    nlink: int = 1
    size: int = 0
    size_comp: int = 0
    blocks: int = 0
    start: int = 0

    def d32(self, file_time: int) -> bytes:
        db = [self.start] + [-1] * (min(self.blocks, 12) - 1) if self.blocks else [self.start]
        db += [0] * (12 - len(db))
        return struct.pack("<HHIqq4q4I2I2QI12i5i", self.mode, self.nlink, self.flags,
                           self.size, self.size_comp, *([file_time] * 4), 0, 0, 0, 0, 0, 0,
                           0, 0, self.blocks, *db, 0, 0, 0, 0, 0)

    def s32_head(self, file_time: int) -> bytes:
        return struct.pack("<HHIqq4q4I2I2QI", self.mode, self.nlink, self.flags, self.size,
                           self.size_comp, *([file_time] * 4), 0, 0, 0, 0, 0, 0, 0, 0,
                           self.blocks)


def _pfs_header(mode: int, ndblock: int, dinode_count: int, dinode_blocks: int,
                file_time: int, signed: bool, seed: Optional[bytes]) -> bytearray:
    """Superblock (block 0) up to the seed; the inode-block descriptor is a 64-bit inode."""
    out = bytearray(BLOCK)
    struct.pack_into("<qqqBBBBHHIIqqqqq", out, 0, 1, 20130315, 0, 0, 0, 1, 0, mode, 0, BLOCK,
                     0, 1, dinode_count, ndblock, dinode_blocks, 0)
    flags = 0 if signed else FLAG_READONLY
    struct.pack_into("<HHIqq4q4I2I2QIi", out, 0x50, 0, 1, flags, dinode_blocks * BLOCK,
                     dinode_blocks * BLOCK, *([file_time] * 4), 0, 0, 0, 0, 0, 0, 0, 0,
                     dinode_blocks, 0)
    db_off = 0x50 + 0x68
    for i in range(min(dinode_blocks, 12)):
        block = (1 + i) if signed else (1 if i == 0 else -1)
        struct.pack_into("<q", out, db_off + 40 * i + 32, block)
    if seed is not None:
        struct.pack_into("<i", out, 0x36C, 1)
        out[0x370:0x380] = seed
    else:
        struct.pack_into("<i", out, 0x368, 1)
    return out


# -- inner PFS (plain, unsigned) --------------------------------------------------------

class _Node:
    __slots__ = ("name", "parent", "is_dir", "source", "dirs", "files", "dirents", "ino",
                 "dirent_blocks")

    def __init__(self, name: str, parent: Optional["_Node"], is_dir: bool,
                 source: Optional[SourceFile] = None):
        self.name, self.parent, self.is_dir, self.source = name, parent, is_dir, source
        self.dirs: list[_Node] = []
        self.files: list[_Node] = []
        self.dirents: list[_Dirent] = []
        self.ino: Optional[_Inode] = None
        self.dirent_blocks: list[bytes] = []

    def full_path(self) -> str:
        if self.parent is None:
            return ""
        return self.parent.full_path() + "/" + self.name


class InnerPfs:
    """Plain PFS image holding the game files, produced block by block."""

    def __init__(self, files: list[SourceFile], dirs: Iterable[str], file_time: int,
                 min_blocks: int = 0x55):
        self.file_time = file_time
        self.root = _Node("uroot", None, True)
        index = {"": self.root}

        def get_dir(path: str) -> _Node:
            if path in index:
                return index[path]
            parent_path, _, name = path.rpartition("/")
            parent = get_dir(parent_path)
            node = _Node(name, parent, True)
            parent.dirs.append(node)
            index[path] = node
            return node

        for d in sorted(dirs):
            get_dir(d)
        for f in files:
            parent_path, _, name = f.path.rpartition("/")
            parent = get_dir(parent_path)
            parent.files.append(_Node(name, parent, False, f))

        all_dirs = sorted((n for p, n in index.items() if p), key=lambda n: n.full_path())
        all_files = sorted((f for n in index.values() for f in n.files),
                           key=lambda n: n.full_path())
        nodes = all_dirs + all_files
        hashes: dict[int, list[_Node]] = {}
        for n in nodes:
            hashes.setdefault(_path_hash(n.full_path()), []).append(n)
        collision = any(len(v) > 1 for v in hashes.values())

        # Inodes: superroot, flat path table, [collision resolver], uroot, dirs, files.
        self.inodes: list[_Inode] = []
        internal = FLAG_INTERNAL | FLAG_READONLY
        self.superroot = self._new_inode(MODE_DIR, internal, size=BLOCK, blocks=1)
        self.fpt = self._new_inode(MODE_FILE, internal, blocks=1)
        self.cr = self._new_inode(MODE_FILE, internal, blocks=1) if collision else None
        root_ino = self._new_inode(MODE_DIR, FLAG_READONLY, size=BLOCK, blocks=1, nlink=3)
        self.root.ino = root_ino
        self.root.dirents = [_Dirent(root_ino.number, DT_DOT, "."),
                             _Dirent(root_ino.number, DT_DOTDOT, "..")]
        for d in all_dirs:
            d.ino = self._new_inode(MODE_DIR, FLAG_READONLY, nlink=2)
            d.dirents = [_Dirent(d.ino.number, DT_DOT, "."),
                         _Dirent(d.parent.ino.number, DT_DOTDOT, "..")]
            d.parent.dirents.append(_Dirent(d.ino.number, DT_DIR, d.name))
            d.parent.ino.nlink += 1
        for f in all_files:
            f.ino = self._new_inode(MODE_FILE, FLAG_READONLY, size=f.source.size)
            f.parent.dirents.append(_Dirent(f.ino.number, DT_FILE, f.name))

        self.superroot_dirents = [_Dirent(self.fpt.number, DT_FILE, "flat_path_table")]
        if self.cr:
            self.superroot_dirents.append(_Dirent(self.cr.number, DT_FILE, "collision_resolver"))
        self.superroot_dirents.append(_Dirent(root_ino.number, DT_DIR, "uroot"))

        # Flat path table (+ collision resolver for paths sharing a hash).
        fpt = bytearray()
        cr = bytearray()
        for h in sorted(hashes):
            group = hashes[h]
            if len(group) == 1:
                n = group[0]
                fpt += struct.pack("<II", h, n.ino.number | (0x20000000 if n.is_dir else 0))
            else:
                fpt += struct.pack("<II", h, 0x80000000 | len(cr))
                for n in group:
                    cr += _Dirent(n.ino.number, DT_DIR if n.is_dir else DT_FILE,
                                  n.full_path()).to_bytes()
                cr += bytes(0x18)
        self.fpt_data, self.cr_data = bytes(fpt), bytes(cr)

        # Block layout.
        per_block = BLOCK // INODE_D32
        self.dinode_blocks = _ceil_div(len(self.inodes), per_block)
        nd = 1 + self.dinode_blocks
        self.superroot.start = nd
        nd += 1
        self.fpt.size = self.fpt.size_comp = len(self.fpt_data)
        self.fpt.blocks = max(1, _ceil_div(len(self.fpt_data), BLOCK))
        self.fpt.start = nd
        nd += self.fpt.blocks
        if self.cr:
            self.cr.size = self.cr.size_comp = len(self.cr_data)
            self.cr.blocks = max(1, _ceil_div(len(self.cr_data), BLOCK))
            self.cr.start = nd
            nd += self.cr.blocks
        else:
            nd += 1  # an empty block follows the path table
        self.nodes = [self.root] + all_dirs + all_files
        for n in self.nodes:
            if n.is_dir:
                n.dirent_blocks = _pack_dirents(n.dirents)
                n.ino.blocks = len(n.dirent_blocks)
                n.ino.size = n.ino.size_comp = n.ino.blocks * BLOCK
            else:
                n.ino.size = n.ino.size_comp = n.source.size
                n.ino.blocks = _ceil_div(n.source.size, BLOCK)
            n.ino.start = nd
            nd += n.ino.blocks
        self.ndblock = max(nd, min_blocks)

    def _new_inode(self, mode: int, flags: int, size: int = 0, blocks: int = 0,
                   nlink: int = 1) -> _Inode:
        ino = _Inode(len(self.inodes), mode, flags, nlink, size, size, blocks)
        self.inodes.append(ino)
        return ino

    @property
    def size(self) -> int:
        return self.ndblock * BLOCK

    def _metadata_blocks(self) -> Iterator[bytes]:
        yield bytes(_pfs_header(0x8, self.ndblock, len(self.inodes), self.dinode_blocks,
                                self.file_time, False, None))
        per_block = BLOCK // INODE_D32
        for b in range(self.dinode_blocks):
            chunk = self.inodes[b * per_block:(b + 1) * per_block]
            data = b"".join(i.d32(self.file_time) for i in chunk)
            yield data + bytes(BLOCK - len(data))
        yield from _pack_dirents(self.superroot_dirents)
        for data, ino in ((self.fpt_data, self.fpt), (self.cr_data, self.cr)):
            if ino is None:
                continue
            for i in range(ino.blocks):
                part = data[i * BLOCK:(i + 1) * BLOCK]
                yield part + bytes(BLOCK - len(part))
        if self.cr is None:
            yield bytes(BLOCK)

    def blocks(self, on_file: Optional[Callable[[str], None]] = None) -> Iterator[bytes]:
        written = 0
        for blk in self._metadata_blocks():
            written += 1
            yield blk
        for n in self.nodes:
            assert n.ino.start == written, (n.full_path(), n.ino.start, written)
            if n.is_dir:
                for blk in n.dirent_blocks:
                    written += 1
                    yield blk
                continue
            if on_file:
                on_file(n.full_path().lstrip("/"))
            buf = bytearray()
            got = 0
            for chunk in n.source.read():
                got += len(chunk)
                buf += chunk
                while len(buf) >= BLOCK:
                    written += 1
                    yield bytes(buf[:BLOCK])
                    del buf[:BLOCK]
            if got != n.source.size:
                raise PkgError(tr("Dimensione inattesa per {path}: {got} invece di {size} byte",
                                  path=n.full_path(), got=got, size=n.source.size))
            if buf:
                written += 1
                yield bytes(buf) + bytes(BLOCK - len(buf))
        while written < self.ndblock:
            written += 1
            yield bytes(BLOCK)


def _pfsc_header(inner_size: int) -> bytes:
    """PFSC container storing the inner image uncompressed (as LibOrbisPkg does)."""
    n = inner_size // BLOCK
    table = 8 + n * 8
    extra = _ceil_div(table - 0xFC00, BLOCK) if table > 0xFC00 else 0
    size = BLOCK * (1 + extra)
    out = bytearray(size)
    struct.pack_into(">I", out, 0, 0x50465343)
    struct.pack_into("<iiiqqqq", out, 4, 0, 6, BLOCK, BLOCK, 0x400, size, n * BLOCK)
    for i in range(n + 1):
        struct.pack_into("<q", out, 0x400 + 8 * i, size + i * BLOCK)
    return bytes(out)


# -- outer PFS (signed + encrypted) -----------------------------------------------------

def _indirect_blocks(n_blocks: int) -> int:
    ib = 0
    if n_blocks > 12:
        n_blocks -= 12
        ib += 1
    if n_blocks > SIGS_PER_BLOCK:
        n_blocks -= SIGS_PER_BLOCK
        ib += 1 + _ceil_div(n_blocks, SIGS_PER_BLOCK)
    return ib


class OuterPfs:
    """Signed and encrypted PFS whose only file, pfs_image.dat, holds the inner image."""

    SUPERROOT, FPT, UROOT, IMAGE = 0, 1, 2, 3

    def __init__(self, inner: InnerPfs, ekpfs: bytes, seed: bytes = bytes(16)):
        self.inner = inner
        self.seed = seed
        self.file_time = inner.file_time
        self.pfsc = _pfsc_header(inner.size)
        self.image_size = len(self.pfsc) + inner.size
        self.image_blocks = self.image_size // BLOCK
        self.n_ib = _indirect_blocks(self.image_blocks)
        # 0 header, 1 inodes, 2 superroot dirents, 3 flat path table, 4 empty (not
        # encrypted), indirect signature blocks, uroot dirents, pfs_image.dat.
        self.empty_block = 4
        self.ib_start = 5
        self.uroot_block = self.ib_start + self.n_ib
        self.data_start = self.uroot_block + 1
        self.ndblock = self.data_start + self.image_blocks
        self.sign_key = hmac.new(ekpfs, struct.pack("<I", 2) + seed, hashlib.sha256).digest()
        data_key, tweak_key = crypto.pfs_gen_crypto_key(ekpfs, seed, False)
        self.xts = crypto.XtsEncryptor(data_key, tweak_key)

    @property
    def size(self) -> int:
        return self.ndblock * BLOCK

    def _sign(self, data: bytes) -> bytes:
        return hmac.new(self.sign_key, data, hashlib.sha256).digest()

    def _encrypt(self, block_no: int, data: bytes) -> bytes:
        if block_no == 0 or block_no == self.empty_block:
            return data
        return self.xts.encrypt(data, block_no * SECTORS_PER_BLOCK)

    def write(self, f, offset: int, progress: Callable[[int], None],
              should_cancel: Optional[Callable[[], bool]],
              on_file: Optional[Callable[[str], None]] = None) -> None:
        """Write the image at offset in f (the area must be zero-filled already)."""
        sigs: list[bytes] = []
        f.seek(offset + self.data_start * BLOCK)
        blocks = self.inner.blocks(on_file)
        pfsc = [self.pfsc[i:i + BLOCK] for i in range(0, len(self.pfsc), BLOCK)]
        for k, blk in enumerate(_chain(pfsc, blocks)):
            if should_cancel and k % 16 == 0 and should_cancel():
                raise Cancelled()
            sigs.append(self._sign(blk))
            f.write(self._encrypt(self.data_start + k, blk))
            progress(BLOCK)
        if len(sigs) != self.image_blocks:
            raise PkgError(tr("Immagine PFS interna di dimensione inattesa"))

        meta: dict[int, bytes] = {}

        def put(block_no: int, data: bytes) -> bytes:
            meta[block_no] = data
            return self._sign(data)

        uroot = [_Dirent(self.UROOT, DT_DOT, "."), _Dirent(self.UROOT, DT_DOTDOT, ".."),
                 _Dirent(self.IMAGE, DT_FILE, "pfs_image.dat")]
        uroot_sig = put(self.uroot_block, _pack_dirents(uroot)[0])

        # Block signatures of pfs_image.dat: 12 direct, then one indirect block, then a
        # doubly indirect block pointing to more indirect blocks.
        def sig_table(entries: list[tuple[bytes, int]]) -> bytes:
            data = b"".join(s + struct.pack("<i", b) for s, b in entries)
            return data + bytes(BLOCK - len(data))

        direct = [(sigs[i], self.data_start + i) for i in range(min(12, len(sigs)))]
        indirect: list[tuple[bytes, int]] = []
        ib_next = self.ib_start
        if len(sigs) > 12:
            part = sigs[12:12 + SIGS_PER_BLOCK]
            entries = [(s, self.data_start + 12 + j) for j, s in enumerate(part)]
            indirect.append((put(ib_next, sig_table(entries)), ib_next))
            ib_next += 1
        done = 12 + SIGS_PER_BLOCK
        if len(sigs) > done:
            top = ib_next
            ib_next += 1
            top_entries = []
            while done < len(sigs):
                part = sigs[done:done + SIGS_PER_BLOCK]
                entries = [(s, self.data_start + done + j) for j, s in enumerate(part)]
                top_entries.append((put(ib_next, sig_table(entries)), ib_next))
                ib_next += 1
                done += len(part)
            indirect.append((put(top, sig_table(top_entries)), top))
        assert ib_next == self.uroot_block

        superroot_sig = put(2, _pack_dirents([
            _Dirent(self.FPT, DT_FILE, "flat_path_table"),
            _Dirent(self.UROOT, DT_DIR, "uroot")])[0])
        fpt_data = struct.pack("<II", _path_hash("/pfs_image.dat"), self.IMAGE)
        fpt_sig = put(3, fpt_data + bytes(BLOCK - len(fpt_data)))

        flags = FLAG_UNK2 | FLAG_UNK3
        inodes = [
            (_Inode(0, MODE_DIR, FLAG_INTERNAL | flags, 1, BLOCK, BLOCK, 1),
             [(superroot_sig, 2)], []),
            (_Inode(1, MODE_FILE, FLAG_INTERNAL | flags, 1, len(fpt_data), len(fpt_data), 1),
             [(fpt_sig, 3)], []),
            (_Inode(2, MODE_DIR, flags, 3, BLOCK, BLOCK, 1), [(uroot_sig, self.uroot_block)], []),
            (_Inode(3, MODE_FILE, FLAG_COMPRESSED | flags, 1, self.image_size, self.inner.size,
                    self.image_blocks), direct, indirect),
        ]
        inode_block = bytearray(BLOCK)
        for ino, db, ib in inodes:
            raw = bytearray(ino.s32_head(self.file_time))
            for i in range(12):
                s, b = db[i] if i < len(db) else (bytes(32), 0)
                raw += s + struct.pack("<i", b)
            for i in range(5):
                s, b = ib[i] if i < len(ib) else (bytes(32), 0)
                raw += s + struct.pack("<i", b)
            assert len(raw) == INODE_S32
            pos = ino.number * INODE_S32
            inode_block[pos:pos + INODE_S32] = raw
        inode_sig = put(1, bytes(inode_block))

        header = _pfs_header(0x1 | 0x4 | 0x8, self.ndblock, len(inodes), 1, self.file_time, True,
                             self.seed)
        header[0xB8:0xB8 + 32] = inode_sig
        struct.pack_into("<i", header, 0xD8, 1)
        header_sig = self._sign(bytes(header[:0x5A0]))
        header[0x380:0x3A0] = header_sig
        struct.pack_into("<i", header, 0x3A0, 0)
        meta[0] = bytes(header)

        for block_no, data in sorted(meta.items()):
            f.seek(offset + block_no * BLOCK)
            f.write(self._encrypt(block_no, data))


def _chain(*iterables):
    for it in iterables:
        yield from it


# -- PKG ------------------------------------------------------------------------------

@dataclass
class _Entry:
    id: int
    name: Optional[str]
    data: bytes = b""
    flags1: int = 0
    key_index: int = 0
    offset: int = 0
    size: int = 0

    def meta(self, name_offset: int) -> bytes:
        return struct.pack(">IIIIII8x", self.id, name_offset, self.flags1, self.key_index << 12,
                           self.offset, self.size)


def _entry_keys(content_id: str) -> bytes:
    out = bytearray(hashlib.sha256(content_id.encode("ascii").ljust(48, b"\x00")).digest())
    digests, enc = [], []
    for i in range(7):
        pk = compute_keys(content_id, PASSCODE, i)
        digests.append(_xor(hashlib.sha256(pk).digest(), pk))
        plain = PASSCODE.encode("ascii") if i == 0 else pk
        enc.append(crypto.rsa_encrypt_key(plain, build_keys.PKG_PUBLIC_KEYS[i]))
    return bytes(out) + b"".join(digests) + b"".join(enc)


def _license_dat(content_id: str) -> bytes:
    cid = content_id.encode("ascii")
    h = hashlib.sha256(cid.ljust(48, b"\x00")).digest()
    secret_iv = h[:16]
    secret = bytearray(144)
    secret[:16] = h[16:32]
    secret = crypto.aes_cbc_encrypt_raw(build_keys.RIF_DEBUG_AES_KEY, secret_iv, bytes(secret))
    out = bytearray(0x400)
    struct.pack_into(">IhhQqq", out, 0, 0x52494600, 1, -1, 0, 1364222275, 0x7FFFFFFFFFFFFFFF)
    out[0x20:0x20 + 36] = cid
    struct.pack_into(">hhhhiiiii", out, 0x50, 0x200, DRM_PS4, CONTENT_TYPE_GD, 3, 0, 0, 0, 1, 0)
    out[0x240:0x260] = bytes(32)
    out[0x260:0x270] = secret_iv
    out[0x270:0x300] = secret
    digest = hashlib.sha256(bytes(out[:0x300])).digest()
    out[0x300:0x400] = crypto.rsa_sign_sha256(digest, build_keys.RIF_DEBUG_N,
                                              build_keys.RIF_DEBUG_D)
    return bytes(out)


def _license_info(content_id: str) -> bytes:
    out = bytearray(0x200)
    out[:36] = content_id.encode("ascii")
    struct.pack_into(">iiii", out, 0x40, 0, CONTENT_TYPE_GD, 0, 1)
    return bytes(out)


def _chunk_dat(content_id: str, package_size: int, inner_size: int) -> bytes:
    out = bytearray(416)
    struct.pack_into("<IHHHHHHIHHIHH", out, 0, 0x6F676C70, 0, 0, 1, 1, 1, 1, 416, 0, 1, 0, 0, 0)
    out[0x20:0x40] = b"\xff" * 32
    out[0x40:0x40 + 36] = content_id.encode("ascii")
    struct.pack_into("<16I", out, 0xC0, 256, 32, 288, 2, 304, 9, 320, 16, 352, 32, 384, 2,
                     400, 12, 336, 16)
    struct.pack_into("<BBB11xHQII", out, 0x100, 0x80, 0, 3, 1, 0xFFFFFFFFFFFFFFFF, 0, 0)
    out[0x130:0x138] = b"Chunk #0"
    struct.pack_into("<QQ", out, 0x140, 0, package_size)
    struct.pack_into("<QQ", out, 0x150, 0, inner_size)
    struct.pack_into("<B19xHHII", out, 0x160, 1, 1, 1, 0, 0)
    out[0x190:0x19B] = b"Scenario #0"
    return bytes(out)


def _sfo_str(sfo: Sfo, key: str) -> str:
    for v in sfo.values:
        if v.key == key:
            return f"0x{v.value:08x}" if isinstance(v.value, int) else str(v.value)
    return ""


def _major_param_digest(sfo: Sfo) -> bytes:
    s = "ATTRIBUTE" + _sfo_str(sfo, "ATTRIBUTE")
    if sfo.get("ATTRIBUTE2") is not None:
        s += "ATTRIBUTE2" + _sfo_str(sfo, "ATTRIBUTE2")
    s += "CATEGORY" + _sfo_str(sfo, "CATEGORY")
    s += "FORMAT" + _sfo_str(sfo, "FORMAT")
    s += "PUBTOOLVER" + _sfo_str(sfo, "PUBTOOLVER")
    return hashlib.sha256(s.encode("ascii", "replace")).digest()


def _header_bytes(h: dict) -> bytearray:
    out = bytearray(0x1000)
    out[0:4] = b"\x7fCNT"
    struct.pack_into(">IIIIHHII", out, 0x04, 0x01, 0, 0xF, h["entry_count"], 6,
                     h["entry_count"], h["entry_table_offset"], h["main_ent_data_size"])
    struct.pack_into(">QQ", out, 0x20, h["body_offset"], h["body_size"])
    out[0x40:0x40 + 36] = h["content_id"].encode("ascii")
    struct.pack_into(">IIIIIIIIIIII", out, 0x70, DRM_PS4, CONTENT_TYPE_GD, CONTENT_FLAGS_GD,
                     h["promote_size"], 0x20161020, 0x1738551, 0, 0, 0, 0, 0, 1)
    for off, key in ((0x100, "sc_entries1_hash"), (0x120, "sc_entries2_hash"),
                     (0x140, "digest_table_hash"), (0x160, "body_digest")):
        out[off:off + 32] = h.get(key, bytes(32))
    struct.pack_into(">IIQQQQQQII", out, 0x400, 1, 1, 0x80000000000003CC,
                     h["pfs_image_offset"], h["pfs_image_size"], 0, h["package_size"],
                     h["package_size"], 0x10000, 0xD0000)
    out[0x440:0x460] = h.get("pfs_image_digest", bytes(32))
    out[0x460:0x480] = h.get("pfs_signed_digest", bytes(32))
    return out


def build_pkg(files: list[SourceFile], dirs: Iterable[str], out_path: str,
              sfo: Optional[Sfo] = None, log: Callable[[str], None] = lambda s: None,
              progress: Optional[BuildProgress] = None,
              should_cancel: Optional[Callable[[], bool]] = None,
              file_time: Optional[int] = None) -> str:
    """Write a game fPKG to out_path; returns its content ID.

    files may include sce_sys/param.sfo (used unless sfo is given), icons and the other
    sce_sys entries; everything else goes into the PFS image.
    """
    file_time = int(time.time()) if file_time is None else file_time
    entry_files: dict[int, SourceFile] = {}
    pfs_files: list[SourceFile] = []
    sfo_source = None
    for f in files:
        rel = f.path[len("sce_sys/"):] if f.path.startswith("sce_sys/") else None
        if rel == "param.sfo":
            sfo_source = f
        elif rel in SKIPPED_SCE_SYS:
            continue
        elif rel is not None and rel in ENTRY_FILES:
            entry_files[ENTRY_FILES[rel]] = f
        else:
            pfs_files.append(f)
    if sfo is None:
        if sfo_source is None:
            raise PkgError(tr("Manca sce_sys/param.sfo: non è la cartella di un gioco"))
        sfo = Sfo.parse(b"".join(sfo_source.read()))
    category = str(sfo.get("CATEGORY", ""))
    if category != "gd":
        raise PkgError(tr("Si possono creare solo PKG di giochi (categoria 'gd', trovata '{cat}')",
                          cat=category))
    content_id = str(sfo.get("CONTENT_ID", ""))
    if len(content_id) != 36 or not content_id.isascii():
        raise PkgError(tr("CONTENT_ID non valido nel param.sfo: '{cid}'", cid=content_id))
    dirs = set(dirs)
    for f in files:
        parent = f.path.rpartition("/")[0]
        while parent:
            dirs.add(parent)
            parent = parent.rpartition("/")[0]
    if not any(f.path == "sce_sys/keystone" for f in pfs_files):
        pfs_files.append(bytes_source("sce_sys/keystone", keystone()))
        dirs.add("sce_sys")

    log(tr("Preparazione del file system ({n} file)...", n=len(pfs_files)))
    inner = InnerPfs(pfs_files, dirs, file_time)
    ekpfs = compute_keys(content_id, PASSCODE, 1)
    outer = OuterPfs(inner, ekpfs)
    pfs_size = outer.size

    sfo.set_str("PUBTOOLINFO",
                f"c_date={datetime.datetime.now(datetime.timezone.utc):%Y%m%d}"
                f",img0_l0_size={(0x80000 + pfs_size + 0xFFFFF) // (1 << 20)}"
                ",img0_l1_size=0,img0_sc_ksize=512,img0_pc_ksize=832", 0x200)
    if sfo.get("PUBTOOLVER") is None:
        sfo.set_int("PUBTOOLVER", 0x02890000)
    sfo_bytes = sfo.to_bytes()

    entries = [
        _Entry(E_ENTRY_KEYS, None, _entry_keys(content_id), 0x60000000),
        _Entry(E_IMAGE_KEY, None, crypto.rsa_encrypt_key(ekpfs, keys.FAKE_N), 0xE0000000, 3),
        _Entry(E_GENERAL_DIGESTS, None, bytes(0x180), 0x60000000),
        _Entry(E_METAS, None, b"", 0x60000000),
        _Entry(E_DIGESTS, None, b"", 0x40000000),
        _Entry(E_ENTRY_NAMES, None, b"", 0x40000000),
        _Entry(E_CHUNK_DAT, "playgo-chunk.dat", bytes(416)),
        _Entry(E_CHUNK_SHA, "playgo-chunk.sha"),
        _Entry(E_CHUNK_XML, "playgo-manifest.xml", PLAYGO_MANIFEST),
        _Entry(E_LICENSE_DAT, None, _license_dat(content_id), 0x80000000, 3),
        _Entry(E_LICENSE_INFO, None, _license_info(content_id), 0x80000000, 2),
        _Entry(E_PARAM_SFO, "param.sfo", sfo_bytes),
        _Entry(E_PSRESERVED, None, bytes(0x2000)),
    ]
    for eid in sorted(entry_files):
        entries.append(_Entry(eid, ENTRY_NAMES[eid], b"".join(entry_files[eid].read())))
    by_id = {e.id: e for e in entries}
    count = len(entries)
    names = sorted({e.name for e in entries if e.name})
    name_offsets, table = {}, bytearray(b"\x00")
    for n in names:
        name_offsets[n] = len(table)
        table += n.encode("ascii") + b"\x00"
    by_id[E_ENTRY_NAMES].data = bytes(table)
    by_id[E_METAS].size = by_id[E_DIGESTS].size = count * 32

    body_offset = 0x2000
    chunk_sha_size = 0
    while True:
        pos = body_offset
        for e in entries:
            if e.id == E_CHUNK_SHA:
                e.size = chunk_sha_size
            elif e.id not in (E_METAS, E_DIGESTS):
                e.size = len(e.data)
            e.offset = pos
            pos = _align(pos + e.size, 16)
        body_size = _align(pos, 0x80000) - body_offset
        package_size = body_offset + body_size + pfs_size
        needed = 4 * (package_size // 0x10000)
        if needed <= chunk_sha_size:
            by_id[E_CHUNK_SHA].size = needed
            break
        chunk_sha_size = needed
    pfs_offset = body_offset + body_size
    if by_id[E_METAS].offset != 0x2A80:
        raise PkgError("unexpected entry table offset")

    log(tr("Scrittura dell'immagine PFS ({size} MB)...", size=pfs_size >> 20))
    total = outer.image_size + pfs_size
    done = [0]
    current = [tr("Struttura del PKG")]

    def advance(n: int) -> None:
        done[0] += n
        if progress:
            progress(done[0], total, current[0])

    def on_file(name: str) -> None:
        current[0] = tr("Sto scrivendo: {name}", name=name)

    tmp_path = out_path + ".part"
    try:
        with open(long_path(tmp_path), "w+b") as f:
            f.truncate(package_size)
            outer.write(f, pfs_offset, advance, should_cancel, on_file)

            log(tr("Calcolo delle impronte…"))
            current[0] = tr("Calcolo delle impronte…")
            full = hashlib.sha256()
            chunk_sha = bytearray(needed)
            f.seek(pfs_offset)
            first = pfs_offset // 0x10000
            for i in range(pfs_size // BLOCK):
                if should_cancel and i % 64 == 0 and should_cancel():
                    raise Cancelled()
                blk = f.read(BLOCK)
                full.update(blk)
                if i == 0:
                    signed_digest = hashlib.sha256(blk).digest()
                chunk_sha[(first + i) * 4:(first + i) * 4 + 4] = hashlib.sha256(blk).digest()[:4]
                advance(BLOCK)
            image_digest = full.digest()
            by_id[E_CHUNK_SHA].data = bytes(chunk_sha)
            by_id[E_CHUNK_DAT].data = _chunk_dat(content_id, package_size, inner.size)

            hdr = {
                "entry_count": count, "entry_table_offset": by_id[E_METAS].offset,
                "main_ent_data_size": 2048 + 256 + 0x180 + 2 * count * 32,
                "body_offset": body_offset, "body_size": body_size, "content_id": content_id,
                "promote_size": body_offset + body_size, "pfs_image_offset": pfs_offset,
                "pfs_image_size": pfs_size, "package_size": package_size,
                "pfs_image_digest": image_digest, "pfs_signed_digest": signed_digest,
            }
            raw_hdr = _header_bytes(hdr)
            header_digest = hashlib.sha256(bytes(raw_hdr[:64]) + bytes(raw_hdr[0x400:0x480]))
            content_digest = hashlib.sha256(
                content_id.encode("ascii") + bytes(12) + struct.pack(">ii", DRM_PS4, CONTENT_TYPE_GD)
                + image_digest + _major_param_digest(sfo)).digest()
            general = bytearray(0x180)
            struct.pack_into(">HH24xi", general, 0, 0xD256, 0x100, 0x2 | 0x4 | 0x8 | 0x20 | 0x40)
            for i, d in enumerate((content_digest, image_digest, header_digest.digest(), bytes(32),
                                   _major_param_digest(sfo), hashlib.sha256(sfo_bytes).digest())):
                general[32 + 32 * i:64 + 32 * i] = d
            by_id[E_GENERAL_DIGESTS].data = bytes(general)

            metas = sorted(entries, key=lambda e: e.id)
            table_bytes = b"".join(e.meta(name_offsets.get(e.name, 0)) for e in metas)
            by_id[E_METAS].data = table_bytes
            by_id[E_DIGESTS].data = bytes(count * 32)

            body = bytearray(body_size)
            stored: dict[int, bytes] = {}
            for e in entries:
                data = e.data
                if e.flags1 & 0x80000000:
                    meta = e.meta(name_offsets.get(e.name, 0))
                    iv_key = hashlib.sha256(
                        meta + compute_keys(content_id, PASSCODE, e.key_index)).digest()
                    data = crypto.aes_cbc_encrypt(iv_key, data)
                assert len(data) == e.size, (hex(e.id), len(data), e.size)
                stored[e.id] = data
                body[e.offset - body_offset:e.offset - body_offset + e.size] = data
            digests = bytearray(count * 32)
            for i, e in enumerate(metas):
                if i == 0:
                    continue
                digests[32 * i:32 * i + 32] = hashlib.sha256(stored[e.id]).digest()
            d = by_id[E_DIGESTS]
            body[d.offset - body_offset:d.offset - body_offset + d.size] = digests
            stored[E_DIGESTS] = bytes(digests)

            hdr["body_digest"] = hashlib.sha256(body).digest()
            hdr["digest_table_hash"] = hashlib.sha256(digests).digest()
            sc = [stored[i] for i in (E_ENTRY_KEYS, E_IMAGE_KEY, E_GENERAL_DIGESTS, E_METAS)]
            hdr["sc_entries1_hash"] = hashlib.sha256(b"".join(sc) + stored[E_DIGESTS]).digest()
            sc[3] = sc[3][:6 * 0x20]
            hdr["sc_entries2_hash"] = hashlib.sha256(b"".join(sc)).digest()
            head = _header_bytes(hdr)
            head[0xFE0:0x1000] = hashlib.sha256(bytes(head[:0xFE0])).digest()
            signature = crypto.rsa_encrypt_key(hashlib.sha256(bytes(head)).digest(),
                                                    build_keys.PKG_PUBLIC_KEYS[3])
            f.seek(0)
            f.write(head)
            f.write(signature)
            f.seek(body_offset)
            f.write(body)
        os.replace(long_path(tmp_path), long_path(out_path))
    except BaseException:
        try:
            os.remove(long_path(tmp_path))
        except OSError:
            pass
        raise
    return content_id
