"""Read verified lineage by alias or exact version without changing the registry."""

import argparse
import json
from pathlib import Path

from src.registry import LocalRegistry


def main() -> None:
    """Print version -> packaging run -> source run -> data/config/source lineage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--alias")
    group.add_argument("--version")
    args = parser.parse_args()
    if not (args.registry / "registry.db").is_file():
        parser.error("Existing local registry.db is required")
    store = LocalRegistry(args.registry)
    selected = store.resolve(args.alias) if args.alias else args.version
    print(json.dumps(store.lineage(selected), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
