import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugin_manifest import build_plugin_manifest, load_plugin_manifest, save_plugin_manifest


class PluginManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_load_returns_none_when_missing(self):
        self.assertIsNone(load_plugin_manifest(self.tmpdir / "plugin.json"))

    def test_save_then_load_round_trips(self):
        manifest = build_plugin_manifest("ip-investigate", "Investigate an IP", "1.0.0", "James Kim", "<REDACTED:email_address>")
        path = self.tmpdir / ".claude-plugin" / "plugin.json"
        save_plugin_manifest(manifest, path)
        loaded = load_plugin_manifest(path)
        self.assertEqual(loaded, manifest)

    def test_build_omits_email_when_not_given(self):
        manifest = build_plugin_manifest("ip-investigate", "Investigate an IP", "1.0.0", "James Kim")
        self.assertNotIn("email", manifest["author"])

    def test_build_includes_email_when_given(self):
        manifest = build_plugin_manifest("ip-investigate", "Investigate an IP", "1.0.0", "James Kim", "<REDACTED:email_address>")
        self.assertEqual(manifest["author"]["email"], "<REDACTED:email_address>")


if __name__ == "__main__":
    unittest.main()
