import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marketplace_index import (
    default_marketplace,
    find_plugin,
    load_marketplace,
    save_marketplace,
    upsert_plugin,
)


class MarketplaceIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_default_marketplace_has_required_keys(self):
        marketplace = default_marketplace("ai", "Security Engineering skills")
        self.assertEqual(marketplace["name"], "ai")
        self.assertEqual(marketplace["plugins"], [])
        self.assertIn("$schema", marketplace)

    def test_load_returns_default_when_missing(self):
        marketplace = load_marketplace(self.tmpdir / "marketplace.json", "ai", "desc")
        self.assertEqual(marketplace["plugins"], [])

    def test_upsert_adds_new_entry(self):
        marketplace = default_marketplace("ai", "desc")
        entry = {"name": "ip-investigate", "description": "d", "author": {"name": "James Kim"}, "source": "./soc_security/ip-investigate", "category": "security"}
        upsert_plugin(marketplace, entry)
        self.assertEqual(len(marketplace["plugins"]), 1)
        self.assertEqual(marketplace["plugins"][0]["name"], "ip-investigate")

    def test_upsert_replaces_existing_entry_by_name(self):
        marketplace = default_marketplace("ai", "desc")
        original = {"name": "ip-investigate", "description": "old", "author": {"name": "James Kim"}, "source": "./soc_security/ip-investigate", "category": "security"}
        updated = {"name": "ip-investigate", "description": "new", "author": {"name": "James Kim"}, "source": "./soc_security/ip-investigate", "category": "security"}
        upsert_plugin(marketplace, original)
        upsert_plugin(marketplace, updated)
        self.assertEqual(len(marketplace["plugins"]), 1)
        self.assertEqual(marketplace["plugins"][0]["description"], "new")

    def test_find_plugin_returns_none_when_absent(self):
        marketplace = default_marketplace("ai", "desc")
        self.assertIsNone(find_plugin(marketplace, "nonexistent"))

    def test_save_then_load_round_trips(self):
        marketplace = default_marketplace("ai", "desc")
        path = self.tmpdir / "marketplace.json"
        save_marketplace(marketplace, path)
        loaded = load_marketplace(path)
        self.assertEqual(loaded, marketplace)


if __name__ == "__main__":
    unittest.main()
