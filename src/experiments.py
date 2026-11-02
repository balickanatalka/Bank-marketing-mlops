"""Run controlled local MLflow experiments without changing baseline artifacts."""

import argparse
import hashlib
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import joblib
import matplotlib
import numpy as np
import pandas as pd
import yaml
from mlflow import MlflowClient
from mlflow.entities import Metric, Param
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
)
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits
from xgboost import XGBClassifier

from src.config import ROOT, load_config
from src.data.download import ensure_data
from src.data.validation import validate_dataframe
from src.features.build import build_preprocessor
from src.pipeline import chronological_split, classification_metrics, config_hash, write_json

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

MODEL_ORDER = (
    "dummy",
    "logistic",
    "logistic_balanced",
    "random_forest",
    "hist_gradient_boosting",
    "xgboost",
)


def sha256(path: Path) -> str:
    """Return a byte-level fingerprint for provenance."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_protocol(path: Path) -> dict:
    """Validate a fixed experiment protocol before any fit or tracking write."""
    protocol = yaml.safe_load(path.read_text(encoding="utf-8"))
    if set(protocol["models"]) != set(MODEL_ORDER):
        raise ValueError("Exactly the six controlled candidates are required")
    if protocol["decision_threshold"] != 0.5 or not 0 <= protocol["seed"] < 2**32:
        raise ValueError("Use the predefined threshold 0.5 and a valid seed")
    selection = protocol["selection"]
    if (
        selection["primary_metric"] != "average_precision"
        or selection["recall_floor_model"] != "logistic"
        or selection["require_above_dummy"] is not True
        or set(selection["tie_break_order"]) != set(MODEL_ORDER) - {"dummy"}
    ):
        raise ValueError("Invalid selection rule")
    return protocol


def build_candidate(name: str, parameters: dict, seed: int, y_train: pd.Series):
    """Build one classifier; estimate imbalance weights using train labels only."""
    options = dict(parameters)
    if name == "dummy":
        return DummyClassifier(**options)
    if name in {"logistic", "logistic_balanced"}:
        return LogisticRegression(random_state=seed, **options)
    if name == "random_forest":
        return RandomForestClassifier(random_state=seed, n_jobs=1, **options)
    if name == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(random_state=seed, **options)
    if name == "xgboost":
        positive = int(y_train.sum())
        if positive == 0 or positive == len(y_train):
            raise ValueError("Train must contain both target classes")
        return XGBClassifier(
            random_state=seed,
            n_jobs=1,
            scale_pos_weight=(len(y_train) - positive) / positive,
            **options,
        )
    raise ValueError(f"Unknown candidate: {name}")


def select_model(results: dict, protocol: dict) -> dict:
    """Apply the recorded AP/recall rule without looking at any holdout."""
    dummy_ap = results["dummy"]["metrics"]["average_precision"]
    recall_floor = results["logistic"]["metrics"]["recall_yes"]
    eligible = [
        name
        for name in protocol["selection"]["tie_break_order"]
        if results[name]["metrics"]["average_precision"] > dummy_ap
        and results[name]["metrics"]["recall_yes"] >= recall_floor
    ]
    winner = max(
        eligible, key=lambda name: results[name]["metrics"]["average_precision"], default=None
    )
    return {
        "winner": winner,
        "eligible": eligible,
        "recall_floor": recall_floor,
        "dummy_average_precision": dummy_ap,
        "threshold": 0.5,
        "primary_metric": "average_precision",
        "evaluation_split": "validation",
        "production_promoted": False,
    }


def error_analysis(
    frame: pd.DataFrame, y: pd.Series, predicted: np.ndarray, scores: np.ndarray
) -> dict:
    """Summarize validation errors without storing identifiable example rows."""
    result = {
        "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
        "subgroups": {},
        "probability_bins": [],
    }
    groups = {
        "age_under_30": frame.age < 30,
        "age_30_to_59": frame.age.between(30, 59),
        "age_60_plus": frame.age >= 60,
        "no_previous_contact": frame.pdays == 999,
        "previous_contact": frame.pdays != 999,
    }
    for name, mask in groups.items():
        actual, guessed = y.to_numpy()[mask], predicted[mask]
        result["subgroups"][name] = {
            "support": int(mask.sum()),
            "positive_support": int(actual.sum()),
            "confusion_matrix": (
                confusion_matrix(actual, guessed, labels=[0, 1]).tolist()
                if mask.any()
                else [[0, 0], [0, 0]]
            ),
        }
    for lower, upper in [(0, 0.1), (0.1, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]:
        mask = (scores >= lower) & (scores < upper)
        result["probability_bins"].append(
            {
                "lower": lower,
                "upper": min(upper, 1.0),
                "support": int(mask.sum()),
                "observed_positive_rate": float(y.to_numpy()[mask].mean()) if mask.any() else None,
            }
        )
    return result


def training_inputs(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Reuse raw integrity, schema and chronological split; return train/validation only."""
    manifest = ensure_data(ROOT / config["data"]["raw"], ROOT / config["data"]["manifest"])
    frame = pd.read_csv(ROOT / config["data"]["raw"], sep=";")
    validate_dataframe(frame)
    parts = chronological_split(frame, config["split"])
    return parts["train"], parts["validation"], manifest


def run_experiments(
    protocol_path: Path | None = None, output: Path | None = None, *, config: dict | None = None
) -> dict:
    """Create a fresh local batch with six runs, aggregate analysis and full provenance.

    Existing output directories are rejected. MLflow's URI is constructed locally,
    never inherited from an environment variable or remote tracking configuration.
    """
    config = config or load_config()
    protocol_path = protocol_path or ROOT / "configs/experiments.yaml"
    protocol = load_protocol(protocol_path)
    train, validation, manifest = training_inputs(config)
    batch = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    output = output or ROOT / "artifacts/lesson5" / batch
    output = output.resolve()
    if not output.is_relative_to((ROOT / "artifacts/lesson5").resolve()):
        raise ValueError("Experiment outputs must remain under artifacts/lesson5")
    output.mkdir(parents=True, exist_ok=False)
    # Persist the rule before fitting the first candidate.
    write_json(output / "protocol.json", protocol)
    write_json(output / "data_config.json", config)
    features = config["data"]["features"]
    x_train, y_train = train[features], (train.y == "yes").astype(int)
    x_valid, y_valid = validation[features], (validation.y == "yes").astype(int)
    revision = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()
        or None
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()
    provenance = {
        "batch_id": batch,
        "git_sha": revision,
        "working_tree_dirty": bool(dirty),
        "raw_sha256": manifest["sha256"],
        "seed": protocol["seed"],
        "python": platform.python_version(),
        "protocol_sha256": config_hash(protocol),
        "data_config_sha256": config_hash(config),
        "evaluation_split": "validation",
        "final_test_evaluated": False,
        "replay_evaluated": False,
        "split": config["split"],
        "features": features,
        "rows": {"train": len(train), "validation": len(validation)},
        "split_sha256": {
            name: hashlib.sha256(part.to_csv(index=False, lineterminator="\n").encode()).hexdigest()
            for name, part in [("train", train), ("validation", validation)]
        },
        "dependencies": {
            name: version(name)
            for name in [
                "pandas",
                "scikit-learn",
                "numpy",
                "joblib",
                "pyyaml",
                "mlflow",
                "xgboost-cpu",
            ]
        },
        "source_sha256": {
            p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted((ROOT / "src").rglob("*.py"))
        },
        "uv_lock_sha256": sha256(ROOT / "uv.lock"),
        "dvc_lock_sha256": sha256(ROOT / "dvc.lock"),
    }
    write_json(output / "provenance.json", provenance)
    tracking = output / "tracking"
    tracking.mkdir()
    client = MlflowClient(tracking_uri="sqlite:///" + (tracking / "mlflow.db").as_posix())
    experiment_id = client.create_experiment(
        "bank-marketing-validation", artifact_location=(tracking / "artifacts").as_uri()
    )
    results = {}
    fig, ax = plt.subplots()
    for name in MODEL_ORDER:
        classifier = build_candidate(name, protocol["models"][name], protocol["seed"], y_train)
        preprocessing = build_preprocessor(features)
        preprocessing.set_params(columns__sparse_threshold=0)
        pipeline = Pipeline([("preprocessing", preprocessing), ("model", classifier)])
        run = client.create_run(
            experiment_id,
            tags={
                "mlflow.runName": name,
                "batch_id": batch,
                "git_sha": revision or "unavailable",
                "raw_sha256": manifest["sha256"],
                "evaluation_split": "validation",
            },
        )
        run_id = run.info.run_id
        destination = output / name
        destination.mkdir()
        try:
            with threadpool_limits(limits=1):
                pipeline.fit(x_train, y_train)
                scores = pipeline.predict_proba(x_valid)[:, 1]
            predicted = (scores >= protocol["decision_threshold"]).astype(int)
            metrics = classification_metrics(y_valid, predicted, scores)
            metrics["f1_yes"] = f1_score(y_valid, predicted, zero_division=0)
            analysis = error_analysis(x_valid, y_valid, predicted, scores)
            write_json(destination / "metrics.json", metrics)
            write_json(destination / "errors.json", analysis)
            precision, recall, thresholds = precision_recall_curve(y_valid, scores)
            write_json(
                destination / "precision_recall.json",
                {
                    "precision": precision.tolist(),
                    "recall": recall.tolist(),
                    "thresholds": thresholds.tolist(),
                },
            )
            ax.plot(recall, precision, label=f"{name}: AP={metrics['average_precision']:.4f}")
            ConfusionMatrixDisplay.from_predictions(y_valid, predicted, labels=[0, 1])
            plt.savefig(destination / "confusion_matrix.png", bbox_inches="tight")
            plt.close()
            joblib.dump(pipeline, destination / "pipeline.joblib")
            reloaded = joblib.load(destination / "pipeline.joblib")
            with threadpool_limits(limits=1):
                np.testing.assert_allclose(
                    reloaded.predict_proba(x_valid),
                    pipeline.predict_proba(x_valid),
                    rtol=1e-12,
                    atol=1e-12,
                )
            params = {
                key: (str(value) if isinstance(value, float) and not np.isfinite(value) else value)
                for key, value in classifier.get_params().items()
                if value is not None
            }
            params.update(
                seed=protocol["seed"],
                decision_threshold=0.5,
                algorithm=name,
                protocol_sha256=provenance["protocol_sha256"],
            )
            write_json(destination / "parameters.json", params)
            client.log_batch(
                run_id,
                params=[Param(k, str(v)) for k, v in params.items()],
                metrics=[
                    Metric(k, float(v), int(time.time() * 1000), 0)
                    for k, v in metrics.items()
                    if v is not None
                ],
            )
            for file in [
                *destination.iterdir(),
                output / "protocol.json",
                output / "data_config.json",
                output / "provenance.json",
                ROOT / "uv.lock",
            ]:
                client.log_artifact(run_id, str(file))
            results[name] = {
                "run_id": run_id,
                "parameters": params,
                "metrics": metrics,
                "model_sha256": sha256(destination / "pipeline.joblib"),
                "serialization_predictions_equal": True,
            }
            client.set_terminated(run_id, status="FINISHED")
        except Exception:
            client.set_terminated(run_id, status="FAILED")
            raise
    selection = select_model(results, protocol)
    ax.axhline(y_valid.mean(), linestyle="--", color="grey", label="validation prevalence")
    ax.set(xlabel="Recall", ylabel="Precision", title="Validation Precision–Recall")
    ax.legend(fontsize=7)
    fig.savefig(output / "precision_recall.png", bbox_inches="tight")
    plt.close(fig)
    summary = {
        "schema_version": 1,
        "provenance": provenance,
        "results": results,
        "selection": selection,
        "experiment_id": experiment_id,
    }
    write_json(output / "summary.json", summary)
    for name in MODEL_ORDER:
        client.log_artifact(results[name]["run_id"], str(output / "summary.json"))
        client.log_artifact(results[name]["run_id"], str(output / "precision_recall.png"))
        saved = client.get_run(results[name]["run_id"])
        if saved.info.status != "FINISHED" or saved.data.metrics != {
            k: float(v) for k, v in results[name]["metrics"].items() if v is not None
        }:
            raise ValueError("MLflow read-back differs from recorded experiment")
    print(
        json.dumps(
            {
                "batch_id": batch,
                "output": output.relative_to(ROOT).as_posix(),
                "winner": selection["winner"],
                "runs": len(results),
            }
        ),
        flush=True,
    )
    return summary


def main() -> None:
    """Run a new batch from the command line; never overwrite an earlier batch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path)
    args = parser.parse_args()
    run_experiments(args.protocol)


if __name__ == "__main__":
    main()
