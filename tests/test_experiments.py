import json
import shutil

import numpy as np
import pandas as pd
import pytest

from src import experiments
from src.config import ROOT, load_config
from src.experiment_report import comparison_table, export_comparison


def test_selection_obeys_recall_floor_and_ap_and_tie_order():
    protocol = experiments.load_protocol(ROOT / "configs/experiments.yaml")
    results = {
        name: {"metrics": {"average_precision": 0.3, "recall_yes": 0.4}}
        for name in experiments.MODEL_ORDER
    }
    results["dummy"]["metrics"] = {"average_precision": 0.1, "recall_yes": 0}
    results["xgboost"]["metrics"] = {"average_precision": 0.9, "recall_yes": 0.1}
    selected = experiments.select_model(results, protocol)
    assert selected["winner"] == "logistic"
    assert "xgboost" not in selected["eligible"]
    for name in results:
        results[name]["metrics"]["average_precision"] = 0.1
    assert experiments.select_model(results, protocol)["winner"] is None


def test_weights_use_only_train_and_config_is_not_mutated():
    params = {"n_estimators": 2}
    model = experiments.build_candidate("xgboost", params, 42, pd.Series([0, 0, 0, 1]))
    assert model.scale_pos_weight == 3
    assert model.n_jobs == 1
    assert params == {"n_estimators": 2}


def test_protocol_rejects_changed_threshold(tmp_path):
    source = (ROOT / "configs/experiments.yaml").read_text(encoding="utf-8")
    path = tmp_path / "protocol.yaml"
    path.write_text(source.replace("decision_threshold: 0.5", "decision_threshold: 0.4"))
    with pytest.raises(ValueError, match="threshold"):
        experiments.load_protocol(path)


def test_only_train_validation_returned(monkeypatch):
    frame = pd.DataFrame({"age": [1, 2]})
    monkeypatch.setattr(experiments, "ensure_data", lambda *a: {"sha256": "pinned"})
    monkeypatch.setattr(experiments.pd, "read_csv", lambda *a, **k: frame)
    monkeypatch.setattr(experiments, "validate_dataframe", lambda *a: None)
    # Holdout objects cannot be interpreted as frames or used for scoring.
    monkeypatch.setattr(
        experiments,
        "chronological_split",
        lambda *a: dict(train=frame, validation=frame, final_test=object(), replay=object()),
    )
    train, validation, _ = experiments.training_inputs(load_config())
    assert train is frame and validation is frame


def test_local_tracking_six_runs_roundtrip_and_exclusive_reports(tmp_path, monkeypatch):
    config = load_config()
    config["data"]["features"] = ["age", "pdays", "job"]
    frame = pd.DataFrame(
        {
            "age": [20, 60] * 40,
            "pdays": [999, 5] * 40,
            "job": ["a", "b"] * 40,
            "y": ["no", "yes"] * 40,
        }
    )
    monkeypatch.setattr(
        experiments,
        "training_inputs",
        lambda cfg: (frame, frame.iloc[:20].copy(), {"sha256": "synthetic"}),
    )
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "https://invalid.example.test")
    protocol = ROOT / "configs/experiments.yaml"
    for name in ["uv.lock", "dvc.lock"]:
        shutil.copyfile(ROOT / name, tmp_path / name)
    monkeypatch.setattr(experiments, "ROOT", tmp_path)
    result = experiments.run_experiments(protocol, config=config)
    assert len(result["results"]) == 6
    assert not result["provenance"]["final_test_evaluated"]
    assert not result["provenance"]["replay_evaluated"]
    batch = next((tmp_path / "artifacts/lesson5").iterdir())
    protocol_before = (batch / "protocol.json").read_bytes()
    assert all(value["serialization_predictions_equal"] for value in result["results"].values())
    exported = export_comparison(batch, tmp_path / "reports")
    assert comparison_table(exported).shape[0] == 6
    assert max(len(c["precision"]) for c in exported["display_curves"].values()) <= 200
    assert (batch / "protocol.json").read_bytes() == protocol_before
    report = tmp_path / "reports/lesson5_experiments.json"
    before = report.read_bytes()
    with pytest.raises(FileExistsError):
        export_comparison(batch, tmp_path / "reports")
    assert report.read_bytes() == before
    assert json.loads(before)["selection"]["evaluation_split"] == "validation"
    with pytest.raises(FileExistsError):
        experiments.run_experiments(protocol, batch, config=config)


def test_error_aggregates_preserve_counts_without_rows():
    frame = pd.DataFrame({"age": [20, 40, 60], "pdays": [999, 3, 999]})
    result = experiments.error_analysis(
        frame, pd.Series([0, 1, 1]), np.array([0, 0, 1]), np.array([0.1, 0.3, 0.9])
    )
    assert result["confusion_matrix"] == [[1, 0], [1, 1]]
    assert sum(item["support"] for item in result["probability_bins"]) == 3
    assert "rows" not in result
