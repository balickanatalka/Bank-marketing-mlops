"""DVC entry points using the existing downloader and training pipeline."""

import argparse
import os

import pandas as pd

from src.config import ROOT, load_config
from src.data.download import ensure_data
from src.data.validation import validate_dataframe
from src.pipeline import evaluate, prepare, train, write_json


def main() -> None:
    """Run one explicit stage; integrity failures propagate as nonzero exits."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["download", "validate", "prepare", "train", "evaluate"])
    args = parser.parse_args()
    if "PROJEKT_SEED" in os.environ:
        parser.error("For DVC, set seed in configs/lesson4.yaml; unset PROJEKT_SEED.")
    config = load_config(ROOT / "configs/lesson4.yaml")
    if args.stage == "download":
        ensure_data(ROOT / config["data"]["raw"], ROOT / config["data"]["manifest"])
    elif args.stage == "validate":
        ensure_data(ROOT / config["data"]["raw"], ROOT / config["data"]["manifest"])
        report = validate_dataframe(pd.read_csv(ROOT / config["data"]["raw"], sep=";"))
        write_json(ROOT / "artifacts/lesson4/validated.json", report)
    else:
        {"prepare": prepare, "train": train, "evaluate": evaluate}[args.stage](config)


if __name__ == "__main__":
    main()
