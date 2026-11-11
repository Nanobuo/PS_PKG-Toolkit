"""Smoke test of the Fluent GUI (skipped when PySide6 is not installed)."""

import glob
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PSPKG_LANG"] = "it"  # messages checked by the tests are Italian

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    import qfluentwidgets  # noqa: F401
except Exception as ex:  # pragma: no cover - depends on the environment
    QApplication = None
    SKIP_REASON = f"GUI non disponibile: {ex}"

from fake_pkg_builder import build_pkg  # noqa: E402


@unittest.skipIf(QApplication is None, globals().get("SKIP_REASON", ""))
class GuiSmoke(unittest.TestCase):
    def test_add_and_extract(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["APPDATA"] = os.path.join(d, "appdata")
            app = QApplication.instance() or QApplication([])
            from qfluentwidgets import Theme, setTheme
            from pkgfree.gui.config import cfg, load_config
            load_config()
            cfg.set(cfg.checkUpdates, False)
            cfg.set(cfg.gamesDir, os.path.join(d, "games"))
            cid = "UP0000-CUSA00007_00-GAMEGAMEGAME0000"
            build_pkg(os.path.join(d, "base.pkg"), cid,
                      {"CATEGORY": "gd", "TITLE_ID": "CUSA00007", "APP_VER": "01.00",
                       "TITLE": "Gui Test"}, {"eboot.bin": b"old", "a.txt": b"a"})
            build_pkg(os.path.join(d, "upd.pkg"), cid,
                      {"CATEGORY": "gp", "TITLE_ID": "CUSA00007", "APP_VER": "01.01",
                       "TITLE": "Gui Test"}, {"eboot.bin": b"new"})
            from pkgfree.gui.window import MainWindow
            w = MainWindow()
            w.show()
            w.extractPage.add_paths(sorted(glob.glob(os.path.join(d, "*.pkg"))))
            self.assertEqual(len(w.extractPage.cards), 1)
            cfg.set(cfg.themeMode, Theme.DARK)
            setTheme(Theme.DARK)
            w.start_extraction()
            loop = QEventLoop()
            w.worker.finished.connect(loop.quit)
            QTimer.singleShot(30000, loop.quit)
            if w.worker.isRunning():
                loop.exec()
            app.processEvents()
            game = pathlib.Path(d, "games", "Gui Test", "CUSA00007")
            self.assertEqual((game / "eboot.bin").read_bytes(), b"new")
            self.assertEqual((game / "a.txt").read_bytes(), b"a")
            self.assertEqual(w.progressPage.title.text(), "Estrazione completata")

            # Same PKGs merged into a new one from the game card.
            out = os.path.join(d, "merged.pkg")
            card = w.extractPage.cards[0]
            from qfluentwidgets import PushButton
            button = next(b for b in card.findChildren(PushButton) if b.text() == "Crea PKG")
            with mock.patch("pkgfree.gui.window.QFileDialog.getSaveFileName",
                            return_value=(out, "")):
                button.click()
            loop = QEventLoop()
            w.worker.finished.connect(loop.quit)
            QTimer.singleShot(30000, loop.quit)
            if w.worker.isRunning():
                loop.exec()
            app.processEvents()
            self.assertEqual(w.progressPage.title.text(), "PKG creato")
            from pkgfree.pkg import PkgFile
            with PkgFile(out) as merged:
                self.assertEqual(merged.info.app_ver, "01.01")
                self.assertEqual(merged.info.category, "gd")
            w.close()
            w.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
