"""Tests for the in-app updater (no network: file:// URLs)."""

import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pkgfree import updater  # noqa: E402


def release_json(name, url, data, digest=True):
    return {
        "tag_name": "v9.1.0", "body": "- novità", "html_url": "https://example.invalid/r",
        "assets": [
            {"name": "other.bin", "browser_download_url": "file:///nope", "size": 1},
            {"name": name, "browser_download_url": url, "size": len(data),
             "digest": "sha256:" + hashlib.sha256(data).hexdigest() if digest else None},
        ],
    }


class Updater(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_versions_and_assets(self):
        self.assertTrue(updater.is_newer("1.10.0", "1.9.3"))
        self.assertFalse(updater.is_newer("1.3.0", "1.3.0"))
        self.assertFalse(updater.is_newer("1.2.9", "1.3.0"))
        self.assertEqual(updater.asset_name("win32"), "PS-PKG-Toolkit-windows-x64.exe")
        self.assertEqual(updater.asset_name("linux"), "PS-PKG-Toolkit-linux-x86_64.AppImage")
        self.assertEqual(updater.asset_name("darwin"), "PS-PKG-Toolkit-macos-arm64.zip")
        rel = updater.release_from_json(release_json("PS-PKG-Toolkit-linux-x86_64.AppImage", "u", b"x"),
                                        "linux")
        self.assertEqual((rel.version, rel.tag, rel.asset_url), ("9.1.0", "v9.1.0", "u"))
        self.assertEqual(rel.asset_sha256, hashlib.sha256(b"x").hexdigest())
        none = updater.release_from_json(release_json("PS-PKG-Toolkit-linux-x86_64.AppImage", "u", b"x"),
                                         "win32")
        self.assertIsNone(none.asset_url)

    def test_fetch_and_download(self):
        payload = os.urandom(3 * updater.CHUNK + 5)
        src = self.d / "asset.bin"
        src.write_bytes(payload)
        meta = self.d / "latest.json"
        meta.write_text(json.dumps(release_json(updater.asset_name(), src.as_uri(), payload)))
        rel = updater.fetch_latest(meta.as_uri())
        self.assertEqual(rel.version, "9.1.0")
        seen = []
        out = updater.download(rel, str(self.d / "dl"), progress=lambda d, t: seen.append(d))
        self.assertEqual(pathlib.Path(out).read_bytes(), payload)
        self.assertEqual(seen[-1], len(payload))

        rel.asset_sha256 = "0" * 64
        with self.assertRaises(updater.UpdateError):
            updater.download(rel, str(self.d / "dl2"))
        self.assertFalse((self.d / "dl2").exists())

        with self.assertRaises(updater.UpdateError):
            updater.fetch_latest((self.d / "missing.json").as_uri())

    def test_apply_replaces_target(self):
        for platform in ("linux", "win32"):
            target = self.d / f"PS-PKG-Toolkit-{platform}"
            target.write_bytes(b"old")
            new = pathlib.Path(updater.staging_path(str(target)))
            new.write_bytes(b"new")
            updater.apply_update(str(new), str(target), platform)
            self.assertEqual(target.read_bytes(), b"new")
            self.assertFalse(new.exists())
            if platform == "linux":
                self.assertTrue(os.access(target, os.X_OK))
            else:
                self.assertEqual(pathlib.Path(str(target) + ".old").read_bytes(), b"old")
                updater.cleanup_previous(str(target))
                self.assertFalse(pathlib.Path(str(target) + ".old").exists())

    def test_not_frozen_cannot_self_update(self):
        self.assertIsNone(updater.install_target())


if __name__ == "__main__":
    unittest.main()
