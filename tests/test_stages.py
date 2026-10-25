import hashlib
import json

import pandas as pd
import pytest

from src.config import load_config
from src.data.validation import CATEGORICAL, NUMERIC, validate_dataframe
from src.pipeline import evaluate, prepare, train


def test_report_output_removes_local_paths():
    from pathlib import Path

    from scripts.verify_reproduction import ROOT, sanitize_output

    result = "20 passed; average_precision=0.18504639379371762; SHA-256=74adfc"
    for project, home in [(str(ROOT), str(Path.home())), (ROOT.as_posix(), Path.home().as_posix())]:
        output = sanitize_output(f"{project}/reports/result.json; {home}/cache; {result}")
        assert project not in output and home not in output
        assert "PROJECT_ROOT/reports/result.json" in output
        assert "<USER_HOME>/cache" in output
        assert result in output


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    config = load_config()
    raw = tmp_path / config["data"]["raw"]
    raw.parent.mkdir(parents=True)
    df = pd.DataFrame({c: [1, 2] * 100 for c in NUMERIC})
    for column in CATEGORICAL:
        df[column] = ["a", "b"] * 100
    df["y"] = ["no", "yes"] * 100
    df.to_csv(raw, index=False, sep=";")
    manifest = tmp_path / config["data"]["manifest"]
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                "size_bytes": raw.stat().st_size,
            }
        )
    )
    monkeypatch.setattr("src.pipeline.ROOT", tmp_path)
    monkeypatch.setattr(
        "src.pipeline.validate_dataframe",
        lambda frame: validate_dataframe(frame, expected_rows=200),
    )
    prepare(config)
    return config, tmp_path


def test_stages_do_not_consume_holdout(prepared):
    config, root = prepared
    # A corrupted holdout must not be read by training or validation evaluation.
    for name in ["final_test", "replay"]:
        (root / config["paths"]["prepared"] / f"{name}.csv").write_text("DO NOT READ")
    train(config)
    result = evaluate(config)
    assert result["evaluation_split"] == "validation"
    assert not result["final_test_evaluated"]
    assert result["models"]["model"]["average_precision"] > 0.9


@pytest.mark.parametrize("fault", ["config", "partition", "model"])
def test_reject_stale_or_tampered_artifacts(prepared, fault):
    config, root = prepared
    train(config)
    if fault == "config":
        config["seed"] += 1
    elif fault == "partition":
        (root / config["paths"]["prepared"] / "validation.csv").write_text("tampered")
    else:
        (root / config["paths"]["models"] / "model.joblib").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        evaluate(config)
