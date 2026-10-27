import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scan_secrets import scan_directory


class ScanSecretsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def write(self, name: str, content: str) -> Path:
        path = self.tmpdir / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_flags_generic_secret_assignment(self):
        self.write("SKILL.md", '<REDACTED:generic_secret_assignment>\n')
        findings = scan_directory(self.tmpdir)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["pattern"], "generic_secret_assignment")

    def test_flags_aws_access_key(self):
        self.write("config.json", '{"key": "<REDACTED:aws_access_key>"}')
        findings = scan_directory(self.tmpdir)
        self.assertTrue(any(f["pattern"] == "aws_access_key" for f in findings))

    def test_flags_private_key_header(self):
        self.write("id_rsa.txt", "<REDACTED:private_key_header>\nMIIEpAIBAAKCAQEA\n")
        findings = scan_directory(self.tmpdir)
        self.assertTrue(any(f["pattern"] == "private_key_header" for f in findings))

    def test_no_findings_on_clean_file(self):
        self.write("README.md", "# My Skill\n\nThis skill does normal things with no secrets.\n")
        findings = scan_directory(self.tmpdir)
        self.assertEqual(findings, [])

    def test_skips_non_text_extensions(self):
        self.write("image.png", "<REDACTED:aws_access_key>")
        findings = scan_directory(self.tmpdir)
        self.assertEqual(findings, [])

    def test_reports_correct_line_number(self):
        self.write("SKILL.md", 'line one\nline two\n<REDACTED:generic_secret_assignment>\n')
        findings = scan_directory(self.tmpdir)
        self.assertEqual(findings[0]["line"], 3)

    def test_flags_secret_in_dotenv_file(self):
        self.write(".env", '<REDACTED:generic_secret_assignment>\n')
        findings = scan_directory(self.tmpdir)
        self.assertTrue(any(f["pattern"] == "generic_secret_assignment" for f in findings))

    def test_flags_private_key_header_in_extensionless_file(self):
        self.write("id_rsa", "<REDACTED:private_key_header>\nMIIEpAIBAAKCAQEA\n")
        findings = scan_directory(self.tmpdir)
        self.assertTrue(any(f["pattern"] == "private_key_header" for f in findings))


if __name__ == "__main__":
    unittest.main()
