import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.data.schema import CATEGORIES
from src.data.validation import CATEGORICAL, NUMERIC, validate_dataframe
from src.pipeline import evaluate, prepare, read_partition, train

MIN_SYNTHETIC_VALIDATION_AP = 0.90


def assert_quality(average_precision):
    assert average_precision >= MIN_SYNTHETIC_VALIDATION_AP, (
        f"Validation AP {average_precision:.3f} below {MIN_SYNTHETIC_VALIDATION_AP:.2f}"
    )


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
        df[column] = sorted(CATEGORIES[column])[:2] * 100
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
    assert_quality(result["models"]["model"]["average_precision"])
    with pytest.raises(AssertionError, match=r"Validation AP 0\.500 below 0\.90"):
        assert_quality(result["models"]["dummy"]["average_precision"])


def test_saved_pipeline_prediction_contract(prepared):
    config, root = prepared
    train(config)
    model = joblib.load(root / config["paths"]["models"] / "model.joblib")
    validation, _ = read_partition(config, "validation")
    fields = config["data"]["features"]
    batch = validation.loc[:2, fields]
    records = json.loads(batch.to_json(orient="records"))
    serving = pd.DataFrame.from_records(records)

    assert list(model.feature_names_in_) == list(serving) == fields
    assert {"duration", "y"}.isdisjoint(fields)
    for record in records:
        for field, value in record.items():
            assert type(value) is (int if field in NUMERIC else str)

    predictions = model.predict(serving)
    probabilities = model.predict_proba(serving)
    np.testing.assert_array_equal(model.classes_, [0, 1])
    assert predictions.shape == (len(records),)
    assert np.issubdtype(predictions.dtype, np.integer)
    assert np.isin(predictions, model.classes_).all()
    assert probabilities.shape == (len(records), 2)
    assert np.issubdtype(probabilities.dtype, np.floating)
    assert np.isfinite(probabilities).all()
    assert ((0 <= probabilities) & (probabilities <= 1)).all()
    np.testing.assert_allclose(probabilities.sum(axis=1), 1)
    np.testing.assert_allclose(model.predict_proba(batch), probabilities)

    with pytest.raises(ValueError, match="age"):
        model.predict_proba(serving.drop(columns="age"))


def test_model_change_reuses_preparation_but_split_change_fails(prepared):
    config, root = prepared
    metadata = root / config["paths"]["prepared"] / "metadata.json"
    before = metadata.read_bytes()
    config["model"]["max_iter"] += 1
    train(config)
    evaluate(config)
    assert metadata.read_bytes() == before
    config["split"]["train"] = 0.5
    with pytest.raises(ValueError, match="prepare"):
        train(config)


def test_transformers_fit_only_training_rows_and_never_in_evaluation(prepared, monkeypatch):
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    config, _ = prepared
    fitted_rows = []
    for transformer in [StandardScaler, OneHotEncoder]:
        original = transformer.fit

        def fit(self, x, y=None, _original=original, **kwargs):
            fitted_rows.append(len(x))
            return _original(self, x, y, **kwargs)

        monkeypatch.setattr(transformer, "fit", fit)
    train(config)
    assert fitted_rows == [120, 120, 120, 120]
    evaluate(config)
    assert fitted_rows == [120, 120, 120, 120]


def test_prepare_rejects_corruption_before_parsing(prepared, monkeypatch):
    config, root = prepared
    raw = root / config["data"]["raw"]
    with raw.open("r+b") as stream:
        stream.write(b"!")

    def forbidden_read(*args, **kwargs):
        pytest.fail("CSV parsing must not precede manifest verification")

    monkeypatch.setattr("src.pipeline.pd.read_csv", forbidden_read)
    with pytest.raises(ValueError, match="SHA-256"):
        prepare(config)


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
