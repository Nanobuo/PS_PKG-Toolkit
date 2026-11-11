"""Tests for resume, free-space check, integrity check and PKG removal."""

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PSPKG_LANG"] = "it"  # messages checked by the tests are Italian

from fake_pkg_builder import build_pkg  # noqa: E402
from pkgfree import installer  # noqa: E402
from pkgfree.pkg import Cancelled, PkgError, PkgFile  # noqa: E402

CID = "UP0000-CUSA00042_00-GAMEGAMEGAME0000"
SFO = {"CATEGORY": "gd", "TITLE_ID": "CUSA00042", "APP_VER": "01.00", "TITLE": "Feature Test"}
FILES = {f"data/f{i}.bin": os.urandom(150_000) for i in range(6)}
FILES["eboot.bin"] = b"EBOOT-100"


class Features(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.base = self.p("base.pkg")
        build_pkg(self.base, CID, SFO, FILES)
        self.upd = self.p("upd.pkg")
        build_pkg(self.upd, CID, dict(SFO, CATEGORY="gp", APP_VER="01.01"),
                  {"eboot.bin": b"EBOOT-101", "data/f0.bin": b"patched"})
        self.games = self.p("games")

    def tearDown(self):
        self.tmp.cleanup()

    def p(self, *a):
        return os.path.join(self.d, *a)

    def plan(self, *paths):
        return installer.build_plan([installer.read_info(x) for x in paths], self.games)

    def game(self, *a):
        return pathlib.Path(self.games, "CUSA00042", *a)

    # -- integrity -----------------------------------------------------------------
    def test_verify_ok_and_detects_corruption(self):
        with PkgFile(self.base) as pkg:
            self.assertEqual({c.name: c.status for c in pkg.verify()},
                             {"header": "ok", "body": "ok", "pfs": "ok"})
        data = bytearray(pathlib.Path(self.base).read_bytes())
        with PkgFile(self.base) as pkg:
            off = pkg.info.pfs_image_offset + pkg.info.pfs_image_size - 10
        data[off] ^= 0xFF
        pathlib.Path(self.base).write_bytes(data)
        with PkgFile(self.base) as pkg:
            status = {c.name: c.status for c in pkg.verify()}
        self.assertEqual(status["pfs"], "mismatch")
        self.assertEqual(status["header"], "ok")
        with self.assertRaises(PkgError) as ctx:
            installer.install(self.plan(self.base), self.games, self.p("dlc"),
                              log=lambda m: None, verify=True)
        self.assertIn("danneggiato", str(ctx.exception))

    def test_verify_without_digests(self):
        path = self.p("nodigest.pkg")
        build_pkg(path, CID, SFO, {"eboot.bin": b"x"}, digests=False)
        with PkgFile(path) as pkg:
            self.assertEqual({c.status for c in pkg.verify()}, {"absent"})
        logs = []
        installer.install(self.plan(path), self.games, self.p("dlc"), log=logs.append,
                          verify=True)
        self.assertTrue(any("non verificabile" in m for m in logs))

    # -- resume --------------------------------------------------------------------
    def test_resume_after_cancel(self):
        plan = self.plan(self.base, self.upd)
        written = []
        real_extract = PkgFile.extract

        def counting_extract(pkg, dest, *a, on_file_done=None, **kw):
            def done(path):
                written.append(path)
                on_file_done(path)
            return real_extract(pkg, dest, *a, on_file_done=done, **kw)

        def cancel_after_three():
            return len(written) >= 3

        with mock.patch.object(PkgFile, "extract", counting_extract):
            with self.assertRaises(Cancelled):
                installer.install(plan, self.games, self.p("dlc"), log=lambda m: None,
                                  should_cancel=cancel_after_three)
        self.assertEqual(len(written), 3)
        journals = list(self.game().glob(".pkgfree-*.resume"))
        self.assertEqual(len(journals), 1)

        # Second run: the three finished files are not rewritten.
        with mock.patch.object(PkgFile, "extract", counting_extract):
            written.clear()
            logs = []
            installer.install(plan, self.games, self.p("dlc"), log=logs.append,
                              should_cancel=lambda: False)
            rewritten = list(written)
        self.assertTrue(any("ripresa" in m for m in logs))
        # base: 7 files minus the 3 already done; update: 2 files.
        self.assertEqual(len(rewritten), len(FILES) - 3 + 2)
        self.assertEqual(self.game("eboot.bin").read_bytes(), b"EBOOT-101")
        self.assertEqual(self.game("data", "f0.bin").read_bytes(), b"patched")
        for name, data in FILES.items():
            if name not in ("eboot.bin", "data/f0.bin"):
                self.assertEqual(self.game(*name.split("/")).read_bytes(), data)
        self.assertEqual(list(self.game().glob(".pkgfree-*.resume")), [])

    def test_resume_skips_finished_pkgs(self):
        plan = self.plan(self.base, self.upd)
        statuses = []
        cancel = {"on": False}

        def item_status(idx, state):
            statuses.append((idx, state))
            if idx == 1 and state == "start":
                cancel["on"] = True

        with self.assertRaises(Cancelled):
            installer.install(plan, self.games, self.p("dlc"), log=lambda m: None,
                              item_status=item_status, should_cancel=lambda: cancel["on"])
        statuses.clear()
        installer.install(plan, self.games, self.p("dlc"), log=lambda m: None,
                          item_status=lambda i, s: statuses.append((i, s)))
        self.assertIn((0, "skipped"), statuses)
        self.assertIn((1, "done"), statuses)
        self.assertEqual(self.game("eboot.bin").read_bytes(), b"EBOOT-101")

    def test_journal_of_another_plan_is_ignored(self):
        plan = self.plan(self.base)
        installer.Journal(installer.journal_path(str(self.game()), plan.all_items()[0]),
                          [["other.pkg", 1]], keep=False).complete()
        statuses = []
        installer.install(plan, self.games, self.p("dlc"), log=lambda m: None,
                          item_status=lambda i, s: statuses.append((i, s)))
        self.assertNotIn((0, "skipped"), statuses)
        self.assertEqual(self.game("eboot.bin").read_bytes(), b"EBOOT-100")

    # -- free space ------------------------------------------------------------------
    def test_space_needed_counts_final_sizes(self):
        plan = self.plan(self.base, self.upd)
        needed = installer.space_needed(plan, self.games, self.p("dlc"), False)
        expected = sum(len(v) for k, v in FILES.items()
                       if k not in ("eboot.bin", "data/f0.bin")) + len(b"EBOOT-101") + len(b"patched")
        self.assertEqual(sum(needed.values()), expected)
        self.assertEqual(installer.check_space(plan, self.games, self.p("dlc"), False), [])
        fake = mock.Mock(free=10)
        with mock.patch("pkgfree.installer.shutil.disk_usage", return_value=fake):
            short = installer.check_space(plan, self.games, self.p("dlc"), False)
        self.assertEqual(len(short), 1)
        self.assertEqual(short[0].needed, expected)
        # Already extracted: nothing more is needed.
        installer.install(plan, self.games, self.p("dlc"), log=lambda m: None)
        self.assertEqual(sum(installer.space_needed(plan, self.games, self.p("dlc"),
                                                    False).values()), 0)

    # -- removing PKGs ---------------------------------------------------------------
    def test_remove_pkgs_only_after_success(self):
        removed = []
        with self.assertRaises(Cancelled):
            installer.install(self.plan(self.base), self.games, self.p("dlc"),
                              log=lambda m: None, should_cancel=lambda: True,
                              remove_pkg=removed.append)
        self.assertEqual(removed, [])
        installer.install(self.plan(self.base, self.upd), self.games, self.p("dlc"),
                          log=lambda m: None, remove_pkg=os.remove)
        self.assertFalse(os.path.exists(self.base))
        self.assertFalse(os.path.exists(self.upd))


class Library(unittest.TestCase):
    def test_scan_library(self):
        with tempfile.TemporaryDirectory() as d:
            games, addons = os.path.join(d, "games"), os.path.join(d, "addcont")
            mk = lambda name, sfo, files: build_pkg(os.path.join(d, name), sfo.pop("_cid"), sfo,
                                                    files)  # noqa: E731
            mk("a.pkg", {"_cid": "UP0000-CUSA00001_00-AAAAAAAAAAAAAAAA", "CATEGORY": "gd",
                         "TITLE_ID": "CUSA00001", "APP_VER": "01.00", "TITLE": "Zeta"},
               {"eboot.bin": b"a"})
            mk("au.pkg", {"_cid": "UP0000-CUSA00001_00-AAAAAAAAAAAAAAAA", "CATEGORY": "gp",
                          "TITLE_ID": "CUSA00001", "APP_VER": "01.05", "TITLE": "Zeta"},
               {"eboot.bin": b"a2"})
            mk("ad.pkg", {"_cid": "UP0000-CUSA00001_00-DLCDLCDLCDLC0001", "CATEGORY": "ac",
                          "TITLE_ID": "CUSA00001", "TITLE": "Zeta Pack"}, {"x": b"x"})
            mk("b.pkg", {"_cid": "UP0000-CUSA00002_00-BBBBBBBBBBBBBBBB", "CATEGORY": "gd",
                         "TITLE_ID": "CUSA00002", "APP_VER": "01.00", "TITLE": "Alfa"},
               {"eboot.bin": b"b"})
            infos = [installer.read_info(os.path.join(d, n)) for n in ("a.pkg", "au.pkg", "ad.pkg")]
            installer.install(installer.build_plan(infos, games, title_folder=True), games,
                              addons, separate_update=True, log=lambda m: None)
            infos = [installer.read_info(os.path.join(d, "b.pkg"))]
            installer.install(installer.build_plan(infos, games), games, addons,
                              log=lambda m: None)
            lib = installer.scan_library(games, addons)
            self.assertEqual([(e.title, e.title_id, e.version) for e in lib],
                             [("Alfa", "CUSA00002", "01.00"), ("Zeta", "CUSA00001", "01.05")])
            zeta = lib[1]
            self.assertTrue(zeta.update_dir.endswith("CUSA00001-UPDATE"))
            self.assertEqual(zeta.dlcs, ["Zeta Pack"])
            self.assertTrue(zeta.icon.endswith("icon0.png"))
            self.assertEqual(installer.scan_library(os.path.join(d, "missing"), addons), [])


if __name__ == "__main__":
    unittest.main()
