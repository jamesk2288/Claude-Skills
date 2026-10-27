---
name: publish-skill
description: Package a finished Claude Code skill from any local directory into a redacted, ready-to-share zip in the Downloads folder, after validating structure and scrubbing secrets and personalized content. Trigger on "publish this skill", "package skill for sharing", "publish-skill <path>", or when a finished skill is ready to hand to a teammate.
---

# publish-skill

Packages a finished skill from any local directory into a zip file (default: `~/Downloads/<skill-name>.zip`), after validating its structure and auto-redacting secrets and personalized content (hardcoded paths/emails). The zip is self-contained: it includes a `SETUP.md` with install instructions addressed to the recipient's own Claude Code session, and an `.install-manifest.json` (with a per-file hash map) so a later re-share of the same skill can be recognized as an update — and so the recipient's install can tell which of their installed files were locally edited and merge upstream changes into those instead of overwriting them.

This is a fully local tool — no GitLab, no marketplace, no network calls. (The team marketplace/GitLab-publish design is deferred; see `docs/specs/2026-09-15-publish-skill-design.md` and `docs/specs/2026-10-16-publish-skill-zip-export-design.md`.)

Run scripts with the `py` launcher (confirmed working in this environment; plain `python`/`python3` do not resolve). All script paths below are relative to this skill's own directory (`scripts/...`).

## Workflow

1. **Get the source skill path** from the user (the finished skill's directory anywhere on disk), and an optional output directory (defaults to `~/Downloads`).
2. **Run the packager**:
   ```
   py scripts/package_skill.py "<source-skill-path>" [--out "<output-dir>"]
   ```
3. **Report the result** to the user: the zip path, how many secret/personalization matches were auto-redacted (and of what kind), and any auto-detected prerequisites (external CLI tools, Python packages, env vars) the recipient should verify — all of this is also baked into the zip's own `SETUP.md`.

That's the whole interactive surface on the packaging side — there are no confirmation gates here. (The *install* side has its own confirm-before-update gate — see the generated `SETUP.md`'s Step 3.) Validation is a hard stop (see below); everything else is handled automatically.

## What the packager does

1. **Validate structure**: confirms a `SKILL.md` (or `.claud` file) exists at the top of the source directory with non-empty `name` and `description` frontmatter fields. If missing or malformed, the script exits non-zero and prints exactly what's wrong — report this to the user and stop.
2. **Stage**: copies the skill into a temp directory (excluding `__pycache__`, `*.pyc`, `.git`).
3. **Scan and redact**: runs both `scan_secrets.py`'s and `scan_personalization.py`'s patterns against the staged copy in a single pass, replacing every match in place with `<REDACTED:pattern_name>`. Always redacts automatically — never a confirmation gate.
4. **Package**: computes a content hash of the staged tree and a per-file hash map, writes `.install-manifest.json` (skill name, `packaged_at`, `content_hash`, `files`), auto-detects likely prerequisites, writes `SETUP.md` with install/update instructions for the recipient — including, on an update, classifying which installed files were locally edited, summarizing the change and confirming with the user, then merging upstream changes into edited files instead of overwriting them — and zips the result to `<out>/<skill-name>.zip`.

## Error Handling

| Condition | Behavior |
|---|---|
| Invalid/missing `SKILL.md`/`.claud` or required frontmatter fields | Script exits non-zero with specifics; report and stop. |
| Secret or personalized content detected | Always auto-redacted; never aborts; reported in the summary and in the zip's `SETUP.md`. |
| Source path doesn't exist or isn't a directory | Script exits non-zero with a clear error. |
