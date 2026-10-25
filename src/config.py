"""Load a portable, validated experiment configuration."""

import math
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SAFE_FEATURES = {
    "age",
    "job",
    "marital",
    "education",
    "default",
    "housing",
    "loan",
    "pdays",
    "previous",
    "poutcome",
}
SPLITS = ("train", "validation", "final_test", "replay")


def load_config(path: Path | None = None) -> dict:
    """Load YAML; PROJEKT_SEED overrides the configured seed."""
    path = path or ROOT / "configs/config.yaml"
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    config["seed"] = int(os.environ.get("PROJEKT_SEED", config["seed"]))
    if not 0 <= config["seed"] < 2**32:
        raise ValueError("seed musi należeć do [0, 2**32).")
    fractions = [config["split"][name] for name in SPLITS]
    if any(not 0 < x < 1 for x in fractions) or not math.isclose(sum(fractions), 1):
        raise ValueError("Udziały split muszą być dodatnie i sumować się do 1.")
    features = config["data"]["features"]
    if not features or len(set(features)) != len(features) or not set(features) <= SAFE_FEATURES:
        raise ValueError("Lista cech zawiera duplikaty lub informacje niedostępne przed kontaktem.")
    if config["data"]["target"] != "y" or config["model"]["max_iter"] < 1:
        raise ValueError("Niepoprawny target lub max_iter.")
    for section, keys in {"data": ("raw", "manifest"), "paths": tuple(config["paths"])}.items():
        for key in keys:
            value = Path(config[section][key])
            if value.is_absolute() or not (ROOT / value).resolve().is_relative_to(ROOT):
                raise ValueError("Ścieżki konfiguracji muszą pozostawać wewnątrz projektu.")
    return config
