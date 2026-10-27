"""Heuristic scanner for hardcoded secrets/credentials in a skill's source files."""
import json
import re
import sys
from pathlib import Path

SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic_secret_assignment", re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|credential)\s*[=:]\s*['\"][^'\"]{8,}['\"]"
    )),
    ("private_key_header", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PGP|DSA) PRIVATE KEY-----")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z]{10,48}")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.]{20,}")),
]

TEXT_EXTENSIONS = {
    ".md", ".py", ".json", ".sh", ".js", ".ts", ".yml", ".yaml", ".txt", ".claud",
    ".pem", ".key",
}


def scan_file(path: Path) -> list[dict]:
    findings = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern_name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "file": str(path),
                    "line": line_number,
                    "pattern": pattern_name,
                    "snippet": line.strip()[:200],
                })
    return findings


def scan_directory(root: Path) -> list[dict]:
    findings = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix and path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        findings.extend(scan_file(path))
    return findings


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: scan_secrets.py <directory>", file=sys.stderr)
        return 2
    findings = scan_directory(Path(sys.argv[1]))
    print(json.dumps(findings, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
