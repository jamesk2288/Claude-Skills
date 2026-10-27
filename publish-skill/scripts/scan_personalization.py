"""Heuristic scanner for machine/user-specific content in a skill's source files."""
import json
import re
import sys
from pathlib import Path

WINDOWS_USER_PATH = re.compile(r"[A-Za-z]:\\Users\\[^\s\"']+")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

TEXT_EXTENSIONS = {".md", ".py", ".json", ".sh", ".js", ".ts", ".yml", ".yaml", ".txt", ".claud"}


def scan_file(path: Path) -> list[dict]:
    findings = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in WINDOWS_USER_PATH.finditer(line):
            findings.append({
                "file": str(path),
                "line": line_number,
                "pattern": "hardcoded_user_path",
                "snippet": line.strip()[:200],
                "matched": match.group(0),
            })
        for match in EMAIL.finditer(line):
            findings.append({
                "file": str(path),
                "line": line_number,
                "pattern": "email_address",
                "snippet": line.strip()[:200],
                "matched": match.group(0),
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
        print("usage: scan_personalization.py <directory>", file=sys.stderr)
        return 2
    findings = scan_directory(Path(sys.argv[1]))
    print(json.dumps(findings, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
