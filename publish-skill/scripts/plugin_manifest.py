"""Read/write helpers for a plugin's .claude-plugin/plugin.json manifest."""
import argparse
import json
from pathlib import Path


def load_plugin_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_plugin_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def build_plugin_manifest(name: str, description: str, version: str, author_name: str, author_email: str | None = None) -> dict:
    author = {"name": author_name}
    if author_email:
        author["email"] = author_email
    return {
        "name": name,
        "description": description,
        "version": version,
        "author": author,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_version = subparsers.add_parser("get-version")
    get_version.add_argument("plugin_json_path")

    write = subparsers.add_parser("write")
    write.add_argument("plugin_json_path")
    write.add_argument("--name", required=True)
    write.add_argument("--description", required=True)
    write.add_argument("--version", required=True)
    write.add_argument("--author-name", required=True)
    write.add_argument("--author-email")

    args = parser.parse_args()
    path = Path(args.plugin_json_path)

    if args.command == "get-version":
        manifest = load_plugin_manifest(path)
        if manifest is None:
            return 1
        print(manifest.get("version", ""))
        return 0

    if args.command == "write":
        manifest = build_plugin_manifest(
            args.name, args.description, args.version, args.author_name, args.author_email
        )
        save_plugin_manifest(manifest, path)
        print(f"Wrote {path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
