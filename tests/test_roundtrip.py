import contextlib
import io
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PSPKG_LANG"] = "it"  # messages checked by the tests are Italian

from fake_pkg_builder import build_pkg  # noqa: E402
from pkgfree import installer  # noqa: E402
from pkgfree.pkg import PkgError, PkgFile  # noqa: E402

BIG = os.urandom(300_000) + b"\x00" * 200_000  # spans several blocks, mixes raw/compressed


class RoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def p(self, *a):
        return os.path.join(self.d, *a)

    def test_full_install(self):
        base_files = {"eboot.bin": b"BASE-EBOOT", "data/big.bin": BIG,
                      "data/keep.txt": b"keep", "sce_module/libc.prx": b"prx", "empty.dat": b""}
        np = build_pkg(self.p("base.pkg"), "UP0000-CUSA00001_00-GAMEGAMEGAME0000",
                       {"CATEGORY": "gd", "TITLE_ID": "CUSA00001", "APP_VER": "01.00",
                        "TITLE": "Test Game"}, base_files)
        build_pkg(self.p("upd2.pkg"), "UP0000-CUSA00001_00-GAMEGAMEGAME0000",
                  {"CATEGORY": "gp", "TITLE_ID": "CUSA00001", "APP_VER": "01.02"},
                  {"eboot.bin": b"EBOOT-v102", "data/new.txt": b"new2"})
        build_pkg(self.p("upd1.pkg"), "UP0000-CUSA00001_00-GAMEGAMEGAME0000",
                  {"CATEGORY": "gp", "TITLE_ID": "CUSA00001", "APP_VER": "01.01"},
                  {"eboot.bin": b"EBOOT-v101", "data/new.txt": b"new1"})
        build_pkg(self.p("dlc.pkg"), "UP0000-CUSA00001_00-DLCPACK000000001",
                  {"CATEGORY": "ac", "TITLE_ID": "CUSA00001"}, {"dlc/a.bin": b"dlc-a"})
        build_pkg(self.p("unlock.pkg"), "UP0000-CUSA00001_00-UNLOCKKEY0000002",
                  {"CATEGORY": "ac", "TITLE_ID": "CUSA00001"}, {}, with_pfs=False)

        with PkgFile(self.p("base.pkg")) as pkg:
            self.assertEqual(pkg.info.kind, "game")
            self.assertEqual(pkg.info.title_id, "CUSA00001")
            names = {n.path for n in pkg.list_files()}
            self.assertIn("data/big.bin", names)

        infos = [installer.read_info(self.p(n)) for n in
                 ("dlc.pkg", "upd2.pkg", "base.pkg", "upd1.pkg", "unlock.pkg")]
        games, addons = self.p("games"), self.p("addcont")
        plan = installer.build_plan(infos, games)
        self.assertEqual(plan.warnings, [])
        installer.install(plan, games, addons, log=lambda m: None)

        g = self.p("games", "CUSA00001")
        read = lambda *a: pathlib.Path(*a).read_bytes()  # noqa: E731
        self.assertEqual(read(g, "eboot.bin"), b"EBOOT-v102")
        self.assertEqual(read(g, "data", "new.txt"), b"new2")
        self.assertEqual(read(g, "data", "big.bin"), BIG)
        self.assertEqual(read(g, "data", "keep.txt"), b"keep")
        self.assertEqual(read(g, "empty.dat"), b"")
        self.assertEqual(read(g, "sce_sys", "nptitle.dat"), np)
        self.assertEqual(read(g, "sce_sys", "icon0.png"), b"ICONDATA")
        from pkgfree.sfo import parse_sfo
        self.assertEqual(parse_sfo(read(g, "sce_sys", "param.sfo"))["APP_VER"], "01.02")
        self.assertEqual(read(addons, "CUSA00001", "DLCPACK000000001", "dlc", "a.bin"), b"dlc-a")
        self.assertTrue(os.path.isfile(
            os.path.join(addons, "CUSA00001", "UNLOCKKEY0000002", "sce_sys", "param.sfo")))

    def test_new_crypt_flag(self):
        build_pkg(self.p("n.pkg"), "UP0000-CUSA00003_00-GAMEGAMEGAME0000",
                  {"CATEGORY": "gd", "TITLE_ID": "CUSA00003"}, {"eboot.bin": BIG},
                  new_crypt=True)
        with PkgFile(self.p("n.pkg")) as pkg:
            pkg.extract(self.p("out"))
        self.assertEqual(pathlib.Path(self.p("out", "eboot.bin")).read_bytes(), BIG)

    def test_key_derivation_flag_mismatch(self):
        # Real-world fPKGs do not always set the "new crypt" flag consistently.
        cases = [
            dict(new_crypt=True, flag_new_crypt=False),
            dict(new_crypt=False, flag_new_crypt=True),
            dict(new_crypt=True, flag_new_crypt=False, outer_superroot=False),
            dict(new_crypt=False, outer_superroot=False, pfsc_offset=0x23000),
        ]
        for i, kw in enumerate(cases):
            with self.subTest(**kw):
                path = self.p(f"m{i}.pkg")
                build_pkg(path, "UP0000-CUSA00004_00-GAMEGAMEGAME0000",
                          {"CATEGORY": "gd", "TITLE_ID": "CUSA00004"}, {"eboot.bin": BIG}, **kw)
                with PkgFile(path) as pkg:
                    pkg.extract(self.p(f"o{i}"))
                self.assertEqual(pathlib.Path(self.p(f"o{i}", "eboot.bin")).read_bytes(), BIG)

    def test_wrong_key_reports_details(self):
        path = self.p("bad.pkg")
        build_pkg(path, "UP0000-CUSA00005_00-GAMEGAMEGAME0000",
                  {"CATEGORY": "gd", "TITLE_ID": "CUSA00005"}, {"eboot.bin": b"x"})
        data = bytearray(pathlib.Path(path).read_bytes())
        with PkgFile(path) as pkg:
            pfs = pkg.info.pfs_image_offset
        data[pfs + 0x370] ^= 0xFF  # corrupt the seed: no key can work any more
        pathlib.Path(path).write_bytes(data)
        with PkgFile(path) as pkg:
            with self.assertRaises(PkgError) as ctx:
                pkg.extract(self.p("bad"))
        self.assertIn("provate", str(ctx.exception))

    def test_installed_version_check(self):
        cid = "UP0000-CUSA00006_00-GAMEGAMEGAME0000"
        sfo = {"CATEGORY": "gd", "TITLE_ID": "CUSA00006", "APP_VER": "01.00"}
        build_pkg(self.p("base.pkg"), cid, sfo, {"eboot.bin": b"v100"})
        build_pkg(self.p("u103.pkg"), cid, dict(sfo, CATEGORY="gp", APP_VER="01.03"),
                  {"eboot.bin": b"v103"})
        build_pkg(self.p("u102.pkg"), cid, dict(sfo, CATEGORY="gp", APP_VER="01.02"),
                  {"eboot.bin": b"v102"})
        games = self.p("games")
        quiet = dict(log=lambda m: None)

        def plan(*names):
            return installer.build_plan([installer.read_info(self.p(n)) for n in names], games)

        installer.install(plan("base.pkg", "u103.pkg"), games, self.p("dlc"), **quiet)
        game_dir = installer.find_game_dir(games, "CUSA00006")
        self.assertEqual(installer.installed_version(game_dir), "01.03")

        older = plan("u102.pkg")
        self.assertEqual(len(older.downgrades), 1)
        self.assertIn("01.03", older.downgrades[0])
        self.assertEqual(plan("base.pkg").downgrades[0].count("01.00"), 1)
        same = plan("u103.pkg")
        self.assertEqual(same.downgrades, [])
        self.assertTrue(any("già installata" in w for w in same.warnings))
        self.assertEqual(plan("base.pkg", "u102.pkg", "u103.pkg").downgrades, [])

        from pkgfree import cli
        rc = cli.main(["install", self.p("u102.pkg"), "-o", games])
        self.assertEqual(rc, 1)
        self.assertEqual(pathlib.Path(games, "CUSA00006", "eboot.bin").read_bytes(), b"v103")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cli.main(["install", self.p("u102.pkg"), "-o", games, "--force"])
        self.assertEqual(rc, 0)
        self.assertEqual(pathlib.Path(games, "CUSA00006", "eboot.bin").read_bytes(), b"v102")

    def test_title_folder(self):
        cid = "UP0000-CUSA00003_00-DRIVECLUBGAME000"
        sfo = {"CATEGORY": "gd", "TITLE_ID": "CUSA00003", "APP_VER": "01.00",
               "TITLE": "DRIVECLUB™: Edizione?"}
        build_pkg(self.p("base.pkg"), cid, sfo, {"eboot.bin": b"v100"})
        build_pkg(self.p("upd.pkg"), cid, dict(sfo, CATEGORY="gp", APP_VER="01.28"),
                  {"eboot.bin": b"v128"})
        build_pkg(self.p("dlc.pkg"), "UP0000-CUSA00003_00-DLCPACK000000001",
                  {"CATEGORY": "ac", "TITLE_ID": "CUSA00003", "TITLE": "DLC"}, {"d": b"d"})
        games, addons = self.p("games"), self.p("addcont")
        quiet = dict(log=lambda m: None)

        def plan(*names, **kw):
            infos = [installer.read_info(self.p(n)) for n in names]
            return installer.build_plan(infos, games, title_folder=True, **kw)

        installer.install(plan("base.pkg", "dlc.pkg"), games, addons, **quiet)
        root = pathlib.Path(games, "DRIVECLUB™ - Edizione", "CUSA00003")
        self.assertEqual((root / "eboot.bin").read_bytes(), b"v100")
        self.assertTrue(pathlib.Path(addons, "CUSA00003", "DLCPACK000000001", "d").is_file())

        # A later update alone finds the game in its title folder.
        p = plan("upd.pkg")
        self.assertEqual(p.warnings, [])
        installer.install(p, games, addons, separate_update=True, **quiet)
        self.assertEqual(pathlib.Path(f"{root}-UPDATE", "eboot.bin").read_bytes(), b"v128")
        self.assertEqual(installer.installed_version(str(root)), "01.28")

        # A game already extracted the old way (<games>/<ID>) stays where it is.
        old = pathlib.Path(self.p("games2"), "CUSA00003")
        old.mkdir(parents=True)
        infos = [installer.read_info(self.p("upd.pkg"))]
        p2 = installer.build_plan(infos, self.p("games2"), title_folder=True)
        self.assertEqual(p2.groups["CUSA00003"].game_dir(self.p("games2")), str(old))

    def test_safe_folder_name(self):
        name = installer.safe_folder_name
        self.assertEqual(name("Marvel's Spider-Man: Miles Morales", "X"),
                         "Marvel's Spider-Man - Miles Morales")
        self.assertEqual(name('A/B\\C|D<E>"F?*', "X"), "A-B-C-DEF")
        self.assertEqual(name("Title.  ", "X"), "Title")
        self.assertEqual(name("Line1\nLine2", "X"), "Line1 Line2")
        self.assertEqual(name("CON", "X"), "CON_")
        self.assertEqual(name(" ?* ", "CUSA1"), "CUSA1")

    def test_separate_update(self):
        build_pkg(self.p("upd.pkg"), "UP0000-CUSA00002_00-GAMEGAMEGAME0000",
                  {"CATEGORY": "gp", "TITLE_ID": "CUSA00002", "APP_VER": "01.01"},
                  {"eboot.bin": b"E"})
        plan = installer.build_plan([installer.read_info(self.p("upd.pkg"))], self.p("g"))
        self.assertEqual(len(plan.warnings), 1)
        installer.install(plan, self.p("g"), self.p("a"), separate_update=True, log=lambda m: None)
        self.assertTrue(os.path.isfile(self.p("g", "CUSA00002-UPDATE", "eboot.bin")))


if __name__ == "__main__":
    unittest.main()
