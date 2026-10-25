"""Shared preparation, training and validation evaluation functions."""

import hashlib
import json
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from src.config import ROOT, SPLITS
from src.data.download import ensure_data, verify_manifest
from src.data.validation import validate_dataframe

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def write_json(path: Path, payload: dict) -> None:
    """Write a UTF-8 report with finite JSON values only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


def config_hash(config: dict) -> str:
    """Identify the complete effective configuration, including seed override."""
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def chronological_split(df: pd.DataFrame, fractions: dict) -> dict[str, pd.DataFrame]:
    """Partition by row order, assigning rounding remainder to replay."""
    boundaries = [0]
    for name in SPLITS[:-1]:
        boundaries.append(boundaries[-1] + int(len(df) * fractions[name]))
    boundaries.append(len(df))
    result = {
        name: df.iloc[start:end].copy()
        for name, start, end in zip(SPLITS, boundaries[:-1], boundaries[1:], strict=True)
    }
    if any(part.empty for part in result.values()):
        raise ValueError("Za mało danych do czterech niepustych części.")
    return result


def prepare(config: dict) -> dict:
    """Verify raw bytes before parsing, validate and persist chronological partitions."""
    manifest = ensure_data(ROOT / config["data"]["raw"], ROOT / config["data"]["manifest"])
    df = pd.read_csv(ROOT / config["data"]["raw"], sep=";")
    report = validate_dataframe(df)
    parts = chronological_split(df, config["split"])
    destination = ROOT / config["paths"]["prepared"]
    destination.mkdir(parents=True, exist_ok=True)
    report["splits"] = {}
    for name, part in parts.items():
        path = destination / f"{name}.csv"
        part.to_csv(path, index=False)
        report["splits"][name] = {
            "rows": len(part),
            "start_inclusive": int(part.index[0]),
            "end_exclusive": int(part.index[-1]) + 1,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    report["raw_sha256"] = manifest["sha256"]
    report["config_sha256"] = config_hash(config)
    write_json(destination / "metadata.json", report)
    write_json(ROOT / config["paths"]["reports"] / "data_validation.json", report)
    counts = df.y.value_counts()
    fig, ax = plt.subplots()
    ax.bar(counts.index, counts.values)
    ax.set(xlabel="Klasa", ylabel="Liczba rekordów", title="UCI Bank Marketing — klasy")
    fig.savefig(ROOT / config["paths"]["reports"] / "class_distribution.png")
    plt.close(fig)
    return report


def read_partition(config: dict, name: str) -> tuple[pd.DataFrame, dict]:
    """Reject stale preparation and modified partitions before consuming them."""
    base = ROOT / config["paths"]["prepared"]
    metadata = json.loads((base / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / config["data"]["manifest"]).read_text(encoding="utf-8"))
    verify_manifest(ROOT / config["data"]["raw"], manifest)
    if metadata["config_sha256"] != config_hash(config):
        raise ValueError("Konfiguracja zmieniła się; uruchom prepare ponownie.")
    if metadata["raw_sha256"] != manifest["sha256"]:
        raise ValueError("Niezgodne pochodzenie przygotowanych danych.")
    path = base / f"{name}.csv"
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["splits"][name]["sha256"]:
        raise ValueError("Zmodyfikowany przygotowany zbiór danych.")
    return pd.read_csv(path), metadata


def history_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Treat pdays=999 as no previous contact, rather than 999 elapsed days."""
    frame = frame.copy()
    frame["not_previously_contacted"] = (frame.pdays == 999).astype(int)
    frame["pdays"] = frame.pdays.mask(frame.pdays == 999, 0)
    return frame


def build_preprocessor(features: list[str]) -> Pipeline:
    """Build one preprocessing path; fitting is performed only by training."""
    numeric = [c for c in features if c in {"age", "pdays", "previous"}]
    if "pdays" in features:
        numeric.append("not_previously_contacted")
    categorical = [c for c in features if c not in {"age", "pdays", "previous"}]
    steps = []
    if "pdays" in features:
        steps.append(("history", FunctionTransformer(history_features)))
    steps.append(
        (
            "columns",
            ColumnTransformer(
                [
                    ("numeric", StandardScaler(), numeric),
                    ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
                ]
            ),
        )
    )
    return Pipeline(steps)


def train(config: dict) -> dict:
    """Fit and save baseline and logistic pipelines using train rows exclusively."""
    df, metadata = read_partition(config, "train")
    features = config["data"]["features"]
    x, y = df[features], (df.y == "yes").astype(int)
    models = ROOT / config["paths"]["models"]
    models.mkdir(parents=True, exist_ok=True)
    for name, classifier in {
        "dummy": DummyClassifier(strategy="most_frequent"),
        "model": LogisticRegression(
            max_iter=config["model"]["max_iter"], random_state=config["seed"]
        ),
    }.items():
        model = Pipeline([("preprocessing", build_preprocessor(features)), ("model", classifier)])
        model.fit(x, y)
        joblib.dump(model, models / f"{name}.joblib")
    revision = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()
        or None
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()
    record = {
        "config": config,
        "config_sha256": config_hash(config),
        "raw_sha256": metadata["raw_sha256"],
        "git_head": revision,
        "working_tree_dirty": bool(dirty),
        "python": platform.python_version(),
        "dependencies": {
            name: version(name) for name in ["pandas", "scikit-learn", "numpy", "joblib", "pyyaml"]
        },
        "model_sha256": {
            name: hashlib.sha256((models / f"{name}.joblib").read_bytes()).hexdigest()
            for name in ["dummy", "model"]
        },
        "source_sha256": {
            str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted((ROOT / "src").rglob("*.py"))
        },
    }
    write_json(models / "training_metadata.json", record)
    return record


def evaluate(config: dict) -> dict:
    """Evaluate validation only; final test and replay are never loaded here."""
    df, _ = read_partition(config, "validation")
    models = ROOT / config["paths"]["models"]
    record = json.loads((models / "training_metadata.json").read_text(encoding="utf-8"))
    if record["config_sha256"] != config_hash(config):
        raise ValueError("Model pochodzi z innej konfiguracji; uruchom train.")
    x, y = df[config["data"]["features"]], (df.y == "yes").astype(int)
    result = {
        "evaluation_split": "validation",
        "final_test_evaluated": False,
        "support": {"no": int((y == 0).sum()), "yes": int(y.sum())},
        "training": record,
        "models": {},
    }
    reports = ROOT / config["paths"]["reports"]
    reports.mkdir(parents=True, exist_ok=True)
    for name in ["dummy", "model"]:
        path = models / f"{name}.joblib"
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["model_sha256"][name]:
            raise ValueError("Hash artefaktu modelu nie zgadza się z metadanymi.")
        # Only load artifacts created by this trusted local training process.
        model = joblib.load(path)
        predicted, scores = model.predict(x), model.predict_proba(x)[:, 1]
        result["models"][name] = {
            "accuracy": accuracy_score(y, predicted),
            "macro_f1": f1_score(y, predicted, average="macro", zero_division=0),
            "average_precision": average_precision_score(y, scores),
            "precision_yes": precision_score(y, predicted, zero_division=0),
            "recall_yes": recall_score(y, predicted, zero_division=0),
            "roc_auc": roc_auc_score(y, scores),
            "brier_score": float(np.mean((scores - y.to_numpy()) ** 2)),
            "lift_at_10_percent": None
            if np.ptp(scores) == 0
            else float(
                y.iloc[np.argsort(-scores, kind="stable")[: max(1, int(len(y) * 0.1))]].mean()
                / y.mean()
            ),
        }
        ConfusionMatrixDisplay.from_predictions(y, predicted, labels=[0, 1])
        plt.savefig(reports / f"confusion_matrix_{name}.png")
        plt.close()
    write_json(reports / "metrics.json", result)
    return result
