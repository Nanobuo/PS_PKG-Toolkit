"""PKG creation: the packages must pass every check LibOrbisPkg's validator makes, carry
valid PFS block signatures and extract back to the same files."""

import hashlib
import hmac
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PSPKG_LANG"] = "it"

from fake_pkg_builder import build_pkg as build_fake_pkg, make_sfo  # noqa: E402
from pkgfree import build_keys, builder, crypto, merge  # noqa: E402
from pkgfree.pkg import PkgFile  # noqa: E402
from pkgfree.sfo import Sfo  # noqa: E402

CID = "UP0000-CUSA12345_00-TESTTESTTEST0000"
SFO = {"CATEGORY": "gd", "TITLE_ID": "CUSA12345", "APP_VER": "01.00", "TITLE": "Prova",
       "CONTENT_ID": CID, "ATTRIBUTE": 0, "FORMAT": "obs", "VERSION": "01.00"}


def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def validate(path: str) -> list[str]:
    """Port of LibOrbisPkg's PkgValidator plus a check of every PFS block signature.
    Returns the names of the failed checks."""
    failed = []

    def check(name, ok):
        if not ok:
            failed.append(name)

    with open(path, "rb") as f:
        data = f.read()
    hdr = data[:0x1000]
    entry_count, = struct.unpack_from(">I", hdr, 0x10)
    sc_count, = struct.unpack_from(">H", hdr, 0x14)
    table_off, = struct.unpack_from(">I", hdr, 0x18)
    body_off, body_size = struct.unpack_from(">QQ", hdr, 0x20)
    content_id = hdr[0x40:0x40 + 36].decode()
    drm, ctype = struct.unpack_from(">II", hdr, 0x70)
    pfs_off, pfs_size, _, mount_size = struct.unpack_from(">QQQQ", hdr, 0x410)
    metas = []
    for i in range(entry_count):
        eid, name_off, f1, f2, off, size = struct.unpack_from(">IIIIII", data, table_off + 32 * i)
        metas.append((eid, f1, f2, off, size, data[table_off + 32 * i:table_off + 32 * i + 32]))
    by_id = {m[0]: m for m in metas}

    def entry(eid, size=None):
        m = by_id[eid]
        return data[m[3]:m[3] + (m[4] if size is None else size)]

    def dk(index):
        return builder.compute_keys(content_id, builder.PASSCODE, index)

    def plain(eid):
        m = by_id[eid]
        iv_key = sha(m[5] + dk((m[2] >> 12) & 0xF))
        return crypto.aes_cbc_decrypt(iv_key, entry(eid))

    check("PKG Size", mount_size % 0x8000 == 0 and mount_size >= 0x100000)
    sfo_raw = entry(0x1000)
    sfo = Sfo.parse(sfo_raw)
    gd = entry(0x80)
    set_digests, = struct.unpack_from(">I", gd, 28)
    digests = {1 << (i + 1): gd[32 + 32 * i:64 + 32 * i] for i in range(6)}
    image_digest = sha(data[pfs_off:pfs_off + pfs_size])
    major = builder._major_param_digest(sfo)
    expected = {
        0x2: sha(content_id.encode() + bytes(12) + struct.pack(">ii", drm, ctype) + image_digest
                 + major),
        0x4: hdr[0x440:0x460],
        0x8: sha(hdr[:64] + hdr[0x400:0x480]),
        0x20: major,
        0x40: sha(sfo_raw),
    }
    for flag, value in expected.items():
        check(f"general digest {flag:#x}", set_digests & flag and digests[flag] == value)
    table = entry(0x1)
    for i, m in enumerate(metas):
        if i:
            check(f"entry {m[0]:#x} digest", table[32 * i:32 * i + 32] == sha(entry(m[0])))
    check("PFS Signed Digest", hdr[0x460:0x480] == sha(data[pfs_off:pfs_off + 0x10000]))
    check("PFS Image Digest", hdr[0x440:0x460] == image_digest)
    check("Body Digest", hdr[0x160:0x180] == sha(data[body_off:body_off + body_size]))
    check("Digest Table Hash", hdr[0x140:0x160] == sha(table))
    sc = [entry(i) for i in (0x10, 0x20, 0x80, 0x100)]
    check("SC Entries Hash 1", hdr[0x100:0x120] == sha(b"".join(sc) + table))
    sc[3] = entry(0x100, sc_count * 0x20)
    check("SC Entries Hash 2", hdr[0x120:0x140] == sha(b"".join(sc)))
    check("PKG Header Digest", hdr[0xFE0:0x1000] == sha(hdr[:0xFE0]))
    check("PKG Header Signature", data[0x1000:0x1100] == crypto.rsa_encrypt_key(
        sha(hdr), build_keys.PKG_PUBLIC_KEYS[3]))
    lic = plain(0x400)
    em = pow(int.from_bytes(lic[0x300:0x400], "big"), build_keys.RIF_DEBUG_E,
             build_keys.RIF_DEBUG_N).to_bytes(256, "big")
    check("Debug RIF Signature", em.endswith(sha(lic[:0x300])) and em[:2] == b"\x00\x01")

    # Entry keys: digest = SHA256(key) xor key, and the derived key 3 must be recoverable.
    keys_entry = entry(0x10)
    for i in range(7):
        k = dk(i)
        check(f"entry key {i} digest",
              keys_entry[32 + 32 * i:64 + 32 * i] == bytes(a ^ b for a, b in zip(sha(k), k)))
    check("derived key 3", crypto.decrypt_dk3(keys_entry[256 + 3 * 256:256 + 4 * 256]) == dk(3))
    ekpfs = crypto.decrypt_ekpfs(plain(0x20))
    check("EKPFS", ekpfs == dk(1))

    # Outer PFS: every block signature, following the inode tree.
    seed = data[pfs_off + 0x370:pfs_off + 0x380]
    data_key, tweak_key = crypto.pfs_gen_crypto_key(ekpfs, seed)
    xts = crypto.XtsDecryptor(data_key, tweak_key)
    sign_key = hmac.new(ekpfs, struct.pack("<I", 2) + seed, hashlib.sha256).digest()

    def block(n):
        raw = data[pfs_off + n * 0x10000:pfs_off + (n + 1) * 0x10000]
        return raw if n in (0, 4) else xts.decrypt(raw, n * 16)

    def sig_ok(sig_and_block, content):
        return sig_and_block[:32] == hmac.new(sign_key, content, hashlib.sha256).digest()

    b0 = bytearray(block(0))
    sig = bytes(b0[0x380:0x3A4])
    b0[0x380:0x3A4] = bytes(0x24)
    check("PFS header signature", sig_ok(sig, bytes(b0[:0x5A0])))
    check("PFS inode block signature", sig_ok(bytes(b0[0xB8:0xDC]), block(1)))
    inodes = block(1)
    ndblock, = struct.unpack_from("<q", b0, 0x38)
    check("PFS size", ndblock * 0x10000 == pfs_size)
    spb = builder.SIGS_PER_BLOCK
    for ino in range(4):
        base = ino * 0x2C8
        n_blocks, = struct.unpack_from("<I", inodes, base + 0x60)
        sigs = [inodes[base + 0x64 + 36 * i:base + 0x64 + 36 * (i + 1)] for i in range(17)]
        leaves = []
        for i in range(min(12, n_blocks)):
            leaves.append(sigs[i])
        if n_blocks > 12:
            ib0, = struct.unpack_from("<i", sigs[12], 32)
            content = block(ib0)
            check("PFS ib[0] signature", sig_ok(sigs[12], content))
            leaves += [content[36 * j:36 * (j + 1)] for j in range(min(spb, n_blocks - 12))]
        if n_blocks > 12 + spb:
            top, = struct.unpack_from("<i", sigs[13], 32)
            top_content = block(top)
            check("PFS ib[1] signature", sig_ok(sigs[13], top_content))
            left = n_blocks - 12 - spb
            i = 0
            while left > 0:
                entry_sig = top_content[36 * i:36 * (i + 1)]
                ib, = struct.unpack_from("<i", entry_sig, 32)
                content = block(ib)
                check("PFS ib[1][i] signature", sig_ok(entry_sig, content))
                take = min(spb, left)
                leaves += [content[36 * j:36 * (j + 1)] for j in range(take)]
                left -= take
                i += 1
        check(f"inode {ino} signature count", len(leaves) == n_blocks)
        for leaf in leaves:
            n, = struct.unpack_from("<i", leaf, 32)
            if not sig_ok(leaf, block(n)):
                failed.append(f"inode {ino} data block {n} signature")
                break
    return failed


def tree(files: dict) -> list:
    return [builder.bytes_source(path, data) for path, data in files.items()]


class BuilderTests(unittest.TestCase):
    def build(self, d, files, dirs=(), **kw):
        out = os.path.join(d, "out.pkg")
        builder.build_pkg(tree(files), dirs, out, **kw)
        return out

    def extract(self, pkg_path, dest):
        with PkgFile(pkg_path) as p:
            self.assertTrue(all(c.status == "ok" for c in p.verify()))
            p.extract(dest)

    def test_valid_and_round_trip(self):
        files = {
            "sce_sys/param.sfo": make_sfo(SFO),
            "sce_sys/icon0.png": b"PNG" * 999,
            "sce_sys/trophy/trophy00.trp": b"T" * 77,
            "eboot.bin": os.urandom(150000),
            "data/big.bin": os.urandom(20 * 0x10000 + 5),  # needs an indirect block
            "data/empty.bin": b"",
        }
        with tempfile.TemporaryDirectory() as d:
            out = self.build(d, files, dirs={"empty_dir"})
            self.assertEqual(validate(out), [])
            self.extract(out, os.path.join(d, "x"))
            for path, data in files.items():
                if path == "sce_sys/param.sfo":
                    continue
                with open(os.path.join(d, "x", path), "rb") as f:
                    self.assertEqual(f.read(), data, path)
            self.assertTrue(os.path.isdir(os.path.join(d, "x", "empty_dir")))
            with open(os.path.join(d, "x", "sce_sys", "keystone"), "rb") as f:
                self.assertEqual(f.read(), builder.keystone())
            with open(os.path.join(d, "x", "sce_sys", "param.sfo"), "rb") as f:
                self.assertIn("img0_l0_size=", Sfo.parse(f.read()).get("PUBTOOLINFO"))

    def test_doubly_indirect_signatures(self):
        # Few signatures per block, so a small file needs the doubly indirect tree.
        with mock.patch.object(builder, "SIGS_PER_BLOCK", 3), tempfile.TemporaryDirectory() as d:
            payload = os.urandom(30 * 0x10000)
            out = self.build(d, {"sce_sys/param.sfo": make_sfo(SFO), "game.bin": payload})
            self.assertEqual(validate(out), [])
            self.extract(out, os.path.join(d, "x"))
            with open(os.path.join(d, "x", "game.bin"), "rb") as f:
                self.assertEqual(f.read(), payload)

    def test_hash_collision_and_big_directory(self):
        self.assertEqual(builder._path_hash("/Ab"), builder._path_hash("/B#"))
        files = {"sce_sys/param.sfo": make_sfo(SFO), "Ab": b"one", "B#": b"two"}
        files.update({f"many/file_with_a_rather_long_name_{i:05d}.dat": b"x" for i in range(2500)})
        with tempfile.TemporaryDirectory() as d:
            out = self.build(d, files)
            self.assertEqual(validate(out), [])
            self.extract(out, os.path.join(d, "x"))
            self.assertEqual(len(os.listdir(os.path.join(d, "x", "many"))), 2500)
            with open(os.path.join(d, "x", "B#"), "rb") as f:
                self.assertEqual(f.read(), b"two")

    def test_deterministic_except_dates(self):
        files = {"sce_sys/param.sfo": make_sfo(SFO), "a.bin": b"abc" * 1000}
        with tempfile.TemporaryDirectory() as d:
            outs = []
            for name in ("1", "2"):
                os.mkdir(os.path.join(d, name))
                outs.append(self.build(os.path.join(d, name), files, file_time=1700000000))
            with open(outs[0], "rb") as a, open(outs[1], "rb") as b:
                self.assertEqual(a.read(), b.read())

    def test_rejects_non_games_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Exception):
                self.build(d, {"sce_sys/param.sfo": make_sfo(dict(SFO, CATEGORY="ac"))})
            with self.assertRaises(Exception):
                self.build(d, {"eboot.bin": b"x"})
            self.assertEqual(os.listdir(d), [])

    def test_merge_base_and_patches(self):
        cid = "UP0000-CUSA00042_00-MERGEMERGEMERGE0"
        base_sfo = {"CATEGORY": "gd", "TITLE_ID": "CUSA00042", "APP_VER": "01.00",
                    "TITLE": "Merge", "CONTENT_ID": cid, "ATTRIBUTE": 0, "FORMAT": "obs"}
        with tempfile.TemporaryDirectory() as d:
            paths = {}
            for name, sfo, files in (
                ("base", base_sfo, {"eboot.bin": b"v1", "data/a.bin": b"A" * 70000,
                                    "data/keep.bin": b"keep"}),
                ("p2", dict(base_sfo, CATEGORY="gp", APP_VER="01.02"),
                 {"eboot.bin": b"v3", "data/new.bin": b"new"}),
                ("p1", dict(base_sfo, CATEGORY="gp", APP_VER="01.01"),
                 {"eboot.bin": b"v2", "data/a.bin": b"B" * 10}),
            ):
                paths[name] = os.path.join(d, name + ".pkg")
                build_fake_pkg(paths[name], cid, sfo, files)
            out = os.path.join(d, "merged.pkg")
            result = merge.merge_pkgs([paths["p2"], paths["base"], paths["p1"]], out)
            self.assertEqual(result.version, "01.02")
            self.assertEqual(validate(out), [])
            with PkgFile(out) as p:
                self.assertEqual(p.info.category, "gd")
                self.assertEqual(p.info.app_ver, "01.02")
                self.assertEqual(p.info.content_id, cid)
            self.extract(out, os.path.join(d, "x"))
            expect = {"eboot.bin": b"v3", "data/a.bin": b"B" * 10, "data/keep.bin": b"keep",
                      "data/new.bin": b"new"}
            for path, data in expect.items():
                with open(os.path.join(d, "x", path), "rb") as f:
                    self.assertEqual(f.read(), data, path)


if __name__ == "__main__":
    unittest.main()
