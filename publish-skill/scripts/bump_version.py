"""Semantic version bump helper."""
import re
import sys

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def bump_version(current: str, part: str) -> str:
    match = SEMVER.match(current)
    if not match:
        raise ValueError(f"not a valid semver string: {current!r}")
    major, minor, patch = (int(group) for group in match.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"part must be 'major', 'minor', or 'patch', got {part!r}")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: bump_version.py <current-version> <major|minor|patch>", file=sys.stderr)
        return 2
    print(bump_version(sys.argv[1], sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
