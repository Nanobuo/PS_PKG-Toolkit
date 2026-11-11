"""Portable mode: data folder next to the program and folders relative to it."""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pkgfree import portable  # noqa: E402


class PortableDataDir(unittest.TestCase):
    def test_created_next_to_program_and_settings_migrated(self):
        # Settings of an installed copy of PKG Free (the old name) are carried over.
        with tempfile.TemporaryDirectory() as d:
            prog = os.path.join(d, "stick", "PS-PKG-Toolkit")
            os.makedirs(prog)
            appdata = os.path.join(d, "appdata")
            os.makedirs(os.path.join(appdata, "PkgFree"))
            with open(os.path.join(appdata, "PkgFree", "config.json"), "w") as f:
                json.dump({"Paths": {"GamesDir": "X"}}, f)
            with mock.patch.dict(os.environ, {"APPDATA": appdata}):
                data = portable.portable_data_dir(prog, platform="win32")
            self.assertEqual(data, os.path.join(prog, "PS-PKG-Toolkit-data"))
            with open(os.path.join(data, "config.json")) as f:
                self.assertEqual(json.load(f)["Paths"]["GamesDir"], "X")

    def test_existing_folder_is_used_even_on_macos(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(portable.portable_data_dir(d, platform="darwin"))
            os.mkdir(os.path.join(d, "PS-PKG-Toolkit-data"))
            self.assertEqual(portable.portable_data_dir(d, platform="darwin"),
                             os.path.join(d, "PS-PKG-Toolkit-data"))

    def test_old_portable_folder_is_renamed(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "PkgFree-data"))
            with open(os.path.join(d, "PkgFree-data", "config.json"), "w") as f:
                f.write("{}")
            data = portable.portable_data_dir(d, platform="darwin")
            self.assertEqual(data, os.path.join(d, "PS-PKG-Toolkit-data"))
            self.assertTrue(os.path.isfile(os.path.join(data, "config.json")))
            self.assertFalse(os.path.exists(os.path.join(d, "PkgFree-data")))

    def test_installed_copy_takes_old_settings(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"APPDATA": d}):
            os.makedirs(os.path.join(d, "PkgFree"))
            with open(os.path.join(d, "PkgFree", "config.json"), "w") as f:
                f.write('{"a": 1}')
            portable.carry_over_settings(portable.user_data_dir())
            with open(os.path.join(d, "PS-PKG-Toolkit", "config.json")) as f:
                self.assertEqual(f.read(), '{"a": 1}')

    def test_not_portable_from_source_or_read_only_folder(self):
        self.assertIsNone(portable.portable_data_dir(None))
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "missing", "deeper")  # mkdir fails: no parent
            self.assertIsNone(portable.portable_data_dir(missing, platform="win32"))


class StoredPaths(unittest.TestCase):
    def test_relative_on_same_removable_volume(self):
        with mock.patch.object(portable, "_volume", lambda p: "E:"), \
                mock.patch.object(portable, "_system_volumes", lambda: {"C:"}):
            base = os.path.abspath(os.path.join("stick", "PS-PKG-Toolkit"))
            games = os.path.abspath(os.path.join("stick", "Giochi"))
            stored = portable.to_stored(games, base)
            self.assertEqual(stored, "../Giochi")
            self.assertEqual(portable.from_stored(stored, base), games)

    def test_absolute_on_system_or_other_volume(self):
        base = os.path.abspath("PS-PKG-Toolkit")
        games = os.path.abspath("Giochi")
        with mock.patch.object(portable, "_volume", lambda p: "C:"), \
                mock.patch.object(portable, "_system_volumes", lambda: {"C:"}):
            self.assertEqual(portable.to_stored(games, base), games)
        with mock.patch.object(portable, "_volume", lambda p: "E:" if p == base else "D:"), \
                mock.patch.object(portable, "_system_volumes", lambda: {"C:"}):
            self.assertEqual(portable.to_stored(games, base), games)

    def test_not_portable_keeps_values(self):
        self.assertEqual(portable.to_stored("/x/y", None), "/x/y")
        self.assertEqual(portable.from_stored("../y", None), "../y")
        self.assertEqual(portable.from_stored("", "/base"), "")


if __name__ == "__main__":
    unittest.main()
