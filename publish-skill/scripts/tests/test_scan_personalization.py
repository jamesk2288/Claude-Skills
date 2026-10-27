import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scan_personalization import scan_directory


class ScanPersonalizationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def write(self, name: str, content: str) -> Path:
        path = self.tmpdir / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_flags_hardcoded_windows_user_path(self):
        self.write("SKILL.md", r"Look in <REDACTED:hardcoded_user_path> for the repo." + "\n")
        findings = scan_directory(self.tmpdir)
        self.assertTrue(any(f["pattern"] == "hardcoded_user_path" for f in findings))

    def test_flags_email_address(self):
        self.write("SKILL.md", "Contact <REDACTED:email_address> for questions.\n")
        findings = scan_directory(self.tmpdir)
        self.assertTrue(any(f["pattern"] == "email_address" for f in findings))

    def test_no_findings_on_relative_paths(self):
        self.write("SKILL.md", "Look in ./scripts/helper.py for the logic.\n")
        findings = scan_directory(self.tmpdir)
        self.assertEqual(findings, [])

    def test_reports_full_matched_path(self):
        self.write("SKILL.md", r"<REDACTED:hardcoded_user_path>" + "\n")
        findings = scan_directory(self.tmpdir)
        self.assertEqual(findings[0]["matched"], r"<REDACTED:hardcoded_user_path>")

    def test_flags_hardcoded_path_in_extensionless_file(self):
        self.write("notes", r"<REDACTED:hardcoded_user_path>" + "\n")
        findings = scan_directory(self.tmpdir)
        self.assertTrue(any(f["pattern"] == "hardcoded_user_path" for f in findings))


if __name__ == "__main__":
    unittest.main()
