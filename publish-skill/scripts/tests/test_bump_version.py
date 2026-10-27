import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bump_version import bump_version


class BumpVersionTests(unittest.TestCase):
    def test_bumps_patch(self):
        self.assertEqual(bump_version("1.0.0", "patch"), "1.0.1")

    def test_bumps_minor_resets_patch(self):
        self.assertEqual(bump_version("1.0.5", "minor"), "1.1.0")

    def test_bumps_major_resets_minor_and_patch(self):
        self.assertEqual(bump_version("1.2.3", "major"), "2.0.0")

    def test_invalid_part_raises(self):
        with self.assertRaises(ValueError):
            bump_version("1.0.0", "bogus")

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            bump_version("not-a-version", "patch")


if __name__ == "__main__":
    unittest.main()
