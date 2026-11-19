"""Offline CI validation and training on a deterministic, explicitly synthetic fixture."""

import argparse
import hashlib
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path

import joblib
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from src.config import ROOT, load_config
from src.data.schema import CATEGORIES
from src.data.validation import CATEGORICAL, NUMERIC, validate_dataframe
from src.experiments import sha256
from src.features.build import build_preprocessor
from src.pipeline import chronological_split, classification_metrics, write_json


def synthetic_fixture() -> pd.DataFrame:
    """Generate valid raw rows; this fixture says nothing about UCI model quality."""
    frame = pd.DataFrame({name: [1] * 320 for name in NUMERIC})
    for name in CATEGORICAL:
        frame[name] = sorted(CATEGORIES[name])[0]
    frame["age"] = [25 + i % 3 if i % 2 else 65 + i % 3 for i in range(len(frame))]
    frame["pdays"] = [999 if i % 2 else 5 for i in range(len(frame))]
    frame["previous"] = [0 if i % 2 else 1 for i in range(len(frame))]
    frame["emp.var.rate"] = [i / 1000 for i in range(len(frame))]
    frame["y"] = ["no" if i % 2 else "yes" for i in range(len(frame))]
    return frame


def run(output: Path) -> dict:
    """Save checked model/metrics and ML-BOM in a new directory; never read UCI."""
    output.mkdir(parents=True, exist_ok=False)
    config = load_config()
    frame = synthetic_fixture()
    validation_report = validate_dataframe(frame, expected_rows=320)
    fixture_hash = hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
    parts = chronological_split(frame, config["split"])
    fields = config["data"]["features"]
    train, validation = parts["train"], parts["validation"]
    metrics, hashes = {}, {}
    for name, classifier in {
        "dummy": DummyClassifier(strategy="most_frequent"),
        "logistic": LogisticRegression(max_iter=1000, random_state=config["seed"]),
    }.items():
        model = Pipeline([("preprocessing", build_preprocessor(fields)), ("model", classifier)])
        with threadpool_limits(limits=1):
            model.fit(train[fields], (train.y == "yes").astype(int))
            scores = model.predict_proba(validation[fields])[:, 1]
        metrics[name] = classification_metrics(
            (validation.y == "yes").astype(int), scores >= 0.5, scores
        )
        joblib.dump(model, output / f"{name}.joblib")
        hashes[name] = sha256(output / f"{name}.joblib")
    write_json(output / "metrics.json", metrics)
    if (
        metrics["logistic"]["average_precision"] < 0.90
        or metrics["logistic"]["average_precision"] <= metrics["dummy"]["average_precision"]
        or metrics["logistic"]["recall_yes"] < 0.90
    ):
        raise ValueError("Synthetic smoke quality gate failed")
    report = {
        "status": "PASS",
        "scope": "synthetic_ci_only",
        "seed": config["seed"],
        "validation": validation_report,
        "partition_rows": {name: len(part) for name, part in parts.items()},
        "final_test_evaluated": False,
        "replay_evaluated": False,
        "python": platform.python_version(),
        "metrics": metrics,
    }
    write_json(output / "smoke.json", report)
    write_json(
        output / "ml-bom.json",
        {
            "schema_version": 1,
            "scope": "synthetic_ci_only_not_a_deployed_model",
            "git_sha": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "uv_lock_sha256": sha256(ROOT / "uv.lock"),
            "source_sha256": {
                name: sha256(ROOT / name)
                for name in (
                    "scripts/ci_smoke.py",
                    "src/pipeline.py",
                    "src/features/build.py",
                    "configs/config.yaml",
                )
            },
            "working_tree_dirty": bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=ROOT, text=True
                ).strip()
            ),
            "dataset": {
                "source": "scripts.ci_smoke.synthetic_fixture",
                "license": "project-owned synthetic fixture; see repository code terms",
                "sha256": fixture_hash,
                "rows": len(frame),
            },
            "models": {
                name: {"version": hashes[name], "metrics": metrics[name]} for name in metrics
            },
            "dependencies": {
                name: version(name) for name in ("scikit-learn", "pandas", "numpy", "joblib")
            },
            "deployed": False,
        },
    )
    return report


def main() -> None:
    """Run the short validation/training gate with an explicit output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.output)["status"])


if __name__ == "__main__":
    main()
