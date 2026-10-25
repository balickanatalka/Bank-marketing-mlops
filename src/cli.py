"""Command-line interface: python -m src.cli all."""

import argparse
import json
from pathlib import Path

from src.config import load_config
from src.pipeline import evaluate, prepare, train


def main() -> None:
    """Run explicit stages with a nonzero exit status on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "train", "evaluate", "all"])
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        actions = {"prepare": prepare, "train": train, "evaluate": evaluate}
        for name in actions if args.command == "all" else [args.command]:
            result = actions[name](config)
            print(
                json.dumps(
                    {
                        "stage": name,
                        "status": "OK",
                        "summary": result.get("models", result.get("splits", {})),
                    },
                    ensure_ascii=False,
                )
            )
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Błąd: {error}\n")


if __name__ == "__main__":
    main()
