"""Read/update helpers for a Claude Code plugin marketplace.json index."""
import argparse
import json
from pathlib import Path


def default_marketplace(name: str, description: str) -> dict:
    return {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": name,
        "description": description,
        "owner": {"name": name},
        "plugins": [],
    }


def load_marketplace(path: Path, name: str = "marketplace", description: str = "") -> dict:
    if not path.exists():
        return default_marketplace(name, description)
    return json.loads(path.read_text(encoding="utf-8"))


def save_marketplace(marketplace: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")


def find_plugin(marketplace: dict, plugin_name: str) -> dict | None:
    for entry in marketplace.get("plugins", []):
        if entry.get("name") == plugin_name:
            return entry
    return None


def upsert_plugin(marketplace: dict, entry: dict) -> dict:
    plugins = marketplace.setdefault("plugins", [])
    for index, existing in enumerate(plugins):
        if existing.get("name") == entry["name"]:
            plugins[index] = entry
            return marketplace
    plugins.append(entry)
    return marketplace


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    upsert = subparsers.add_parser("upsert")
    upsert.add_argument("marketplace_path")
    upsert.add_argument("--name", required=True)
    upsert.add_argument("--description", required=True)
    upsert.add_argument("--source", required=True)
    upsert.add_argument("--category", required=True)
    upsert.add_argument("--author-name", default="James Kim")
    upsert.add_argument("--homepage")

    args = parser.parse_args()
    path = Path(args.marketplace_path)

    if args.command == "upsert":
        marketplace = load_marketplace(path, path.stem, "Security Engineering skill marketplace")
        entry = {
            "name": args.name,
            "description": args.description,
            "author": {"name": args.author_name},
            "source": args.source,
            "category": args.category,
        }
        if args.homepage:
            entry["homepage"] = args.homepage
        upsert_plugin(marketplace, entry)
        save_marketplace(marketplace, path)
        print(f"Updated {path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
