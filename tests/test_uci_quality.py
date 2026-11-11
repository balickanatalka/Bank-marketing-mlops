import os
from pathlib import Path

import pytest
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from src.config import ROOT, load_config
from src.experiments import build_candidate, load_protocol, training_inputs
from src.features.build import build_preprocessor
from src.pipeline import classification_metrics

# Lesson 5 validation recorded seven true positives out of 794 for ordinary LR.
MIN_VALIDATION_RECALL = 7 / 794


def assert_validation_quality(metrics: dict, dummy_ap: float) -> None:
    ap = metrics["average_precision"]
    recall = metrics["recall_yes"]
    assert ap > dummy_ap, f"Validation AP {ap:.6f} must exceed Dummy AP {dummy_ap:.6f}"
    assert recall >= MIN_VALIDATION_RECALL, (
        f"Validation recall {recall:.6f} is below {MIN_VALIDATION_RECALL:.6f}"
    )


def test_uci_validation_quality_gate():
    source = os.environ.get("BANK_MARKETING_QUALITY_CSV")
    if not source:
        pytest.skip("Set BANK_MARKETING_QUALITY_CSV to a manifest-verified UCI CSV")
    csv_path = Path(source).resolve()
    if not csv_path.is_file():
        pytest.fail(f"BANK_MARKETING_QUALITY_CSV must point to an existing CSV: {csv_path}")

    config = load_config()
    config["data"]["raw"] = csv_path
    protocol = load_protocol(ROOT / "configs/experiments.yaml")
    train, validation, _ = training_inputs(config)
    fields = config["data"]["features"]
    x_train, y_train = train[fields], (train.y == "yes").astype(int)
    x_valid, y_valid = validation[fields], (validation.y == "yes").astype(int)
    metrics = {}
    for name in ("dummy", "logistic"):
        classifier = build_candidate(name, protocol["models"][name], protocol["seed"], y_train)
        preprocessor = build_preprocessor(fields).set_params(columns__sparse_threshold=0)
        model = Pipeline([("preprocessing", preprocessor), ("model", classifier)])
        with threadpool_limits(limits=1):
            model.fit(x_train, y_train)
            scores = model.predict_proba(x_valid)[:, 1]
        predicted = (scores >= protocol["decision_threshold"]).astype(int)
        metrics[name] = classification_metrics(y_valid, predicted, scores)

    dummy_ap = metrics["dummy"]["average_precision"]
    logistic = metrics["logistic"]
    print(
        f"UCI validation: train={len(train)}, validation={len(validation)}, "
        f"Dummy AP={dummy_ap:.9f}, logistic AP={logistic['average_precision']:.9f}, "
        f"logistic recall={logistic['recall_yes']:.9f}"
    )
    assert_validation_quality(logistic, dummy_ap)
    with pytest.raises(AssertionError, match="must exceed Dummy AP"):
        assert_validation_quality(metrics["dummy"], dummy_ap)
