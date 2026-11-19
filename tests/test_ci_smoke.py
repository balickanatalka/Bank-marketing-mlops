import json

import pytest

from scripts import ci_smoke
from scripts.ci_smoke import run, synthetic_fixture


def test_synthetic_training_and_holdout_isolation(tmp_path):
    output = tmp_path / "smoke"
    report = run(output)
    assert report["status"] == "PASS"
    assert report["final_test_evaluated"] is False
    assert report["replay_evaluated"] is False
    assert (
        report["metrics"]["logistic"]["average_precision"]
        > report["metrics"]["dummy"]["average_precision"]
    )
    bom = json.loads((output / "ml-bom.json").read_text())
    assert bom["deployed"] is False
    assert bom["dataset"]["rows"] == len(synthetic_fixture())
    assert all(len(item["version"]) == 64 for item in bom["models"].values())
    with pytest.raises(FileExistsError):
        run(output)


def test_quality_gate_rejects_a_regressed_smoke_model(tmp_path, monkeypatch):
    original = ci_smoke.classification_metrics

    def regressed(*args, **kwargs):
        return {**original(*args, **kwargs), "average_precision": 0.5, "recall_yes": 0.0}

    monkeypatch.setattr(ci_smoke, "classification_metrics", regressed)
    output = tmp_path / "rejected"
    with pytest.raises(ValueError, match="quality gate failed"):
        run(output)
    assert not (output / "smoke.json").exists()
    assert not (output / "ml-bom.json").exists()
