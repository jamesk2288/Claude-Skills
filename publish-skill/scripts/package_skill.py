"""Package a finished skill directory into a redacted, ready-to-share zip."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import scan_personalization
import scan_secrets


def find_skill_file(skill_dir: Path) -> Path | None:
    candidate = skill_dir / "SKILL.md"
    if candidate.is_file():
        return candidate
    claud_files = sorted(skill_dir.glob("*.claud"))
    return claud_files[0] if claud_files else None


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    frontmatter: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = value.strip()
    return frontmatter


def validate_structure(skill_dir: Path) -> str:
    skill_file = find_skill_file(skill_dir)
    if skill_file is None:
        return f"no SKILL.md or .claud file found at the top of {skill_dir}"
    frontmatter = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
    missing = [key for key in ("name", "description") if not frontmatter.get(key)]
    if missing:
        return f"{skill_file.name} is missing required frontmatter field(s): {', '.join(missing)}"
    return ""


PERSONALIZATION_PATTERNS = [
    ("hardcoded_user_path", scan_personalization.WINDOWS_USER_PATH),
    ("email_address", scan_personalization.EMAIL),
]

# Patterns that scan_secrets.py doesn't carry (it must stay unmodified/dormant
# per this project's design) but that redact_matches still needs locally.
LOCAL_EXTRA_PATTERNS = [
    ("private_key_pkcs8", re.compile(r"<REDACTED:private_key_pkcs8>")),
]

# Pattern names whose presence anywhere in a file means the *whole file* gets
# replaced with one placeholder line rather than redacted line-by-line: a
# private key's body is unredacted base64 with no further secret-shaped
# tokens on each line, so line-by-line redaction only strips the header.
PRIVATE_KEY_PATTERN_NAMES = {"private_key_header", "private_key_pkcs8"}

# A header match alone isn't enough to justify a whole-file wipe - prose or
# test fixtures can mention a key header string without an actual key body.
# Require a matching footer elsewhere in the same file too.
PRIVATE_KEY_FOOTER_RE = re.compile(r"-----END (?:(?:RSA|EC|OPENSSH|PGP|DSA) )?PRIVATE KEY-----")


def build_redaction_patterns() -> tuple[list[tuple[str, re.Pattern]], set[str]]:
    patterns = scan_secrets.SECRET_PATTERNS + PERSONALIZATION_PATTERNS + LOCAL_EXTRA_PATTERNS
    text_extensions = scan_secrets.TEXT_EXTENSIONS | scan_personalization.TEXT_EXTENSIONS
    return patterns, text_extensions


def iter_scannable_files(root: Path, text_extensions: set[str]):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix and path.suffix.lower() not in text_extensions:
            continue
        yield path


def redact_matches(staged_root: Path, patterns, text_extensions, unreadable: list | None = None) -> list[dict]:
    # Deliberately NOT iter_scannable_files: that filters by extension, which
    # is fine for the soft heuristics in detect_prerequisites but would let a
    # secret in a .env/.ini/.ps1/.conf/etc. ship unredacted. Walk every file
    # instead and let the UTF-8 decode attempt be the only filter.
    redactions = []
    private_key_patterns = [(name, pattern) for name, pattern in patterns if name in PRIVATE_KEY_PATTERN_NAMES]
    for path in sorted(staged_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8", newline="") as f:
                text = f.read()
        except (UnicodeDecodeError, OSError):
            if unreadable is not None:
                unreadable.append(str(path.relative_to(staged_root)))
            continue

        # Private key bodies are unredacted base64 below the header line, so
        # line-by-line redaction only strips the header. If a key pattern
        # matches AND a matching footer is present (i.e. this looks like an
        # actual key, not just a header string mentioned in prose/fixtures),
        # replace the whole file instead.
        whole_file_pattern_name = None
        if PRIVATE_KEY_FOOTER_RE.search(text):
            for pattern_name, pattern in private_key_patterns:
                if pattern.search(text):
                    whole_file_pattern_name = pattern_name
                    break
        if whole_file_pattern_name is not None:
            redactions.append({
                "file": str(path.relative_to(staged_root)),
                "line": 1,
                "pattern": whole_file_pattern_name,
            })
            with path.open("w", encoding="utf-8", newline="") as f:
                f.write(f"<REDACTED:{whole_file_pattern_name}>\n")
            continue

        lines = text.splitlines(keepends=True)
        changed = False
        for i, line in enumerate(lines):
            current = line
            for pattern_name, pattern in patterns:
                new_current, count = pattern.subn(f"<REDACTED:{pattern_name}>", current)
                if count:
                    redactions.append({
                        "file": str(path.relative_to(staged_root)),
                        "line": i + 1,
                        "pattern": pattern_name,
                    })
                    current = new_current
                    changed = True
            lines[i] = current
        if changed:
            with path.open("w", encoding="utf-8", newline="") as f:
                f.write("".join(lines))
    return redactions


MANIFEST_NAME = ".install-manifest.json"


def compute_content_hash(staged_root: Path, exclude: set[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(staged_root.rglob("*")):
        if not path.is_file() or path.name in exclude:
            continue
        rel = path.relative_to(staged_root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def compute_file_hashes(staged_root: Path, exclude: set[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(staged_root.rglob("*")):
        if not path.is_file() or path.name in exclude:
            continue
        rel = path.relative_to(staged_root).as_posix()
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def write_install_manifest(staged_root: Path, skill_name: str, content_hash: str, file_hashes: dict[str, str]) -> dict:
    manifest = {
        "skill_name": skill_name,
        "packaged_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": content_hash,
        "files": file_hashes,
    }
    (staged_root / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


CLI_TOOLS = [
    "glab", "gh", "aws", "az", "kubectl", "docker", "terraform",
    "psql", "mysql", "gcloud", "helm",
]
# Excludes '*'-adjacency too (not just \b's word-char check), since index
# name wildcards like `aws*cloudtrail` or `*aws*cloudtrail` otherwise match.
CLI_RE = re.compile(r"(?<![\w*])(" + "|".join(CLI_TOOLS) + r")(?![\w*])")

# Files where prose can mention a tool name without invoking it (e.g. "aws
# CloudTrail" as a log source). Restrict CLI_RE to code-formatted spans
# (inline `code` or fenced ```blocks```) in these; other text extensions are
# treated as code in full since that's what they are.
PROSE_EXTENSIONS = {".md", ".txt"}
CODE_SPAN_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)

IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)")
ENV_PY_RE = re.compile(
    r"os\.(?:environ(?:\.get)?\(?\[?|getenv\()['\"]([A-Za-z_][A-Za-z0-9_]*)"
)
ENV_SHELL_RE = re.compile(r"\$\{?([A-Z_][A-Z0-9_]*)\}?")

STDLIB_MODULES = set(getattr(sys, "stdlib_module_names", ()))


def extract_code_spans(text: str) -> str:
    return "\n".join(m.group(0) for m in CODE_SPAN_RE.finditer(text))


def detect_prerequisites(staged_root: Path, text_extensions: set[str]):
    tools, packages, env_vars = set(), set(), set()
    for path in iter_scannable_files(staged_root, text_extensions):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        cli_scan_text = extract_code_spans(text) if path.suffix in PROSE_EXTENSIONS else text
        for m in CLI_RE.finditer(cli_scan_text):
            tools.add(m.group(1))

        for line in text.splitlines():
            if path.suffix == ".py":
                m = IMPORT_RE.match(line)
                if m and m.group(1) not in STDLIB_MODULES:
                    name = m.group(1)
                    # Skip sibling modules within this same skill (e.g.
                    # `from scan_secrets import ...`) - those aren't pip
                    # packages the recipient needs to install.
                    if not any(staged_root.rglob(f"{name}.py")):
                        packages.add(name)
            for m in ENV_PY_RE.finditer(line):
                env_vars.add(m.group(1))
            if path.suffix in (".sh", ".yml", ".yaml"):
                for m in ENV_SHELL_RE.finditer(line):
                    env_vars.add(m.group(1))
    return sorted(tools), sorted(packages), sorted(env_vars)


def write_setup_md(staged_root: Path, skill_name: str, manifest: dict, redactions, tools, packages, env_vars, unreadable=None):
    unreadable = unreadable or []
    lines = [
        f"# Setup for `{skill_name}`",
        "",
        "Auto-generated by `publish-skill`. This file is instructions to "
        "execute, addressed to whichever Claude Code session the recipient "
        "points at this folder (a human can follow the same steps manually). "
        "Everything under 'Verify prerequisites' is a best-effort heuristic — "
        "confirm it, don't trust it blindly.",
        "",
        f"This package's own manifest: `content_hash={manifest['content_hash']}`, "
        f"`packaged_at={manifest['packaged_at']}`.",
        "",
        "## Step 0 — Locate the payload",
        "",
        "If you were handed a `.zip`, extract it to a temp directory first. "
        f"Everything below refers to the extracted `{skill_name}/` folder.",
        "",
        "## Step 1 — Pick the target skills directory",
        "",
        "Default to the personal skills directory:",
        "- macOS/Linux: `~/.claude/skills/`",
        "- Windows: `%USERPROFILE%\\.claude\\skills\\`",
        "",
        "If the user didn't already say which they want, ask whether they'd "
        "rather install this project-scoped instead (`.claude/skills/` under "
        "the current project) before proceeding. Call the chosen skills "
        f"directory `<target>` below; the final install path is `<target>/{skill_name}/`.",
        "",
        "## Step 2 — Check for an existing install (the update path)",
        "",
        f"Look for `<target>/{skill_name}/{MANIFEST_NAME}`.",
        "- **Missing:** this is a fresh install. Go to Step 4.",
        "- **Present:** compare its top-level `content_hash` to this "
        f"package's own (`{manifest['content_hash']}`, quoted above — no "
        "need to recompute it).",
        "  - **Same hash:** already up to date. Tell the user and stop "
        "here — do not touch the installed folder or continue to later "
        "steps.",
        "  - **Different hash:** this is a real update. Classify each file "
        "before touching anything:",
        "    - For every path in the *old* installed manifest's `files` "
        "map that still exists on disk, hash the currently-installed file "
        "(sha256 of the raw bytes — e.g. `sha256sum <file>` or "
        "PowerShell's `Get-FileHash -Algorithm SHA256`; don't hash decoded "
        "or line-ending-normalized text, or every file will look edited) "
        "and compare it to that recorded hash.",
        "      - **Match:** untouched since install — safe to overwrite "
        "with this package's version later, no discussion needed.",
        "      - **Mismatch:** locally edited — needs a careful merge in "
        "Step 4, not a plain overwrite.",
        "      - **Path also missing from this package:** removed "
        "upstream too. If it was also locally edited, this needs a "
        "keep-or-delete decision in Step 3; otherwise just remove it in "
        "Step 4.",
        "    - For every path in the *old* installed manifest's `files` "
        "map that no longer exists on disk at all: the user deleted it "
        "locally. Flag it for the Step 3 summary — Step 4 won't resurrect "
        "it from this package without asking.",
        "    - Separately, for every path in this package's `files` map "
        "that is absent from the old manifest: added upstream, just add "
        "it in Step 4.",
        "    - If the installed manifest has no `files` map (packaged "
        "before this classification existed), treat every installed file "
        "as unknown edit status — don't assume anything is untouched; "
        "still produce the Step 3 summary and confirm gate.",
        "",
        "## Step 3 — Summarize and confirm",
        "",
        "Only on a real update (hash differs): before touching any file, "
        "tell the user, in a few lines, which files are straightforward "
        "(classified untouched), which ones you'll merge because they were "
        "locally edited, any removed-upstream-but-locally-edited files "
        "that need a keep-or-delete decision from them, and any files you "
        "noticed they'd deleted locally (so they know you won't resurrect "
        "them). Ask them to confirm before proceeding. If they decline, "
        "stop — leave the installed folder and manifest untouched.",
        "",
        "## Step 4 — Install or merge the payload",
        "",
        f"On a fresh install: copy every file from this package except "
        f"`SETUP.md` into `<target>/{skill_name}/`. That's it.",
        "",
        "On an update, do not blanket-copy this package over the installed "
        "folder — apply per the Step 2 classification instead, file by file:",
        "- **Untouched files:** overwrite directly with this package's version, "
        "no further confirmation.",
        "- **Locally-edited files:** read both the installed (edited) version "
        "and this package's version in full, and merge by judgment — carry "
        "the upstream change in while preserving the user's customization. "
        "Don't ask per file; just do the merge and note what you did for the "
        "Step 7 report.",
        "  - Exception: if both versions changed the same section in "
        "incompatible ways and you can't confidently reconcile them, stop "
        "and ask the user about that one file.",
        "  - Exception: a locally-edited binary/non-UTF-8 file can't be "
        "text-merged — ask the user to pick keep-theirs or take-the-update "
        "instead of attempting a merge.",
        "- **Removed-upstream + locally-edited files:** resolve per the Step "
        "3 decision; never delete a locally-edited file silently.",
        "- **Installed file missing entirely** (user deleted it): treat as "
        "an intentional removal, don't resurrect it from this package "
        "without asking.",
        "- **Files new in this package, absent from the old manifest:** add "
        "them directly, nothing to merge.",
        "",
        "Finally, copy this package's own `.install-manifest.json` into the "
        "installed folder as your new baseline manifest (it's already "
        "correct as-is for untouched and newly-added files), then make two "
        "adjustments before you're done:",
        "- **Merged files:** make no changes to their entry — leave it at "
        "this package's (new upstream) hash. The merged file's on-disk "
        "content still carries your customization blended in, so it will "
        "keep differing from that hash and correctly show up as "
        "locally-edited again on the next update, prompting another merge "
        "instead of a silent overwrite.",
        "- **Kept-despite-removal files:** this package's manifest has no "
        "entry for them at all (upstream no longer ships that path) — add "
        "one yourself to the `files` map, using the hash from the *old* "
        "installed manifest (the pristine hash it diverged from before "
        "removal), not a hash of its current on-disk content. That keeps it "
        "permanently classified as locally-edited, so it can never fade "
        "into 'untouched' and get silently dropped or overwritten if a "
        "future release ever reintroduces that path.",
        "",
        "A file the user deleted locally needs no manifest fix-up either "
        "way — the next update will simply find it missing again and ask "
        "the same question.",
        "",
        "If you previously replaced any `<REDACTED:...>` placeholder with a "
        "real value: an untouched-file overwrite restores the placeholder, "
        "so re-check it after this update. A locally-edited file carrying "
        "your replacement value through the merge is expected to keep it.",
        "",
        "## Step 5 — Verify prerequisites",
        "",
        "Auto-detected, best-effort — check each one on the system and report "
        "found/missing. Do not install or configure anything missing yourself; "
        "that's a system-level change the user needs to confirm. Just tell them "
        "what's missing and how they'd normally get it.",
        "",
        "**Possible external tools** (check with `command -v <tool>` or equivalent): "
        + (", ".join(f"`{t}`" for t in tools) if tools else "none detected."),
        "",
        "**Possible Python packages** (check with `pip show <package>` or equivalent): "
        + (", ".join(f"`{p}`" for p in packages) if packages else "none detected."),
        "",
        "**Possible environment variables** (check if set): "
        + (", ".join(f"`{e}`" for e in env_vars) if env_vars else "none detected."),
        "",
        "**Files that could not be scanned for secrets** (binary or "
        "non-UTF-8 — verify manually before relying on this package's "
        "redaction): "
        + (", ".join(f"`{f}`" for f in unreadable) if unreadable else "none."),
        "",
        "Note: redaction runs against every file, including test fixtures — "
        "if the skill's own tests reference secret-like placeholder values, "
        "expect them to be redacted too.",
        "",
        "## Step 6 — Self-clean",
        "",
        f"Delete `SETUP.md` from the installed `<target>/{skill_name}/` folder — "
        "it's packaging-only, not part of the skill. Once the user confirms the "
        "install looks right, remove the temp extraction directory and/or the "
        f"original zip/download too. Leave `{MANIFEST_NAME}` in place inside the "
        "installed folder — it's what makes Step 2 possible next time this skill "
        "is shared and re-installed.",
        "",
        "## Step 7 — Report back",
        "",
        "Tell the user the install/update path, which files (if any) were merged "
        "and what was preserved, the prerequisite status summary, and that a new "
        "Claude Code session will pick up the skill.",
        "",
        "## Redacted secrets",
    ]
    if redactions:
        lines.append("These values were stripped before sharing. Replace each "
                      "`<REDACTED:...>` placeholder with your own value.")
        lines.append("")
        lines += [f"- `{r['file']}:{r['line']}` — {r['pattern']}" for r in redactions]
    else:
        lines.append("None detected.")
    lines.append("")

    (staged_root / "SETUP.md").write_text("\n".join(lines), encoding="utf-8")


def default_output_dir() -> Path:
    return Path.home() / "Downloads"


def package_skill(skill_dir: Path, out_dir: Path) -> dict:
    error = validate_structure(skill_dir)
    if error:
        raise ValueError(error)

    # Symlinks can't be allowed into staging: anything downstream (redaction's
    # file walk, the final zip write) uses normal open()/read() calls that
    # transparently follow a symlink, and if the target is outside the skill
    # dir, redact_matches's write-back would destructively modify that real
    # external file (e.g. ~/.ssh/id_rsa) when a pattern happens to match.
    symlinks = [p for p in skill_dir.rglob("*") if p.is_symlink()]
    if symlinks:
        raise ValueError(
            f"skill directory contains a symlink at {symlinks[0].relative_to(skill_dir)}; "
            "publish-skill doesn't support packaging symlinks (they could point outside "
            "the skill and either leak into the zip or be destructively modified) - "
            "replace it with a real copy before packaging."
        )

    skill_name = skill_dir.name
    patterns, text_extensions = build_redaction_patterns()

    with tempfile.TemporaryDirectory() as tmp:
        staged_root = Path(tmp) / skill_name
        shutil.copytree(
            skill_dir, staged_root,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
        )

        unreadable: list[str] = []
        redactions = redact_matches(staged_root, patterns, text_extensions, unreadable)
        content_hash = compute_content_hash(staged_root, exclude={"SETUP.md", MANIFEST_NAME})
        file_hashes = compute_file_hashes(staged_root, exclude={"SETUP.md", MANIFEST_NAME})
        manifest = write_install_manifest(staged_root, skill_name, content_hash, file_hashes)
        tools, packages, env_vars = detect_prerequisites(staged_root, text_extensions)
        write_setup_md(staged_root, skill_name, manifest, redactions, tools, packages, env_vars, unreadable)

        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / f"{skill_name}.zip"
        if zip_path.exists():
            zip_path.unlink()

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(staged_root.rglob("*")):
                if file_path.is_file():
                    zf.write(file_path, arcname=str(Path(skill_name) / file_path.relative_to(staged_root)))

    return {
        "zip_path": zip_path,
        "redactions": redactions,
        "tools": tools,
        "packages": packages,
        "env_vars": env_vars,
        "unreadable": unreadable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package a skill directory into a zip for local sharing."
    )
    parser.add_argument("skill_dir", help="Path to the skill directory to package")
    parser.add_argument("--out", default=None, help="Output directory for the zip (default: ~/Downloads)")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.is_dir():
        print(f"error: {skill_dir} is not a directory", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser().resolve() if args.out else default_output_dir()

    try:
        result = package_skill(skill_dir, out_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {result['zip_path']}")
    redactions = result["redactions"]
    if redactions:
        counts: dict[str, int] = {}
        for r in redactions:
            counts[r["pattern"]] = counts.get(r["pattern"], 0) + 1
        breakdown = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        print(f"Redacted {len(redactions)} match(es): {breakdown}")
    tools, packages, env_vars = result["tools"], result["packages"], result["env_vars"]
    if tools or packages or env_vars:
        print("Detected possible prerequisites (tools/packages/env vars) - see SETUP.md inside the zip.")
    unreadable = result.get("unreadable", [])
    if unreadable:
        print(
            f"{len(unreadable)} file(s) could not be scanned, verify manually: "
            + ", ".join(unreadable)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
